# -*- encoding: utf-8 -*-
##############################################################################
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AccountInvoicePerception(models.Model):
    """
    Percepciones cargadas en invoices. Tener en cuenta que hay datos necesarios que se deberian tomar
    de la invoice: Cuit, Moneda, Fecha, Tipo (Proveedor/Cliente)
    """

    _inherit = 'account.document.tax'
    _name = 'account.invoice.perception'
    _description = 'Percepciones de factura'

    @api.onchange('perception_id')
    def onchange_perception_id(self):
        if self.perception_id:
            self.update({
                'name': self.perception_id.name,
                'jurisdiction': self.perception_id.jurisdiction,
                'amount': 0.0,
                'base': round(sum(line.price_subtotal for line in self.move_id.invoice_line_ids.filtered(
                    lambda x: x.product_id and x.product_id.perception_taxable
                )), 2)
            })
        else:
            self.update({
                'name': None,
                'jurisdiction': None,
                'amount': 0.0,
                'base': 0.0,
            })

    move_id = fields.Many2one('account.move', 'Documento', required=True, ondelete="cascade")
    currency_id = fields.Many2one(related='move_id.currency_id')
    date_invoice = fields.Date(string='Fecha de factura', related='move_id.invoice_date', store=True)
    date_account = fields.Date(string='Fecha contable', related='move_id.date', store=True)
    partner_id = fields.Many2one(string='Empresa', related='move_id.partner_id')
    perception_id = fields.Many2one(
        'perception.perception',
        'Percepcion',
        ondelete='restrict',
        required=True
    )
    jurisdiction = fields.Selection(
        [
            ('nacional', 'Nacional'),
            ('provincial', 'Provincial'),
            ('municipal', 'Municipal')
        ],
        string='Jurisdiccion',
        required=True,
    )

    @api.onchange('base', 'aliquot')
    def onchange_aliquot(self):
        self.amount = round(self.base * (self.aliquot/100), 2)

    @api.constrains('perception_id', 'move_id')
    def constraint_perception_id(self):
        for perception in self:
            if len(perception.move_id.perception_ids.filtered(
                    lambda x: x.perception_id == perception.perception_id)
            ) > 1:
                raise ValidationError("No puede haber mas de una percepcion similar en un mismo documento.")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
