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

from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
from operator import itemgetter
from itertools import groupby

from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp import netsvc
from openerp import tools
from openerp.tools import float_compare, DEFAULT_SERVER_DATETIME_FORMAT
import openerp.addons.decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)

class stock_move(osv.osv):
    
    _columns = {
        'warehouse_id': fields.many2one('stock.warehouse','Warehouse',required=True),
        'location_department_id': fields.many2one('stock.location','Department', domain=[('usage','=','view')]),
    }

    def onchange_warehouse(self, cr, uid, ids, warehouse_id, context=None):

        result = {}
        picking_type = context.get('picking_type')
        if warehouse_id:
            if picking_type == 'in':
                warehouse = self.pool.get('stock.warehouse').browse(cr, uid, [warehouse_id])[0]
                result['location_dest_id'] = warehouse.lot_stock_id.id
                result['location_department_id'] = warehouse.lot_stock_id.id
            elif picking_type == 'out':
                warehouse = self.pool.get('stock.warehouse').browse(cr, uid, [warehouse_id])[0]
                result['location_id'] = warehouse.lot_stock_id.id    
                result['location_department_id'] = False
                result['location_dest_id'] = False
                        
        return {'value': result}

    def onchange_department(self, cr, uid, ids, location_department_id, context=None):
        result = {}
        picking_type = context.get('picking_type')
        if location_department_id:
            if picking_type == 'out':
                result['location_dest_id'] = False
        return result
    
        
    def _default_location_destination(self, cr, uid, context=None):
        """ Gets default address of partner for destination location
        @return: Address id or False
        """
        mod_obj = self.pool.get('ir.model.data')
        picking_type = context.get('picking_type')
        location_id = False
        if context is None:
            context = {}
        if context.get('move_line', []):
            if context['move_line'][0]:
                if isinstance(context['move_line'][0], (tuple, list)):
                    location_id = context['move_line'][0][2] and context['move_line'][0][2].get('location_dest_id',False)
                else:
                    move_list = self.pool.get('stock.move').read(cr, uid, context['move_line'][0], ['location_dest_id'])
                    location_id = move_list and move_list['location_dest_id'][0] or False
        elif context.get('address_out_id', False):
            property_out = self.pool.get('res.partner').browse(cr, uid, context['address_out_id'], context).property_stock_customer
            location_id = property_out and property_out.id or False
        else:
            location_xml_id = False
            if picking_type in ('in', 'internal'):
                sql = """
                    select sm.id from stock_move sm
                    left join stock_location sl on sm.location_id = sl.id
                    where sm.create_uid = %s and state <> 'cancel' and sl.usage in ('customer','supplier')
                    order by sm.create_date desc limit 1
                """
                cr.execute(sql % uid)
                move_id = cr.fetchone()
                if move_id:
                    move = self.pool.get('stock.move').browse(cr, uid, [move_id[0]])[0]
                    location_id = move.location_dest_id.id
                else:
                    location_xml_id = 'stock_location_stock'
            elif picking_type == 'out':
                sql = """
                    select sm.id from stock_move sm
                    left join stock_location sl on sm.location_dest_id = sl.id
                    where sm.create_uid = %s and state <> 'cancel' and sl.usage in ('customer','supplier')
                    order by sm.create_date desc limit 1
                """
                cr.execute(sql % uid)
                move_id = cr.fetchone()
                if move_id:
                    move = self.pool.get('stock.move').browse(cr, uid, [move_id[0]])[0]
                    location_id = move.location_dest_id.id
                else:
                    location_xml_id = 'stock_location_customers'
            if location_xml_id:
                location_model, location_id = mod_obj.get_object_reference(cr, uid, 'stock', location_xml_id)
        return location_id

    def _default_location_source(self, cr, uid, context=None):
        """ Gets default address of partner for source location
        @return: Address id or False
        """
        mod_obj = self.pool.get('ir.model.data')
        picking_type = context.get('picking_type')
        location_id = False

        if context is None:
            context = {}
        if context.get('move_line', []):
            try:
                location_id = context['move_line'][0][2]['location_id']
            except:
                pass
        elif context.get('address_in_id', False):
            part_obj_add = self.pool.get('res.partner').browse(cr, uid, context['address_in_id'], context=context)
            if part_obj_add:
                location_id = part_obj_add.property_stock_supplier.id
        else:
            location_xml_id = False
            if picking_type == 'in':
                location_xml_id = 'stock_location_suppliers'
            elif picking_type in ('out', 'internal'):
                sql = """
                    select sm.id from stock_move sm
                    left join stock_location sl on sm.location_dest_id = sl.id
                    where sm.create_uid = %s and state <> 'cancel' and sl.usage in ('customer','supplier')
                    order by sm.create_date desc limit 1
                """
                cr.execute(sql % uid)
                move_id = cr.fetchone()
                if move_id:
                    move = self.pool.get('stock.move').browse(cr, uid, [move_id[0]])[0]
                    location_id = move.location_id.id
                else:
                    location_xml_id = 'stock_location_stock'
            if location_xml_id:
                location_model, location_id = mod_obj.get_object_reference(cr, uid, 'stock', location_xml_id)
        return location_id    

    def _default_warehouse(self, cr, uid, context=None):
        """ Gets default address of partner for source location
        @return: Address id or False
        """
        warehouse_id = False

        if context is None:
            context = {}
        if context.get('move_line', []):
            try:
                warehouse_id = context['move_line'][0][2]['warehouse_id']
            except:
                pass
        else:
            sql = "select warehouse_id from stock_move where state <> 'cancel' order by create_date desc limit 1"
            cr.execute(sql)
            data_ids = cr.fetchone()
            warehouse_id = data_ids and data_ids[0] or 4
            
        return warehouse_id    

    def _default_department(self, cr, uid, context=None):
        """ Gets default address of partner for source location
        @return: Address id or False
        """

        location_id = False

        if context is None:
            context = {}
        if context.get('move_line', []):
            try:
                location_id = context['move_line'][0][2]['location_department_id']
            except:
                pass
        else:
            sql = "select location_department_id from stock_move where state <> 'cancel' order by create_date desc limit 1"
            cr.execute(sql)
            data_ids = cr.fetchone()
            location_id = data_ids and data_ids[0] or False
            
        return location_id    
    
    _inherit = 'stock.move'
    _defaults = {
        'location_id': _default_location_source,
        'location_dest_id': _default_location_destination,
        'warehouse_id': _default_warehouse,
        'location_department_id': _default_department,
    }
    
    def action_done(self, cr, uid, ids, context=None):
        """ Makes the move done and if all moves are done, it will finish the picking.
        @return:
        """
        picking_ids = []
        move_ids = []
        wf_service = netsvc.LocalService("workflow")
        if context is None:
            context = {}

        todo = []
        for move in self.browse(cr, uid, ids, context=context):
            if move.state=="draft":
                todo.append(move.id)
        if todo:
            self.action_confirm(cr, uid, todo, context=context)
            todo = []

        for move in self.browse(cr, uid, ids, context=context):
            if move.state in ['done','cancel']:
                continue
            move_ids.append(move.id)

            if move.picking_id:
                picking_ids.append(move.picking_id.id)
            if move.move_dest_id.id and (move.state != 'done'):
                # Downstream move should only be triggered if this move is the last pending upstream move
                other_upstream_move_ids = self.search(cr, uid, [('id','!=',move.id),('state','not in',['done','cancel']),
                                            ('move_dest_id','=',move.move_dest_id.id)], context=context)
                if not other_upstream_move_ids:
                    self.write(cr, uid, [move.id], {'move_history_ids': [(4, move.move_dest_id.id)]})
                    if move.move_dest_id.state in ('waiting', 'confirmed'):
                        self.force_assign(cr, uid, [move.move_dest_id.id], context=context)
                        if move.move_dest_id.picking_id:
                            wf_service.trg_write(uid, 'stock.picking', move.move_dest_id.picking_id.id, cr)
                        if move.move_dest_id.auto_validate:
                            self.action_done(cr, uid, [move.move_dest_id.id], context=context)

            self._create_product_valuation_moves(cr, uid, move, context=context)
            if move.state not in ('confirmed','done','assigned'):
                todo.append(move.id)

        if todo:
            self.action_confirm(cr, uid, todo, context=context)

        self.write(cr, uid, move_ids, {'state': 'done', 'date': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)}, context=context)
        
        for id in move_ids:
            wf_service.trg_trigger(uid, 'stock.move', id, cr)            

        for pick_id in picking_ids:
            wf_service.trg_write(uid, 'stock.picking', pick_id, cr)
        
        picking_type = context.get('picking_type')
        if picking_type == 'in':
            product_obj = self.pool.get('product.product')        
            for move in self.browse(cr, uid, move_ids):
                if move.product_id.cost_method == 'average' and move.product_id.valuation == 'real_time':
                    amount_unit = move.product_id.price_get('standard_price', context=context)[move.product_id.id]
                    new_std_price = ((amount_unit * (move.product_id.qty_available - move.product_qty))\
                        + (move.price_unit * move.product_qty))/(move.product_id.qty_available or 1.0)
                    product_obj.write(cr, uid, [move.product_id.id],{'standard_price': new_std_price})            

        return True    
    
    def _create_account_move_line(self, cr, uid, move, src_account_id, dest_account_id, reference_amount, reference_currency_id, context=None):
        """
        Generate the account.move.line values to post to track the stock valuation difference due to the
        processing of the given stock move.
        """
        # prepare default values considering that the destination accounts have the reference_currency_id as their main currency
        partner_id = (move.picking_id.partner_id and self.pool.get('res.partner')._find_accounting_partner(move.picking_id.partner_id).id) or False
        debit_line_vals = {
                    'name': move.name,
                    'product_id': move.product_id and move.product_id.id or False,
                    'quantity': move.product_qty,
                    'ref': move.picking_id and move.picking_id.name or False,
                    'date': time.strftime('%Y-%m-%d'),
                    'partner_id': partner_id,
                    'debit': reference_amount,
                    'account_id': dest_account_id,
                    'stock_move_id': move.id,
        }
        credit_line_vals = {
                    'name': move.name,
                    'product_id': move.product_id and move.product_id.id or False,
                    'quantity': move.product_qty,
                    'ref': move.picking_id and move.picking_id.name or False,
                    'date': time.strftime('%Y-%m-%d'),
                    'partner_id': partner_id,
                    'credit': reference_amount,
                    'account_id': src_account_id,
                    'stock_move_id': move.id,
        }

        # if we are posting to accounts in a different currency, provide correct values in both currencies correctly
        # when compatible with the optional secondary currency on the account.
        # Financial Accounts only accept amounts in secondary currencies if there's no secondary currency on the account
        # or if it's the same as that of the secondary amount being posted.
        account_obj = self.pool.get('account.account')
        src_acct, dest_acct = account_obj.browse(cr, uid, [src_account_id, dest_account_id], context=context)
        src_main_currency_id = src_acct.company_id.currency_id.id
        dest_main_currency_id = dest_acct.company_id.currency_id.id
        cur_obj = self.pool.get('res.currency')
        if reference_currency_id != src_main_currency_id:
            # fix credit line:
            credit_line_vals['credit'] = cur_obj.compute(cr, uid, reference_currency_id, src_main_currency_id, reference_amount, context=context)
            if (not src_acct.currency_id) or src_acct.currency_id.id == reference_currency_id:
                credit_line_vals.update(currency_id=reference_currency_id, amount_currency=-reference_amount)
        if reference_currency_id != dest_main_currency_id:
            # fix debit line:
            debit_line_vals['debit'] = cur_obj.compute(cr, uid, reference_currency_id, dest_main_currency_id, reference_amount, context=context)
            if (not dest_acct.currency_id) or dest_acct.currency_id.id == reference_currency_id:
                debit_line_vals.update(currency_id=reference_currency_id, amount_currency=reference_amount)

        return [(0, 0, debit_line_vals), (0, 0, credit_line_vals)]
    
    
    def onchange_product_id(self, cr, uid, ids, prod_id=False, loc_id=False,
                            loc_dest_id=False, partner_id=False):
        """ On change of product id, if finds UoM, UoS, quantity and UoS quantity.
        @param prod_id: Changed Product id
        @param loc_id: Source location id
        @param loc_dest_id: Destination location id
        @param partner_id: Address id of partner
        @return: Dictionary of values
        """
        if not prod_id:
            return {}
        lang = False
        if partner_id:
            addr_rec = self.pool.get('res.partner').browse(cr, uid, partner_id)
            if addr_rec:
                lang = addr_rec and addr_rec.lang or False
        ctx = {'lang': lang}

        product = self.pool.get('product.product').browse(cr, uid, [prod_id], context=ctx)[0]
        uos_id  = product.uos_id and product.uos_id.id or False
        result = {
            'product_uom': product.uom_id.id,
            'product_uos': uos_id,
            'product_qty': 1.00,
            'product_uos_qty' : self.pool.get('stock.move').onchange_quantity(cr, uid, ids, prod_id, 1.00, product.uom_id.id, uos_id)['value']['product_uos_qty'],
            'prodlot_id' : False,
            'price_unit' : product.standard_price or 0.0,
        }
        if not ids:
            result['name'] = product.partner_ref
        if loc_id:
            result['location_id'] = loc_id
        if loc_dest_id:
            result['location_dest_id'] = loc_dest_id
        return {'value': result}
   
    
