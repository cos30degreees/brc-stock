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

import math
import re

#from _common import rounding

from openerp import tools
from openerp.osv import osv, fields
from openerp.tools.translate import _

import openerp.addons.decimal_precision as dp

class product_uom_categ(osv.osv):
    _inherit = 'product.uom.categ'
    _columns = {
        'active': fields.boolean('Active', help="By unchecking the active field you can disable a unit of measure without deleting it."),
    }
    _defaults = {
        'active': True,
    }
    
class product_uom(osv.osv):
    _inherit = 'product.uom'
    _description = 'Product Unit of Measure'
    
    def name_get(self, cr, uid, ids, context=None):
        if isinstance(ids, (list, tuple)) and not len(ids):
            return []
        if isinstance(ids, (long, int)):
            ids = [ids]
        reads = self.read(cr, uid, ids, ['name','category_id','factor','uom_type'], context=context)
        res = []
        for record in reads:
            name = record['name']
            if record['category_id']:
                uom_categ = record['category_id']
                #print uom_categ
                if record['uom_type'] == 'reference':
                    name = name 
                elif record['uom_type'] == 'bigger':
                    name =  ('%.0f' % (1/record['factor'])) + ' ' +uom_categ[1] +' / '+name
                else:
                    name =  ('%.0f' % (record['factor'])) + ' ' +name+' / '+uom_categ[1] 
            res.append((record['id'], name))
        return res  

    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        if isinstance(ids, (list, tuple)) and not len(ids):
            return []
        if isinstance(ids, (long, int)):
            ids = [ids]
        res = {}
        for id in ids:
            data = self.browse(cr, uid, id)
            if data.uom_type == 'reference':
                res[id] = 1
            elif data.uom_type == 'bigger':
                res[id] = int ('%.0f' % (1/data.factor))
            else:
                res[id] = int('%.0f' % (data.factor))
        return res
        
    _columns = {
        'factor_name': fields.function(_name_get_fnc, type="integer", string='Factor'),                
    }  
    
class product_category(osv.osv):
    
    def _get_product_stock(self, cr, uid, ids, name, arg, context=None):
        res = {'product_count': False,
               'product_onhand':False,
               'product_forecast': False,
        }
        product_obj = self.pool.get('product.product')
        for id in ids:
            product_ids = product_obj.search(cr, uid, [('categ_id','=',id)])
            onhand = 0
            forecast = 0
            for product in product_obj.browse(cr, uid, product_ids):
                onhand += product.qty_available
                forecast += product.virtual_available
            res[id] = { 
                        'product_count': len(product_ids),
                        'product_onhand': onhand,
                        'product_forecast': forecast
            }
        return res 
    
    _inherit = 'product.category'
    _columns = {
        'product_count': fields.function(_get_product_stock, string='Product Count', type='integer', multi='inventory', readonly=True),                
        'product_onhand': fields.function(_get_product_stock, string='On Hand', type='float', multi='inventory', readonly=True),                
        'product_forecast': fields.function(_get_product_stock, string='Forecast', type='float', multi='inventory', readonly=True),                
    }
    
class product_product(osv.osv):
    _inherit = 'product.product'

    def _get_last_incoming_shipment_date(self, cr, uid, ids, name, arg, context=None):
        res = {}
        dbs = cr.dbname
        if dbs == 'BS100':
            dest_id = 16
        else:
            dest_id = 17

        for id in ids:
            cr.execute('select create_date::timestamp::date from stock_move where product_id=%s and location_dest_id=%s order by create_date desc limit 1',[id,dest_id])
            dict = cr.dictfetchone()
            if dict is None:
                res[id] = 'NA'
            else:
                res[id] = dict.get('create_date')
        return res

    _columns = {
        'internal_barcode': fields.char('Internal Barcode', size=64),
        'last_ship_date': fields.function(_get_last_incoming_shipment_date, string='Last Shipped', type='char', readonly=True),
    }
