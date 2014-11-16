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

import psycopg2
import psycopg2.extras
#from datetime import datetime
#from dateutil.relativedelta import relativedelta
#import time
#from operator import itemgetter
#from itertools import groupby

from openerp.osv import fields, osv
#from openerp.tools.translate import _
#from openerp import netsvc
#from openerp import tools
#from openerp.tools import float_compare, DEFAULT_SERVER_DATETIME_FORMAT
#import openerp.addons.decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)

class ineco_adempiere_server(osv.osv):
    _name = "ineco.adempiere.server"
    _description = "Adempiere Server Configuration"
    _columns = {
        'name': fields.char('Server IP', size=32, required=True, selected=True),
        'user': fields.char('User Name', size=32, required=True, selected=True),
        'dbname': fields.char('Database Name', size=64, required=True,),
        'password': fields.char('Password', size=32, required=True,),
        'active': fields.boolean('Active')
    }
    _defaults = {
        'active': True
    }
#     _sql_constraints = [
#         ('name_dbname_user_uniq', 'unique(name, dbname, user)', 'Server, DB and User must be unique'),
#     ]
    def action_sync_uom(self, cr, uid, ids, context=None):
        """ Sync Product UOM
        @return:
        """
        
        for row in self.browse(cr, uid, ids):
            conn_string = "host='%s' dbname='%s' user='%s' password='%s'"
            conn = psycopg2.connect(conn_string % (row.name, row.dbname, row.user, row.password))
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
      
            _sql_product_uom = """
                select name, 'Unit' as category_id, 1 as factor from adempiere.c_uom where name is not null order by name
            """
            if context is None:
                context = {}
            cursor.execute(_sql_product_uom)
            for line in cursor.fetchall():
                if line and line['name']:
                    data_ids = self.pool.get('product.uom').search(cr, uid, [('name','=',line['name'])])
                    if not data_ids:
                        data = {
                            'name': line['name'],
                            'category_id': 1,
                            'factor': 1.0, 
                        }
                        self.pool.get('product.uom').create(cr, uid, data)
        return True

    def action_sync_category(self, cr, uid, ids, context=None):
        """ Sync Product Category
        @return:
        """
        for row in self.browse(cr, uid, ids):
            conn_string = "host='%s' dbname='%s' user='%s' password='%s'"
            conn = psycopg2.connect(conn_string % (row.name, row.dbname, row.user, row.password))
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            _sql_product_category = """
                select distinct name from adempiere.m_product_category order by name
            """
            if context is None:
                context = {}
                
            cursor.execute(_sql_product_category)
            for line in cursor.fetchall():
                if line and line['name']:
                    data_ids = self.pool.get('product.category').search(cr, uid, [('name','=',line['name'])])
                    if not data_ids:
                        data = {
                            'name': line['name'],
                        }
                        self.pool.get('product.category').create(cr, uid, data)
        return True

    def action_sync_product(self, cr, uid, ids, context=None):
        """ Sync Product
        @return:
        """
        _sql_product = """
            select p.value as default_code, p.name , u.name as uom_id, c.name as categ_id
            from adempiere.m_product p
            left join adempiere.c_uom u on p.c_uom_id = u.c_uom_id
            left join adempiere.m_product_category c on p.m_product_category_id = c.m_product_category_id
        """        
        
        if context is None:
            context = {}

        for row in self.browse(cr, uid, ids):
            conn_string = "host='%s' dbname='%s' user='%s' password='%s'"
            conn = psycopg2.connect(conn_string % (row.name, row.dbname, row.user, row.password))
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            
            cursor.execute(_sql_product)
            for line in cursor.fetchall():
                if line and line['uom_id']:
                    uom_ids = self.pool.get('product.uom').search(cr, uid, [('name','=',line['uom_id'])])
                if line and line['categ_id']:
                    category_ids = self.pool.get('product.category').search(cr, uid, [('name','=',line['categ_id'])])
                if line and line['name']:
                    data_ids = self.pool.get('product.product').search(cr, uid, [('name','=',line['name'])])
                    if not data_ids:
                        data = {
                            'name': line['name'],
                            'uom_id': uom_ids and uom_ids[0] or False,
                            'default_code': line['default_code'],
                            'categ_id': category_ids and category_ids[0] or False,
                        }
                        self.pool.get('product.product').create(cr, uid, data)
                        cr.commit()
        return True
    
    def action_sync_account(self, cr, uid, ids, context=None):
        """ Sync Account
        @return:
        """
        for row in self.browse(cr, uid, ids):
            conn_string = "host='%s' dbname='%s' user='%s' password='%s'"
            conn = psycopg2.connect(conn_string % (row.name, row.dbname, row.user, row.password))
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            _sql_account = """
                select value as code, name from adempiere.c_elementvalue order by value
            """
            if context is None:
                context = {}
                
            cursor.execute(_sql_account)
            for line in cursor.fetchall():
                if line and line['code'] and line['name'] :
                    data_ids = self.pool.get('account.account').search(cr, uid, [('code','=',line['code'])])
                    if not data_ids:
                        data = {
                            'code': line['code'],
                            'name': line['name'],
                            'user_type': 18,
                        }
                        self.pool.get('account.account').create(cr, uid, data)
        return True

