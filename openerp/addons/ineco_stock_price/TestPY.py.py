# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from lxml import etree
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
from operator import itemgetter
from itertools import groupby

from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp import netsvc
from openerp import tools
from openerp.tools import float_compare
import openerp.addons.decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)

class stock_picking(osv.osv):

    _inherit = 'stock.picking'
    
    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        """ Makes partial picking and moves done.
        @param partial_datas : Dictionary containing details of partial picking
                          like partner_id, partner_id, delivery_date,
                          delivery moves with product_id, product_qty, uom
        @return: Dictionary of values
        """
        if context is None:
            context = {}
        else:
            context = dict(context)
        res = {}
        move_obj = self.pool.get('stock.move')
        product_obj = self.pool.get('product.product')
        currency_obj = self.pool.get('res.currency')
        uom_obj = self.pool.get('product.uom')
        sequence_obj = self.pool.get('ir.sequence')
        wf_service = netsvc.LocalService("workflow")
        for pick in self.browse(cr, uid, ids, context=context):
            new_picking = None
            complete, too_many, too_few = [], [], []
            move_product_qty, prodlot_ids, product_avail, partial_qty, product_uoms = {}, {}, {}, {}, {}
            for move in pick.move_lines:
                if move.state in ('done', 'cancel'):
                    continue
                partial_data = partial_datas.get('move%s'%(move.id), {})
                product_qty = partial_data.get('product_qty',0.0)
                move_product_qty[move.id] = product_qty
                product_uom = partial_data.get('product_uom',False)
                if move.price_unit:
                    product_price = move.price_unit 
                else:
                    product_price = partial_data.get('product_price',0.0)
                product_currency = partial_data.get('product_currency',False)
                prodlot_id = partial_data.get('prodlot_id')
                prodlot_ids[move.id] = prodlot_id
                product_uoms[move.id] = product_uom
                partial_qty[move.id] = uom_obj._compute_qty(cr, uid, product_uoms[move.id], product_qty, move.product_uom.id)
                if move.product_qty == partial_qty[move.id]:
                    complete.append(move)
                elif move.product_qty > partial_qty[move.id]:
                    too_few.append(move)
                else:
                    too_many.append(move)

                # Average price computation
                if (pick.type == 'in') and (move.product_id.cost_method == 'average'):
                    product = product_obj.browse(cr, uid, move.product_id.id)
                    move_currency_id = move.company_id.currency_id.id
                    context['currency_id'] = move_currency_id
                    qty = uom_obj._compute_qty(cr, uid, product_uom, product_qty, product.uom_id.id)

                    if product.id in product_avail:
                        product_avail[product.id] += qty
                    else:
                        product_avail[product.id] = product.qty_available

                    if qty > 0:
                        new_price = currency_obj.compute(cr, uid, product_currency,
                                move_currency_id, product_price)
                        new_price = uom_obj._compute_price(cr, uid, product_uom, new_price,
                                product.uom_id.id)
                        if product.qty_available <= 0:
                            new_std_price = new_price
                        else:
                            # Get the standard price
                            amount_unit = product.price_get('standard_price', context=context)[product.id]
                            new_std_price = ((amount_unit * product_avail[product.id])\
                                + (new_price * qty))/(product_avail[product.id] + qty)
                        # Write the field according to price type field
                        product_obj.write(cr, uid, [product.id], {'standard_price': new_std_price})

                        # Record the values that were chosen in the wizard, so they can be
                        # used for inventory valuation if real-time valuation is enabled.
                        move_obj.write(cr, uid, [move.id],
                                {'price_unit': product_price,
                                 'price_currency_id': product_currency})


            for move in too_few:
                product_qty = move_product_qty[move.id]
                if not new_picking:
                    new_picking_name = pick.name
                    self.write(cr, uid, [pick.id], 
                               {'name': sequence_obj.get(cr, uid,
                                            'stock.picking.%s'%(pick.type)),
                               })
                    new_picking = self.copy(cr, uid, pick.id,
                            {
                                'name': new_picking_name,
                                'move_lines' : [],
                                'state':'draft',
                            })
                if product_qty != 0:
                    defaults = {
                            'product_qty' : product_qty,
                            'product_uos_qty': product_qty, #TODO: put correct uos_qty
                            'picking_id' : new_picking,
                            'state': 'assigned',
                            'move_dest_id': False,
                            'price_unit': move.price_unit,
                            'product_uom': product_uoms[move.id]
                    }
                    prodlot_id = prodlot_ids[move.id]
                    if prodlot_id:
                        defaults.update(prodlot_id=prodlot_id)
                    move_obj.copy(cr, uid, move.id, defaults)
                move_obj.write(cr, uid, [move.id],
                        {
                            'product_qty': move.product_qty - partial_qty[move.id],
                            'product_uos_qty': move.product_qty - partial_qty[move.id], #TODO: put correct uos_qty
                            'prodlot_id': False,
                            'tracking_id': False,
                        })

            if new_picking:
                move_obj.write(cr, uid, [c.id for c in complete], {'picking_id': new_picking})
            for move in complete:
                defaults = {'product_uom': product_uoms[move.id], 'product_qty': move_product_qty[move.id]}
                if prodlot_ids.get(move.id):
                    defaults.update({'prodlot_id': prodlot_ids[move.id]})
                move_obj.write(cr, uid, [move.id], defaults)
            for move in too_many:
                product_qty = move_product_qty[move.id]
                defaults = {
                    'product_qty' : product_qty,
                    'product_uos_qty': product_qty, #TODO: put correct uos_qty
                    'product_uom': product_uoms[move.id]
                }
                prodlot_id = prodlot_ids.get(move.id)
                if prodlot_ids.get(move.id):
                    defaults.update(prodlot_id=prodlot_id)
                if new_picking:
                    defaults.update(picking_id=new_picking)
                move_obj.write(cr, uid, [move.id], defaults)

            # At first we confirm the new picking (if necessary)
            if new_picking:
                wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_confirm', cr)
                # Then we finish the good picking
                self.write(cr, uid, [pick.id], {'backorder_id': new_picking})
                self.action_move(cr, uid, [new_picking], context=context)
                wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_done', cr)
                wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
                delivered_pack_id = new_picking
                back_order_name = self.browse(cr, uid, delivered_pack_id, context=context).name
                self.message_post(cr, uid, ids, body=_("Back order <em>%s</em> has been <b>created</b>.") % (back_order_name), context=context)
            else:
                self.action_move(cr, uid, [pick.id], context=context)
                wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
                delivered_pack_id = pick.id

            delivered_pack = self.browse(cr, uid, delivered_pack_id, context=context)
            res[pick.id] = {'delivered_picking': delivered_pack.id or False}

        return res
    
    

class stock_move(osv.osv):
    _inherit = 'stock.move'

    # FIXME: needs refactoring, this code is partially duplicated in stock_picking.do_partial()!
    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        """ Makes partial pickings and moves done.
        @param partial_datas: Dictionary containing details of partial picking
                          like partner_id, delivery_date, delivery
                          moves with product_id, product_qty, uom
        """
        res = {}
        picking_obj = self.pool.get('stock.picking')
        product_obj = self.pool.get('product.product')
        currency_obj = self.pool.get('res.currency')
        uom_obj = self.pool.get('product.uom')
        wf_service = netsvc.LocalService("workflow")

        if context is None:
            context = {}

        complete, too_many, too_few = [], [], []
        move_product_qty = {}
        prodlot_ids = {}
        for move in self.browse(cr, uid, ids, context=context):
            if move.state in ('done', 'cancel'):
                continue
            partial_data = partial_datas.get('move%s'%(move.id), False)
            assert partial_data, _('Missing partial picking data for move #%s.') % (move.id)
            product_qty = partial_data.get('product_qty',0.0)
            move_product_qty[move.id] = product_qty
            product_uom = partial_data.get('product_uom',False)
            if move.price_unit:
                product_price = move.price_unit 
            else:
                product_price = partial_data.get('product_price',0.0)
            product_currency = partial_data.get('product_currency',False)
            prodlot_ids[move.id] = partial_data.get('prodlot_id')
            if move.product_qty == product_qty:
                complete.append(move)
            elif move.product_qty > product_qty:
                too_few.append(move)
            else:
                too_many.append(move)

            # Average price computation
            if (move.picking_id.type == 'in') and (move.product_id.cost_method == 'average'):
                product = product_obj.browse(cr, uid, move.product_id.id)
                move_currency_id = move.company_id.currency_id.id
                context['currency_id'] = move_currency_id
                qty = uom_obj._compute_qty(cr, uid, product_uom, product_qty, product.uom_id.id)
                if qty > 0:
                    new_price = currency_obj.compute(cr, uid, product_currency,
                            move_currency_id, product_price)
                    new_price = uom_obj._compute_price(cr, uid, product_uom, new_price,
                            product.uom_id.id)
                    if product.qty_available <= 0:
                        new_std_price = new_price
                    else:
                        # Get the standard price
                        amount_unit = product.price_get('standard_price', context=context)[product.id]
                        new_std_price = ((amount_unit * product.qty_available)\
                            + (new_price * qty))/(product.qty_available + qty)

                    product_obj.write(cr, uid, [product.id],{'standard_price': new_std_price})

                    # Record the values that were chosen in the wizard, so they can be
                    # used for inventory valuation if real-time valuation is enabled.
                    self.write(cr, uid, [move.id],
                                {'price_unit': product_price,
                                 'price_currency_id': product_currency,
                                })

        for move in too_few:
            product_qty = move_product_qty[move.id]
            if product_qty != 0:
                defaults = {
                            'product_qty' : product_qty,
                            'product_uos_qty': product_qty,
                            'picking_id' : move.picking_id.id,
                            'state': 'assigned',
                            'move_dest_id': False,
                            'price_unit': move.price_unit,
                            }
                prodlot_id = prodlot_ids[move.id]
                if prodlot_id:
                    defaults.update(prodlot_id=prodlot_id)
                new_move = self.copy(cr, uid, move.id, defaults)
                complete.append(self.browse(cr, uid, new_move))
            self.write(cr, uid, [move.id],
                    {
                        'product_qty': move.product_qty - product_qty,
                        'product_uos_qty': move.product_qty - product_qty,
                        'prodlot_id': False,
                        'tracking_id': False,
                    })


        for move in too_many:
            self.write(cr, uid, [move.id],
                    {
                        'product_qty': move.product_qty,
                        'product_uos_qty': move.product_qty,
                    })
            complete.append(move)

        for move in complete:
            if prodlot_ids.get(move.id):
                self.write(cr, uid, [move.id],{'prodlot_id': prodlot_ids.get(move.id)})
            self.action_done(cr, uid, [move.id], context=context)
            if  move.picking_id.id :
                # TOCHECK : Done picking if all moves are done
                cr.execute("""
                    SELECT move.id FROM stock_picking pick
                    RIGHT JOIN stock_move move ON move.picking_id = pick.id AND move.state = %s
                    WHERE pick.id = %s""",
                            ('done', move.picking_id.id))
                res = cr.fetchall()
                if len(res) == len(move.picking_id.move_lines):
                    picking_obj.action_move(cr, uid, [move.picking_id.id])
                    wf_service.trg_validate(uid, 'stock.picking', move.picking_id.id, 'button_done', cr)

        return [move.id for move in complete]
