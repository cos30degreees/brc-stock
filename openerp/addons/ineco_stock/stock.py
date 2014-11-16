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

# 2014-01-24    POP-1    Bug in stock date datetime

#from lxml import etree
#from datetime import datetime, timedelta
#from dateutil.relativedelta import relativedelta
import datetime
import time
#from operator import itemgetter
#from itertools import groupby

from openerp.osv import fields, osv
from openerp.tools.translate import _
#from openerp import netsvc
from openerp import tools
#from openerp.tools import float_compare
import openerp.addons.decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)

class stock_production_lot(osv.osv):
    
    _inherit = 'stock.production.lot'
    _columns = {
        'production_id': fields.many2one('mrp.production', 'Manufacturing Order'),
    }

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        reads = self.read(cr, uid, ids, ['name', 'prefix', 'ref'], context)
        res = []
        for record in reads:
            name = record['name']
            prefix = record['prefix']
            if prefix:
                name = prefix + '/' + name
            if record['ref']:
                name = '%s/%s' % (name, record['ref'])
            res.append((record['id'], name))
        return res
    
    def name_search(self, cr, uid, name, args=None, operator='ilike', context=None, limit=100):
        args = args or []
        ids = []
        if name:
            ids = self.search(cr, uid, [('ref', operator, name)] + args, limit=limit, context=context)
            if not ids:
                ids = self.search(cr, uid, [('name', operator, name)] + args, limit=limit, context=context)
        else:
            ids = self.search(cr, uid, args, limit=limit, context=context)
        return self.name_get(cr, uid, ids, context)
    

class stock_journal(osv.osv):
    _inherit = 'stock.journal'
    _columns = {
        'sequence_id': fields.many2one('ir.sequence', 'Sequence'),
        'shipping_type': fields.selection([('in','Getting Goods'),('internal','Internal'),('out','Sending Goods')],'Shipping Type'),
        'location_id': fields.many2one('stock.location','Default Location'),
        'location_dest_id': fields.many2one('stock.location','Default Destination Location'),
    }

class stock_picking_in(osv.osv):
    
    _inherit = 'stock.picking.in'
    
    def create(self, cr, user, vals, context=None):
        if ('name' not in vals) or (vals.get('name')=='/'):
            if ('stock_journal_id' in vals) and (vals.get('stock_journal_id')):
                stock_journal = self.pool.get('stock.journal').browse(cr, user, [vals.get('stock_journal_id')])[0]
                if stock_journal:
                    seq_obj_name = stock_journal.sequence_id.code
                else:
                    seq_obj_name =  'stock.picking.' + vals['type']
            elif ('stock_journal_id' in context): #make stock_journal_id in context
                stock_journal_ids = self.pool.get('stock.journal').search(cr, user, [('name','=',context['stock_journal_id'])])
                if stock_journal_ids:
                    stock_journal = self.pool.get('stock.journal').browse(cr, user, stock_journal_ids)[0]
                    if stock_journal:
                        vals['stock_journal_id'] = stock_journal.id
                        seq_obj_name = stock_journal.sequence_id.code
                    else:
                        seq_obj_name =  'stock.picking.' + vals['type']
            else:
                seq_obj_name =  'stock.picking.' + vals['type']
            vals['name'] = self.pool.get('ir.sequence').get(cr, user, seq_obj_name)
        new_id = super(stock_picking_in, self).create(cr, user, vals, context)
        return new_id 

    def set_stock_journal_id(self, cr, uid, ids, aos_id, context=None):
        # get stock_journal object
        args = []
        aos_obj = self.pool.get('brc.aos')
        aos_rec = aos_obj.browse(cr, uid, aos_id)
        j_name = aos_rec.name + '_1AFA'
        jnl_obj = self.pool.get('stock.journal')
        jnl_ids = jnl_obj.search(cr, uid, [('name','like',j_name)] + args, limit=1, context=context)
        jnl_rec = jnl_obj.browse(cr, uid, jnl_ids[0])

        return {'value': {'stock_journal_id': jnl_rec.id}}

    def _sum_x_amount_per_picking(self, cr, uid, ids, name, args, context=None):

        res = {}
        for m in self.browse(cr, uid, ids, context=context):
            picking_id = [m.id]
            cr.execute('select sum(x_amount) as sum_x_amount from stock_move where picking_id = %s', picking_id)
            # fetch value of sum_x_amount
            dict = cr.dictfetchone()
            res[m.id] = dict['sum_x_amount']
        return res

    _columns = {
        'aos_id': fields.many2one('brc.aos', 'AOS Type'),
        'reason_id': fields.many2one('brc.reason', 'Reason'),
        'x_amount_total': fields.function(_sum_x_amount_per_picking,type='float',string='Total Amount'),
    }

class brc_aos(osv.osv):
    _name = 'brc.aos'
    _description = "BRC AOS Type for grouping product"
    _table = "brc_aos"
    _columns = {
        'name': fields.char('AOS Type', size=8),
        'account_real': fields.char('Real Account', size=32),
        'account_temp': fields.char('Temp Account', size=32),
    }
brc_aos()

class brc_reason(osv.osv):
    _name = 'brc.reason'
    _description = "BRC reason for getting product from stock"
    _table = "brc_reason"
    _columns = {
        'name': fields.char('Reason', size=16),
        'account_code': fields.char('Reason-Account', size=32),
    }
brc_reason()
    
class stock_picking(osv.osv):
    
    _inherit = 'stock.picking'
    
    def create(self, cr, user, vals, context=None):
        if ('name' not in vals) or (vals.get('name')=='/'):
            if ('stock_journal_id' in vals) and (vals.get('stock_journal_id')):
                stock_journal = self.pool.get('stock.journal').browse(cr, user, [vals.get('stock_journal_id')])[0]
                if stock_journal:
                    seq_obj_name = stock_journal.sequence_id.code
                else:
                    seq_obj_name =  'stock.picking.' + vals['type']
            elif ('stock_journal_id' in context): #make stock_journal_id in context
                stock_journal_ids = self.pool.get('stock.journal').search(cr, user, [('name','=',context['stock_journal_id'])])
                if stock_journal_ids:
                    stock_journal = self.pool.get('stock.journal').browse(cr, user, stock_journal_ids)[0]
                    if stock_journal:
                        vals['stock_journal_id'] = stock_journal.id
                        seq_obj_name = stock_journal.sequence_id.code
                    else:
                        seq_obj_name =  'stock.picking.' + vals['type']
            else:
                seq_obj_name =  'stock.picking.' + vals['type']
            vals['name'] = self.pool.get('ir.sequence').get(cr, user, seq_obj_name)
        new_id = super(stock_picking, self).create(cr, user, vals, context)
        return new_id    

    def set_stock_journal_id(self, cr, uid, ids, aos_id, context=None):
        # get stock_journal object
        args = []
        aos_obj = self.pool.get('brc.aos')
        aos_rec = aos_obj.browse(cr, uid, aos_id)
        j_name = aos_rec.name + '_1AFA'
        jnl_obj = self.pool.get('stock.journal')
        jnl_ids = jnl_obj.search(cr, uid, [('name','like',j_name)] + args, limit=1, context=context)
        jnl_rec = jnl_obj.browse(cr, uid, jnl_ids[0])

        return {'value': {'stock_journal_id': jnl_rec.id}}

    def _sum_x_amount_per_picking(self, cr, uid, ids, name, args, context=None):

        res = {}
        for m in self.browse(cr, uid, ids, context=context):
            picking_id = [m.id]
            cr.execute('select sum(x_amount) as sum_x_amount from stock_move where picking_id = %s', picking_id)
            # fetch value of sum_x_amount
            dict = cr.dictfetchone()
            res[m.id] = dict['sum_x_amount']
        return res

    _columns = {
        'aos_id': fields.many2one('brc.aos', 'AOS Type'),
        'reason_id': fields.many2one('brc.reason', 'Reason'),
        'x_amount_total': fields.function(_sum_x_amount_per_picking,type='float',string='Total Amount'),
    }
    
class stock_picking_out(osv.osv):
    
    _inherit = 'stock.picking.out'

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        picking_obj = self.browse(cr, uid, id, context=context)
        move_obj=self.pool.get('stock.move')
        if ('name' not in default) or (picking_obj.name=='/'):
            if picking_obj.stock_journal_id:
                seq_obj_name =picking_obj.stock_journal_id.sequence_id.code
            else:
                seq_obj_name =  'stock.picking.' + picking_obj.type
            default['name'] = self.pool.get('ir.sequence').get(cr, uid, seq_obj_name)
            default['origin'] = ''
            default['backorder_id'] = False
        if 'invoice_state' not in default and picking_obj.invoice_state == 'invoiced':
            default['invoice_state'] = '2binvoiced'
        res=super(stock_picking_out, self).copy(cr, uid, id, default, context)
        if res:
            picking_obj = self.browse(cr, uid, res, context=context)
            for move in picking_obj.move_lines:
                move_obj.write(cr, uid, [move.id], {'tracking_id': False,'prodlot_id':False, 'move_history_ids2': [(6, 0, [])], 'move_history_ids': [(6, 0, [])]})
        return res
    
    def create(self, cr, user, vals, context=None):
        if ('name' not in vals) or (vals.get('name')=='/'):
            if ('stock_journal_id' in vals) and (vals.get('stock_journal_id')):
                stock_journal = self.pool.get('stock.journal').browse(cr, user, [vals.get('stock_journal_id')])[0]
                if stock_journal:
                    seq_obj_name = stock_journal.sequence_id.code
                else:
                    seq_obj_name =  'stock.picking.' + vals['type']
            elif ('stock_journal_id' in context): #make stock_journal_id in context
                stock_journal_ids = self.pool.get('stock.journal').search(cr, user, [('name','=',context['stock_journal_id'])])
                if stock_journal_ids:
                    stock_journal = self.pool.get('stock.journal').browse(cr, user, stock_journal_ids)[0]
                    if stock_journal:
                        vals['stock_journal_id'] = stock_journal.id
                        seq_obj_name = stock_journal.sequence_id.code
                    else:
                        seq_obj_name =  'stock.picking.' + vals['type']
            else:
                seq_obj_name =  'stock.picking.' + vals['type']
            vals['name'] = self.pool.get('ir.sequence').get(cr, user, seq_obj_name)
        new_id = super(stock_picking_out, self).create(cr, user, vals, context)
        return new_id

class stock_move(osv.osv):  
    
    def _get_inventory(self, cr, uid, ids, name, arg, context=None):
        #1 = Receive
        #2 = Transfer
        #3 = Issue
        res = {}
        uom_obj = self.pool.get('product.uom')
        context['raise-exception'] = False
        for data in self.browse(cr, uid, ids):
            #Finding Before Qty
            before_ids = self.search(cr, uid, [('date_expected','<=',data.date_expected),('id','!=',data.id),('state','=','done'),('product_id','=',data.product_id.id)], order='date_expected desc, id', limit=1)
            before_qty = 0.0
            next_qty = 0.0
            if before_ids:
                before_obj = self.browse(cr, uid, before_ids)[0]
                before_qty = before_obj.next or 0.0
            converted_qty = uom_obj._compute_qty(cr, uid, data.product_uom.id, data.product_qty, data.product_id.uom_id.id)
            res[data.id] = {
                'inventory_type': False,
                'receive': 0.0,
                'issue': 0.0,
                'transfer': 0.0,
                'before': 0.0,
                'next': 0.0,
            }
            if data.location_id and data.location_dest_id:
                if data.location_id.is_stock and data.location_dest_id.is_stock:
                    res[data.id] = {
                        'inventory_type': 2,
                        'receive': 0.0,
                        'issue': 0.0,
                        'transfer': converted_qty,
                        'before': before_qty,
                        'next': before_qty,
                    }
                elif data.location_id.is_stock and not data.location_dest_id.is_stock:
                    res[data.id] = {
                        'inventory_type': 3,
                        'receive': 0.0 ,
                        'issue': converted_qty,
                        'transfer': 0.0 ,
                        'before': before_qty,
                        'next': before_qty - converted_qty,
                    }
                elif not data.location_id.is_stock and data.location_dest_id.is_stock:
                    res[data.id] = {
                        'inventory_type': 1,
                        'receive': converted_qty,
                        'issue': 0.0,
                        'transfer': 0.0,
                        'before': before_qty,
                        'next': converted_qty + before_qty,
                    }
                else:
                    res[data.id] = {
                        'inventory_type': 2,
                        'receive': 0.0,
                        'issue': 0.0,
                        'transfer': converted_qty,
                        'before': before_qty,
                        'next': before_qty,
                    }
        context['raise-exception'] = True
        return res    
    
    _inherit = 'stock.move'
    _columns = {
        'date_stock_card': fields.datetime('Date Stock Card'),
        'x_amount': fields.float('Amount'),
        'reason_id': fields.many2one('brc.reason', 'Reason'),
        'on_hand': fields.integer('On Hand'),

        
#         'inventory_type': fields.function(_get_inventory, string='Inventory Type', type='integer',
#             store={
#                 'stock.move': (lambda self, cr, uid, ids, c={}: ids, [], 10),
#             }, multi="inventory", readonly=True),
#         'receive': fields.function(_get_inventory, digits_compute=dp.get_precision('Product Unit of Measure'), 
#             string='Receive', type='float',
#             store={
#                 'stock.move': (lambda self, cr, uid, ids, c={}: ids, [], 10),
#             }, multi="inventory", readonly=True),    
#         'transfer': fields.function(_get_inventory, digits_compute=dp.get_precision('Product Unit of Measure'), 
#             string='Transfer', type='float',
#             store={
#                 'stock.move': (lambda self, cr, uid, ids, c={}: ids, [], 10),
#             }, multi="inventory", readonly=True),    
#         'issue': fields.function(_get_inventory, digits_compute=dp.get_precision('Product Unit of Measure'), 
#             string='Issue', type='float',
#             store={
#                 'stock.move': (lambda self, cr, uid, ids, c={}: ids, [], 10),
#             }, multi="inventory", readonly=True),    
#         'before': fields.function(_get_inventory, digits_compute=dp.get_precision('Product Unit of Measure'), 
#             string='Before Qty', type='float',
#             store={
#                 'stock.move': (lambda self, cr, uid, ids, c={}: ids, [], 10),
#             }, multi="inventory", readonly=True),    
#         'next': fields.function(_get_inventory, digits_compute=dp.get_precision('Product Unit of Measure'), 
#             string='Next Qty', type='float',
#             store={
#                 'stock.move': (lambda self, cr, uid, ids, c={}: ids, [], 10),
#             }, multi="inventory", readonly=True),    
    }
    _defaults = {
        'date_stock_card': False,
        'x_amount': 0.0,
    }
    
    def create(self, cr, user, vals, context=None):
        if ('picking_id' in vals) and ('location_id' in vals) and ('location_dest_id' in vals):
            picking_obj = self.pool.get('stock.picking').browse(cr, user, vals['picking_id'])
            org_location_id = vals['location_id']
            org_location_dest_id = vals['location_dest_id']
            stock_journal_obj = False
            if picking_obj:
                stock_journal_obj = picking_obj.stock_journal_id
                if stock_journal_obj.location_id:
                    org_location_id = stock_journal_obj.location_id.id
                if stock_journal_obj.location_dest_id:
                    org_location_dest_id = stock_journal_obj.location_dest_id.id
            vals['location_id'] = org_location_id
            vals['location_dest_id'] = org_location_dest_id
            #print vals['picking_id']
        new_id = super(stock_move, self).create(cr, user, vals, context)
        return new_id
    
    def action_done(self, cr, uid, ids, context=None):
        result = super(stock_move, self).action_done(cr, uid, ids, context=context)
        #POP-01
        i = 1
        for data in self.browse(cr, uid, ids):
            newtime = datetime.datetime.now() + datetime.timedelta(0,i)
            i = i + 1
            data.write({'date_stock_card': newtime.strftime('%Y-%m-%d %H:%M:%S')})
        return result

    def action_cancel(self, cr, uid, ids, context=None):
        result = super(stock_move, self).action_cancel(cr, uid, ids, context=context)
        for data in self.browse(cr, uid, ids):
            data.write({'date_stock_card': False})
        return result    

    def onchange_quantity(self, cr, uid, ids, product_id, product_qty,
                          product_uom, product_uos):
        result = super(stock_move, self).onchange_quantity(cr, uid, ids, product_id, product_qty,
                          product_uom, product_uos)

        #This is override method of ORIGINAL onchange_quantity and Worked!! Dr.Titasak 20141026

        #get standard_price from product_template via product_id
        prod_id = int(product_id)
        cr.execute('select standard_price from product_template where id = %s', [prod_id])
        dict = cr.dictfetchone()
        if dict is None:
            standard_price = 0.00
        else:
            standard_price = dict.get('standard_price')

        total_amount = product_qty * standard_price

        # get quantity on hand if product_id
        on_hand = 0
        if product_id:
            dbs = cr.dbname
            if dbs == 'BS100':
                stock_location = 16
            else:
                stock_location = 17

            # get incoming quantity for product_id to stock_location
            sql = "select sum(product_qty) from stock_move where product_id = %s and state in ('done') and location_dest_id = %s" % (product_id,stock_location)
            cr.execute(sql)
            in_stock = cr.fetchall()[0][0] or 0

            # get outgoing quantity for product_id to stock_location
            sql = "select sum(product_qty) from stock_move where product_id = %s and state in ('done') and location_id = %s" % (product_id,stock_location)
            cr.execute(sql)
            out_stock = cr.fetchall()[0][0] or 0

            on_hand = in_stock - out_stock

            if on_hand == 0:
                msg_warn = 'ขออภัย... ไม่มีสินค้ารายการนี้ในสต็อค...'

                result = {
                    'warning': {
                        'title': _('คำเตือน'),
                        'message':  _(msg_warn)
                    },
                    'value': {
                        'product_qty': 0,
                        'product_uos_qty': 0,
                        'x_amount': 0.0,
                        'on_hand': 0.0
                    }
                }

            elif product_qty > on_hand:
                total_amount = 1 * standard_price

                msg_warn = 'ท่านไม่สามารถเบิกสินค้าเกินจำนวนที่มีในสต็อค\n'
                msg_warn += 'จำนวนคงเหลือ: %s จำนวนที่เบิก: %s' % (on_hand, product_qty) 

                result = {
                    'warning': {
                        'title': _('คำเตือน'),
                        'message':  _(msg_warn)
                    },
                    'value': {
                        'product_qty': 1,
                        'x_amount': total_amount,
                        'on_hand': on_hand
                    }
                }

            else:
                result['value'].update({
                    'x_amount': total_amount,
                'on_hand': on_hand
            })

        return result

class stock_location(osv.osv):

    def _get_warehouse(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('stock.warehouse').browse(cr, uid, ids, context=context):
            result[line.lot_stock_id.id] = True
        return result.keys()
    
    def _check_location_stock(self, cr, uid, ids, name, arg, context=None):
        res = {}
        stock_obj = self.pool.get('stock.location')
        warehouse_obj = self.pool.get('stock.warehouse')
        location_ids = {}
        warehouse_all_ids = warehouse_obj.search(cr, uid, [])
        
        for warehouse in self.pool.get('stock.warehouse').browse(cr, uid, warehouse_all_ids):
            location_ids[warehouse.lot_stock_id.id] = True
        location_ids = location_ids.keys()      
        location_ids = stock_obj.search(cr, uid, [('location_id','child_of',location_ids)])
        for data in self.browse(cr, uid, ids):
            if data.id in location_ids:
                res[data.id] = True
            else:
                res[data.id] = False
        return res
        
    _inherit = 'stock.location'
    _columns = {
        'is_stock': fields.function(_check_location_stock, string='Stock Location', type='boolean',
            store={
                'stock.location': (lambda self, cr, uid, ids, c={}: ids, [], 10),
                'stock.warehouse': (_get_warehouse, [], 10),
            }, readonly=True), 
    } 

class ineco_stock_card(osv.osv):
    _name = 'ineco.stock.card'
    _description = "Ineco Stock Card"
    _auto = False
    _columns = {
        'date_expected': fields.datetime('Date Expected', readonly=True),
        'date_stock_card': fields.datetime('Date Stock', readonly=True),
        'product_id': fields.many2one('product.product','Product', readonly=True),
        'product_uom': fields.many2one('product.uom','UOM',readonly=True),
        'location_id': fields.many2one('stock.location','Source Location',readonly=True),
        'location_dest_id': fields.many2one('stock.location','Destination Location',readonly=True),
        'partner_id': fields.many2one('res.partner','Partner',readonly=True),
        'purchase_line_id': fields.many2one('purchase.order.line','Purchase Line',readonly=True),
        'sale_line_id': fields.many2one('sale.order.line','Sale Line',readonly=True),
        'picking_id': fields.many2one('stock.picking','Picking',readonly=True),
        'origin': fields.related('picking_id','origin',type='char',string='เลขที่เอกสาร', relation='stock.picking',readonly=True),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True),
        'state': fields.selection([('draft', 'New'),
                                   ('cancel', 'Cancelled'),
                                   ('waiting', 'Waiting Another Move'),
                                   ('confirmed', 'Waiting Availability'),
                                   ('assigned', 'Available'),
                                   ('done', 'Done'),
                                   ], 'Status', readonly=True, select=True),
        'before': fields.float('Before', digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True),
        'receive': fields.float('Receive', digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True),
        'issue': fields.float('Issue', digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True),
        'transfer': fields.float('Transfer', digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True),
        'next': fields.float('Next', digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True),   
    }
    _order = 'date_expected, id'

    def init(self, cr):
        tools.drop_view_if_exists(cr, 'ineco_stock_card')
        cr.execute("""
create or replace view ineco_stock_card as
select 
  sm.id,
  sm.date_expected,
  sm.date_stock_card,
  sm.product_id,
  sm.product_uom,
  sm.location_id,
  sm.location_dest_id,
  sm.partner_id,
  sm.purchase_line_id,
  sm.sale_line_id,
  sm.picking_id,
  sm.origin,
  sm.product_qty,
  sm.state,
  case
    when (sl1.is_stock isnull or sl1.is_stock = false) and sl2.is_stock = true and sm.state = 'done' then round(sm.product_qty/pu.factor,2)     
    else 0.00
  end as receive,
  case
    when sl1.is_stock = true and (sl2.is_stock isnull or sl2.is_stock = false) and sm.state = 'done' then round(sm.product_qty/pu.factor,2)     
    else 0.00
  end as issue,
  case
    when sl1.is_stock = sl2.is_stock and sm.state = 'done' then round(sm.product_qty/pu.factor,2)     
    else 0.00
  end as transfer,
    (
        select coalesce(sum(receive) - sum(issue), 0.00) as balance
        from 
        (
            select 
              smm.id,
              smm.product_id,
              smm.date_stock_card,
              case
                when (sl1.is_stock isnull or sl1.is_stock = false) and sl2.is_stock = true and smm.state = 'done' then round(smm.product_qty/pu.factor,2)     
                else 0.00
              end as receive,
              case
                when sl1.is_stock = true and (sl2.is_stock isnull or sl2.is_stock = false) and smm.state = 'done' then round(smm.product_qty/pu.factor,2)     
                else 0.00
              end as issue,
              case
                when sl1.is_stock = sl2.is_stock and smm.state = 'done' then round(smm.product_qty/pu.factor,2)     
                else 0.00
              end as transfer
            from stock_move smm
            left join stock_location sl1 on sl1.id = smm.location_id
            left join stock_location sl2 on sl2.id = smm.location_dest_id
            left join product_uom pu on pu.id = smm.product_uom
            where smm.product_id = sm.product_id
        ) as subquery
        where subquery.product_id = sm.product_id 
              and subquery.date_stock_card < sm.date_stock_card  
              --and subquery.id < sm.id
    ) as before,
  case
    when sl1.is_stock = sl2.is_stock and sm.state = 'done' then 
    (
        select coalesce(sum(receive) - sum(issue),0.00) as balance
        from 
        (
            select 
              smm.id,
              smm.product_id,
              smm.date_stock_card,
              case
                when (sl1.is_stock isnull or sl1.is_stock = false) and sl2.is_stock = true and smm.state = 'done' then round(smm.product_qty/pu.factor,2)     
                else 0.00
              end as receive,
              case
                when sl1.is_stock = true and (sl2.is_stock isnull or sl2.is_stock = false) and smm.state = 'done' then round(smm.product_qty/pu.factor,2)     
                else 0.00
              end as issue,
              case
                when sl1.is_stock = sl2.is_stock and smm.state = 'done' then round(smm.product_qty/pu.factor,2)     
                else 0.00
              end as transfer
        
            from stock_move smm
            left join stock_location sl1 on sl1.id = smm.location_id
            left join stock_location sl2 on sl2.id = smm.location_dest_id
            left join product_uom pu on pu.id = smm.product_uom
            where smm.product_id = sm.product_id
            order by
                smm.product_id, smm.date_stock_card, smm.id
        ) as subquery
        where subquery.product_id = sm.product_id 
              and subquery.date_stock_card < sm.date_stock_card 
              --and subquery.id < sm.id 
    )    
    when sl1.is_stock = true and sl2.is_stock isnull and sm.state = 'done' then 
    (
        select coalesce(sum(receive) - sum(issue),0.00) as balance
        from 
        (
            select 
              smm.id,
              smm.product_id,
              smm.date_stock_card,
              case
                when (sl1.is_stock isnull or sl1.is_stock = false) and sl2.is_stock = true and smm.state = 'done' then round(smm.product_qty/pu.factor,2)     
                else 0.00
              end as receive,
              case
                when sl1.is_stock = true and (sl2.is_stock isnull or sl2.is_stock = false) and smm.state = 'done' then round(smm.product_qty/pu.factor,2)     
                else 0.00
              end as issue,
              case
                when sl1.is_stock = sl2.is_stock and smm.state = 'done' then round(smm.product_qty/pu.factor,2)     
                else 0.00
              end as transfer
            from stock_move smm
            left join stock_location sl1 on sl1.id = smm.location_id
            left join stock_location sl2 on sl2.id = smm.location_dest_id
            left join product_uom pu on pu.id = smm.product_uom
            where smm.product_id = sm.product_id
            order by
                smm.product_id, smm.date_stock_card, smm.id
        ) as subquery
        where subquery.product_id = sm.product_id 
              and subquery.date_stock_card < sm.date_stock_card 
              --and subquery.id < sm.id 
    ) - round(sm.product_qty/pu.factor,2)      
    when (sl1.is_stock isnull or sl1.is_stock = 'f') and sl2.is_stock = true and sm.state = 'done' then 
    (
        select coalesce(sum(receive) - sum(issue),0.00) as balance
        from 
        (
            select 
              smm.id,
              smm.product_id,
              smm.date_stock_card,
              case
                when (sl1.is_stock isnull or sl1.is_stock =false) and sl2.is_stock = true and smm.state = 'done' then round(smm.product_qty/pu.factor,2)     
                else 0.00
              end as receive,
              case
                when sl1.is_stock = true and (sl2.is_stock isnull or sl2.is_stock = false) and smm.state = 'done' then round(smm.product_qty/pu.factor,2)     
                else 0.00
              end as issue,
              case
                when sl1.is_stock = sl2.is_stock and smm.state = 'done' then round(smm.product_qty/pu.factor,2)     
                else 0.00
              end as transfer
            from stock_move smm
            left join stock_location sl1 on sl1.id = smm.location_id
            left join stock_location sl2 on sl2.id = smm.location_dest_id
            left join product_uom pu on pu.id = smm.product_uom
            where smm.product_id = sm.product_id
            order by
                smm.product_id, smm.date_stock_card, smm.id
        ) as subquery
        where subquery.product_id = sm.product_id 
              and subquery.date_stock_card < sm.date_stock_card
              --and subquery.id < sm.id 
    ) +  round(sm.product_qty/pu.factor,2)
    else 

    (
        select coalesce(sum(receive) - sum(issue), 0.00) as balance
        from 
        (
            select 
              smm.id,
              smm.product_id,
              smm.date_stock_card,
              case
                when (sl1.is_stock isnull or sl1.is_stock = false) and sl2.is_stock = true and smm.state = 'done' then round(smm.product_qty/pu.factor,2)     
                else 0.00
              end as receive,
              case
                when sl1.is_stock = true and (sl2.is_stock isnull or sl2.is_stock = false) and smm.state = 'done' then round(smm.product_qty/pu.factor,2)     
                else 0.00
              end as issue,
              case
                when sl1.is_stock = sl2.is_stock and smm.state = 'done' then round(smm.product_qty/pu.factor,2)     
                else 0.00
              end as transfer
            from stock_move smm
            left join stock_location sl1 on sl1.id = smm.location_id
            left join stock_location sl2 on sl2.id = smm.location_dest_id
            left join product_uom pu on pu.id = smm.product_uom
            where smm.product_id = sm.product_id
        ) as subquery
        where subquery.product_id = sm.product_id 
              and subquery.date_stock_card < sm.date_stock_card  
              --and subquery.id < sm.id
    )

  end as next
from stock_move sm
left join stock_location sl1 on sl1.id = sm.location_id
left join stock_location sl2 on sl2.id = sm.location_dest_id
left join product_uom pu on pu.id = sm.product_uom
where
  date_stock_card is not null 
order by
  sm.product_id, sm.date_stock_card, sm.id            
          """)
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
