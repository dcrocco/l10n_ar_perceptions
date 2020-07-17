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
import mock


class AccountMove(models.Model):

    _inherit = 'account.move'

    perception_ids = fields.One2many(
        'account.invoice.perception',
        'move_id',
        string='Percepciones',
        copy=True
    )

    def _recompute_dynamic_lines(self, recompute_all_taxes=False, recompute_tax_base_amount=False):
        self.add_perceptions()
        res = super(AccountMove, self.with_context(no_zero=True))._recompute_dynamic_lines(
            recompute_all_taxes, recompute_tax_base_amount
        )
        # Borramos las move_lines que dieron 0 pero que no son de percepciones.
        non_balance_lines = self.line_ids.filtered(
            lambda x: x.balance == 0 and x.tax_line_id and x.tax_line_id.tax_group_id
            not in self.env['perception.perception'].get_perception_groups()
        )
        if non_balance_lines:
            self.line_ids -= non_balance_lines
        self.assign_perception_values()
        return res

    @api.onchange('perception_ids', 'invoice_line_ids', 'currency_id', 'currency_rate')
    def onchange_perception_ids(self):
        self.delete_perceptions()
        self._onchange_invoice_line_ids()
        self._recompute_dynamic_lines(recompute_tax_base_amount=True)

    @api.onchange('invoice_line_ids', 'currency_id', 'currency_rate')
    def onchange_set_perception_values(self):
        for perception in self.perception_ids:
            perception.base = round(sum(line.price_subtotal for line in self.invoice_line_ids.filtered(
                lambda x: x.product_id and x.product_id.perception_taxable
            )), 2)
            perception.onchange_aliquot()

    def assign_perception_values(self):
        for perception in self.perception_ids:
            tax = perception.perception_id.tax_id
            line_with_tax = self.line_ids.filtered(lambda x: x.tax_line_id == tax)
            amount = perception.amount
            vals = self._get_perception_value(amount)
            line_with_tax.update(vals)
        self._compute_invoice_taxes_by_group()

    def delete_perceptions(self):
        """ Para el caso que se borre una percepcion de la grilla de percepciones """
        taxes_invoices = self.invoice_line_ids.mapped('tax_ids')
        perception_taxes = self.perception_ids.mapped('perception_id').mapped('tax_id')
        taxes_to_delete = self.env['perception.perception'].search([
            ('tax_id', 'in', taxes_invoices.ids),
            ('tax_id', 'not in', perception_taxes.ids),
        ]).mapped('tax_id')
        if taxes_to_delete:
            self.invoice_line_ids.update({
                'tax_ids': [(3, perception_tax.id) for perception_tax in taxes_to_delete]
            })
            self.line_ids -= self.line_ids.filtered(lambda x: x.tax_line_id == taxes_to_delete)

    def add_perceptions(self):
        perception_taxes = self.perception_ids.mapped('perception_id').mapped('tax_id')
        self.invoice_line_ids.filtered(lambda x: x.product_id and x.product_id.perception_taxable).update({
            'tax_ids': [(4, perception_tax.id) for perception_tax in perception_taxes]
        })

    def _get_perception_value(self, amount):
        debit = credit = 0
        if self.type in ["in_invoice", "out_refund"]:
            debit = amount
        else:
            credit = amount

        move_currency = self.currency_id
        company_currency = self.company_currency_id
        if self.need_rate:
            move_currency = move_currency.with_context(
                fixed_rate=self.currency_rate,
                fixed_from_currency=move_currency,
                fixed_to_currency=company_currency
            )
        if move_currency and move_currency != company_currency:
            return {
                'amount_currency': amount if debit else -amount,
                'debit': move_currency._convert(
                    debit,
                    company_currency,
                    self.company_id,
                    self.invoice_date or fields.Date.context_today(self)
                ),
                'credit': move_currency._convert(
                    credit,
                    company_currency,
                    self.company_id,
                    self.invoice_date or fields.Date.context_today(self)
                )
            }

        return {'debit': debit, 'credit': credit, 'balance': amount if debit else -amount}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
