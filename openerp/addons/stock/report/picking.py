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

import time
from openerp.report import report_sxw
from openerp.osv import osv
from openerp import pooler

class picking(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(picking, self).__init__(cr, uid, name, context=context)
        self.price_total = 0.0
        self.grand_total = 0.0
        self.localcontext.update({
            'time': time,
            'process': self.process,
            'price_total': self._price_total,
            'grand_total': self._grand_total,
            'get_total_amount': self.get_total_amount,
            'get_product_desc': self.get_product_desc,
            'get_product_desc_only': self.get_product_desc_only,
            'get_product_code': self.get_product_code
        })

    def process(self, move_line):
        self.price_total = 0.0
        self.price_total += move_line.x_amount
        self.grand_total += move_line.x_amount
        data['price_total'] = self.price_total
        data['grand_total'] = self.grand_total
        return [data]

    def _price_total(self):
        return self.price_total

    def _grand_total(self):
        return self.grand_total

    def get_total_amount(self,move_line):
        return self.grand_total

    def get_product_desc(self,move_line):
        desc = move_line.product_id.name
        if move_line.product_id.default_code:
            desc = '[' + move_line.product_id.default_code + ']' + ' ' + desc
        return desc

    def get_product_desc_only(self,move_line):
        desc = move_line.product_id.name
        return desc

    def get_product_code(self,move_line):
        code = ''
        if move_line.product_id.default_code:
            code = '[' + move_line.product_id.default_code + ']'
        return code


report_sxw.report_sxw('report.stock.picking.list','stock.picking','addons/stock/report/picking.rml',parser=picking)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
