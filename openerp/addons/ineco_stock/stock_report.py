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

#from lxml import etree
#from datetime import datetime
#from dateutil.relativedelta import relativedelta
import time
#from operator import itemgetter
#from itertools import groupby

from openerp.osv import fields, osv
#from openerp.tools.translate import _
#from openerp import netsvc
from openerp import tools
#from openerp.tools import float_compare
import openerp.addons.decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)

class query_stock_list_template(osv.osv):
    _name = "query.stock.list.template"
    _auto = False

    def init(self, cr):
        tools.drop_view_if_exists(cr, 'query_stock_list_template')
        cr.execute("""
        create or replace view query_stock_list_template as
select 
  pt.uom_id,
  move.*,
  coalesce((
  select sum(product_qty * case when uom_type = 'reference' then round(factor,0) when uom_type = 'bigger' then round(1/factor,0) else round(factor,0) end ) from stock_move
  left join product_uom on stock_move.product_uom = product_uom.id
                where location_id <> move.location_dest_id
                and location_dest_id = move.location_dest_id
                and product_id = move.product_id
                and
            case 
              when move.prodlot_id is not null then prodlot_id = move.prodlot_id 
              else prodlot_id is null
            end 
                and state in ('done')
  ),0) -
  coalesce((
  select sum(product_qty * case when uom_type = 'reference' then round(factor,0) when uom_type = 'bigger' then round(1/factor,0) else round(factor,0) end) from stock_move
  left join product_uom on stock_move.product_uom = product_uom.id
                where location_id = move.location_dest_id
                and location_dest_id <> move.location_dest_id
                and product_id = move.product_id
                and
            case 
              when move.prodlot_id is not null then prodlot_id = move.prodlot_id 
              else prodlot_id is null
            end 
                and state in ('done')
  ),0) as on_hand,
  coalesce((
  select sum(product_qty * case when uom_type = 'reference' then round(factor,0) when uom_type = 'bigger' then round(1/factor,0) else round(factor,0) end ) from stock_move
  left join product_uom on stock_move.product_uom = product_uom.id
                where location_id <> move.location_dest_id
                and location_dest_id = move.location_dest_id
                and product_id = move.product_id
                and
            case 
              when move.prodlot_id is not null then prodlot_id = move.prodlot_id 
              else prodlot_id is null
            end 
                and state in ('confirmed','waiting','assigned','done')
  ),0) -
  coalesce((
  select sum(product_qty * case when uom_type = 'reference' then round(factor,0) when uom_type = 'bigger' then round(1/factor,0) else round(factor,0) end) from stock_move
  left join product_uom on stock_move.product_uom = product_uom.id
                where location_id = move.location_dest_id
                and location_dest_id <> move.location_dest_id
                and product_id = move.product_id
                and
            case 
              when move.prodlot_id is not null then prodlot_id = move.prodlot_id 
              else prodlot_id is null
            end 
                and state in ('confirmed','waiting','assigned','done')
  ),0) as forecast  
from product_template pt
left join product_product pp on pp.product_tmpl_id = pt.id
left join product_uom pu on pt.uom_id = pu.id
left join 
  (select distinct 
    sm.product_id, 
    product_packaging, 
    prodlot_id, 
    sm.location_dest_id, 
    case when sl2.is_stock is null then 'OTHER' else 'STOCK' end as is_stock
   from stock_move sm
   left join stock_location sl1 on sm.location_id = sl1.id
   left join stock_location sl2 on sm.location_dest_id = sl2.id
   left join stock_production_lot spl on spl.id = sm.prodlot_id
   ) 
  as move on move.product_id = pp.id
order by default_code, prodlot_id, location_dest_id
        
        """)
    
class ineco_stock_list(osv.osv):
    _name = 'ineco.stock.list'
    _auto = False
    _columns = {
        'product_id': fields.many2one('product.product','Product',readonly=True),
        'product_packaging': fields.many2one('product.packaging','Packing', readonly=True),
        'prodlot_id': fields.many2one('stock.production.lot','Serial Number', readonly=True),
        'location_dest_id': fields.many2one('stock.location','Location',readonly=True),
        'is_stock': fields.char('Is Stock', size=32, readonly=True),
        'on_hand': fields.float('On Hand', digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True),
        'forecast': fields.float('Forecast', digits_compute=dp.get_precision('Product Unit of Measure'), readonly=True),
        'uom_id': fields.many2one('product.uom', 'UOM' ,readonly=True),
    }
    
    def init(self, cr):
        tools.drop_view_if_exists(cr, 'ineco_stock_list')
        cr.execute("""
create or replace view ineco_stock_list as

select 
  move.*,
  pt.uom_id,
  (coalesce((
  select sum(product_qty * case when uom_type = 'reference' then round(factor,0) when uom_type = 'bigger' then round(1/factor,0) else round(factor,0) end ) from stock_move
  left join product_uom on stock_move.product_uom = product_uom.id
                where location_id <> move.location_dest_id
                and location_dest_id = move.location_dest_id
                and product_id = move.product_id
                and
            case 
              when move.prodlot_id is not null then prodlot_id = move.prodlot_id 
              else prodlot_id is null
            end 
                and state in ('done')
  ),0) -
  coalesce((
  select sum(product_qty * case when uom_type = 'reference' then round(factor,0) when uom_type = 'bigger' then round(1/factor,0) else round(factor,0) end) from stock_move
  left join product_uom on stock_move.product_uom = product_uom.id
                where location_id = move.location_dest_id
                and location_dest_id <> move.location_dest_id
                and product_id = move.product_id
                and
            case 
              when move.prodlot_id is not null then prodlot_id = move.prodlot_id 
              else prodlot_id is null
            end 
                and state in ('done')
  ),0)) * pu.factor as on_hand,
  (coalesce((
  select sum(product_qty * case when uom_type = 'reference' then round(factor,0) when uom_type = 'bigger' then round(1/factor,0) else round(factor,0) end ) from stock_move
  left join product_uom on stock_move.product_uom = product_uom.id
                where location_id <> move.location_dest_id
                and location_dest_id = move.location_dest_id
                and product_id = move.product_id
                and
            case 
              when move.prodlot_id is not null then prodlot_id = move.prodlot_id 
              else prodlot_id is null
            end 
                and state in ('confirmed','waiting','assigned','done')
  ),0) -
  coalesce((
  select sum(product_qty * case when uom_type = 'reference' then round(factor,0) when uom_type = 'bigger' then round(1/factor,0) else round(factor,0) end) from stock_move
  left join product_uom on stock_move.product_uom = product_uom.id
                where location_id = move.location_dest_id
                and location_dest_id <> move.location_dest_id
                and product_id = move.product_id
                and
            case 
              when move.prodlot_id is not null then prodlot_id = move.prodlot_id 
              else prodlot_id is null
            end 
                and state in ('confirmed','waiting','assigned','done')
  ),0)) * pu.factor  as forecast
from product_template pt
left join product_product pp on pp.product_tmpl_id = pt.id
left join product_uom pu on pt.uom_id = pu.id
left join 
  (select distinct 
    min(sm.id) as id,
    sm.product_id, 
    product_packaging, 
    prodlot_id, 
    sm.location_dest_id, 
    case when sl2.is_stock is null then 'OTHER' else 'STOCK' end as is_stock
   from stock_move sm
   left join stock_location sl1 on sm.location_id = sl1.id
   left join stock_location sl2 on sm.location_dest_id = sl2.id
   left join stock_production_lot spl on spl.id = sm.prodlot_id
  group by
  sm.product_id, 
    product_packaging, 
    prodlot_id, 
    sm.location_dest_id, 
    case when sl2.is_stock is null then 'OTHER' else 'STOCK' end
      ) 
  as move on move.product_id = pp.id
order by default_code, prodlot_id, location_dest_id
            """)
    
class brc_report_001(osv.osv):
    _name = "brc.report.001"
    _description = "REP-001: Inventory Value Report"
    _auto = False
    _columns = {
        'recno': fields.integer('No.', readonly=True),
        'code': fields.char('Item', size=16, readonly=True),
        'name': fields.char('Name', size=64, readonly=True),
        'cost': fields.float('Cost', readonly=True),
        'uom': fields.char('UOM', size=16, readonly=True),
        'last_ship_date':  fields.char('Last Shipped', size=64, readonly=True),
        'qty_onhand': fields.float('On Hand', readonly=True),
        'total_amount': fields.float('Amount', readonly=True),
    }
    _order = 'recno'

    def init(self, cr):
        dbs = cr.dbname
        if dbs == 'BB100':
            loc_id = 17
        elif dbs == 'BS100':
            loc_id = 16
        elif dbs == 'BPRL':
            loc_id = 14
        else:
            loc_id = 17
        
        tools.drop_view_if_exists(cr, 'brc_report_001')
        cr.execute("""
        create or replace view brc_report_001 as
        SELECT pp.default_code as code,sm.product_id,row_number() over() as id,row_number() over() as recno,
        pp.name_template as name,pt.standard_price as cost,uom.name as uom,
        ( SELECT create_date::timestamp::date
          FROM stock_move
          WHERE product_id=sm.product_id AND location_dest_id=%s
          ORDER BY create_date DESC
          LIMIT 1) as last_ship_date,
        SUM( CASE WHEN sm.location_dest_id=%s THEN product_qty ELSE 0.0 END ) - 
        SUM( CASE WHEN sm.location_id=%s THEN product_qty ELSE 0.0 END ) as qty_onhand,
        ( SUM( CASE WHEN sm.location_dest_id=%s THEN product_qty ELSE 0.0 END ) - 
        SUM( CASE WHEN sm.location_id=%s THEN product_qty ELSE 0.0 END )) * pt.standard_price as total_amount
        FROM stock_move sm
        INNER JOIN product_product pp ON (sm.product_id=pp.id)
        INNER JOIN product_template pt ON (sm.product_id=pt.id)
        INNER JOIN product_uom uom ON (pt.uom_id=uom.id)
        GROUP BY pp.default_code,sm.product_id,pp.name_template,pt.standard_price,uom.name
        HAVING SUM( CASE WHEN sm.location_dest_id=%s THEN product_qty ELSE 0.0 END ) -
        SUM( CASE WHEN sm.location_id=%s THEN product_qty ELSE 0.0 END ) > 0
        ORDER BY pp.default_code
        """,(loc_id,loc_id,loc_id,loc_id,loc_id,loc_id,loc_id))

class brc_report_002(osv.osv):
    _name = "brc.report.002"
    _description = "REP-002: Inventory Value Report by AOS Type"
    _auto = False

    _columns = {
        'recno': fields.integer('No.', readonly=True),
        'aos': fields.char('AOS Type', size=8, readonly=True),
        'code': fields.char('Item', size=16, readonly=True),
        'name': fields.char('Name', size=64, readonly=True),
        'cost': fields.float('Cost', readonly=True),
        'uom': fields.char('UOM', size=16, readonly=True),
        'last_ship_date': fields.char('Last Shipped', size=64, readonly=True),
        'qty_onhand': fields.float('On Hand', readonly=True),
        'total_amount': fields.float('Amount', readonly=True),
    }
    _order = 'recno'

    def init(self, cr):
        dbs = cr.dbname
        if dbs == 'BB100':
            loc_id = 17
        elif dbs == 'BS100':
            loc_id = 16
        elif dbs == 'BPRL':
            loc_id = 14
        else:
            loc_id = 17
        
        tools.drop_view_if_exists(cr, 'brc_report_002')
        cr.execute("""
        create or replace view brc_report_002 as
        SELECT pp.default_code as code,sm.product_id,row_number() over() as id,row_number() over() as recno,
        ba.name as aos,pp.name_template as name,pt.standard_price as cost,uom.name as uom,
        ( SELECT create_date::timestamp::date
          FROM stock_move
          WHERE product_id=sm.product_id AND location_dest_id=%s
          ORDER BY create_date DESC
          LIMIT 1) as last_ship_date,
        SUM( CASE WHEN sm.location_dest_id=%s THEN product_qty ELSE 0.0 END ) - 
        SUM( CASE WHEN sm.location_id=%s THEN product_qty ELSE 0.0 END ) as qty_onhand,
        ( SUM( CASE WHEN sm.location_dest_id=%s THEN product_qty ELSE 0.0 END ) - 
        SUM( CASE WHEN sm.location_id=%s THEN product_qty ELSE 0.0 END )) * pt.standard_price as total_amount

        FROM stock_move sm

        INNER JOIN stock_picking sp ON (sm.picking_id=sp.id)
        INNER JOIN brc_aos ba ON (sp.aos_id=ba.id)
        INNER JOIN product_product pp ON (sm.product_id=pp.id)
        INNER JOIN product_template pt ON (sm.product_id=pt.id)
        INNER JOIN product_uom uom ON (pt.uom_id=uom.id)
        GROUP BY pp.default_code,sm.product_id,ba.name,pp.name_template,pt.standard_price,uom.name
        HAVING SUM( CASE WHEN sm.location_dest_id=%s THEN product_qty ELSE 0.0 END ) -
        SUM( CASE WHEN sm.location_id=%s THEN product_qty ELSE 0.0 END ) > 0
        ORDER BY ba.name,pp.default_code
        """,(loc_id,loc_id,loc_id,loc_id,loc_id,loc_id,loc_id))

class brc_report_003(osv.osv):
    _name = "brc.report.003"
    _description = "REP-003: Incoming Shipments by AOS / Source Document"
    _auto = False

    _columns = {
        'recno': fields.integer('No.', readonly=True),
        'aos': fields.char('AOS Type', size=1, readonly=True),
        'origin': fields.char('Source Document', size=1, readonly=True),
        'code': fields.char('Item', size=16, readonly=True),
        'name': fields.char('Name', size=64, readonly=True),
        'cost': fields.float('Cost', readonly=True),
        'uom': fields.char('UOM', size=16, readonly=True),
        'last_ship_date':  fields.char('Last Shipped', size=64, readonly=True),
        'qty_in': fields.float('Quantity', readonly=True),
        'total_amount': fields.float('Amount', readonly=True),
    }
    _order = 'recno'

    def init(self, cr):
        tools.drop_view_if_exists(cr, 'brc_report_003')
        cr.execute("""
        create or replace view brc_report_003 as
        SELECT pp.default_code as code,sm.product_id,row_number() over() as id,row_number() over() as recno,
        ba.name as aos,sm.origin,pp.name_template as name,pt.standard_price as cost,
        uom.name as uom,
        ( SELECT create_date::timestamp::date
          FROM stock_move
          WHERE product_id=sm.product_id AND location_id=8
          ORDER BY create_date DESC
          LIMIT 1) as last_ship_date,
        SUM( product_qty ) as qty_in, 
        SUM( product_qty ) * pt.standard_price as total_amount
        FROM stock_move sm
        INNER JOIN stock_picking sp ON (sm.picking_id=sp.id)
        INNER JOIN brc_aos ba ON (sp.aos_id=ba.id)
        INNER JOIN product_product pp ON (sm.product_id=pp.id)
        INNER JOIN product_template pt ON (sm.product_id=pt.id)
        INNER JOIN product_uom uom ON (pt.uom_id=uom.id)
        WHERE sm.location_id=8
        GROUP BY pp.default_code,sm.product_id,ba.name,sm.origin,pp.name_template,pt.standard_price,uom.name
        ORDER BY pp.default_code
        """)

class brc_report_004(osv.osv):
    _name = "brc.report.004"
    _description = "REP-004: Inventory Issued Report by Reason / Department"
    _auto = False

    _columns = {
        'recno': fields.integer('No.', readonly=True),
        'reason': fields.char('Reason', size=32, readonly=True),
        'department': fields.char('Department', size=64, readonly=True),
        'date_issued': fields.char('Date Issued', size=16, readonly=True),
        'origin': fields.char('Source Document', size=16, readonly=True),
        'code': fields.char('Item', size=16, readonly=True),
        'name': fields.char('Name', size=64, readonly=True),
        'cost': fields.float('Cost', readonly=True),
        'uom': fields.char('UOM', size=16, readonly=True),
        'qty_out': fields.float('Quantity', readonly=True),
        'total_amount': fields.float('Amount', readonly=True),
    }
    _order = 'recno'

    def init(self, cr):
        dbs = cr.dbname
        if dbs == 'BB100':
            loc_id = 17
        elif dbs == 'BS100':
            loc_id = 16
        elif dbs == 'BPRL':
            loc_id = 14
        else:
            loc_id = 17
        
        tools.drop_view_if_exists(cr, 'brc_report_004')
        cr.execute("""
        create or replace view brc_report_004 as
        SELECT br.name as reason, sl.name as department, sm.date_stock_card::timestamp::date as date_issued,
        sm.origin, pp.default_code as code, row_number() over() as id,
        pp.name_template as name, pt.standard_price as cost, uom.name as uom, row_number() over() as recno,
        SUM( product_qty ) as qty_out, 
        SUM( product_qty ) * pt.standard_price as total_amount
        FROM stock_move sm
        INNER JOIN brc_reason br ON (sm.reason_id=br.id)
        INNER JOIN stock_location sl ON (sm.location_dest_id=sl.id)
        INNER JOIN product_product pp ON (sm.product_id=pp.id)
        INNER JOIN product_template pt ON (sm.product_id=pt.id)
        INNER JOIN product_uom uom ON (pt.uom_id=uom.id)
        WHERE sm.location_id=%s
        GROUP BY br.name,sl.name,sm.date_stock_card::timestamp::date,sm.origin,
        pp.default_code,pp.name_template,pt.standard_price,uom.name
        ORDER BY br.name,sl.name,sm.date_stock_card::timestamp::date,sm.origin,pp.default_code
        """,(loc_id,))

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

