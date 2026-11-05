from odoo import api, fields, models


class ResellerCommissionLine(models.Model):
    _name = 'reseller.commission.line'
    _description = 'Reseller Commission Detail Line'
    _order = 'invoice_date, id'

    commission_id = fields.Many2one(
        'reseller.commission', required=True, ondelete='cascade', index=True)
    move_id = fields.Many2one(
        'account.move', string='Source Document', required=True, ondelete='restrict', index=True)
    invoice_date = fields.Date(related='move_id.invoice_date')
    invoice_origin = fields.Char(related='move_id.invoice_origin', string='Origin')
    move_type = fields.Selection(related='move_id.move_type', string='Type')
    company_id = fields.Many2one(related='commission_id.company_id', store=True)
    currency_id = fields.Many2one(related='commission_id.currency_id')
    amount = fields.Monetary(
        string='Net Amount', required=True, currency_field='currency_id',
        help='Untaxed amount in company currency; negative for credit notes.')

    _sql_constraints = [
        ('commission_move_uniq', 'unique(commission_id, move_id)',
         'A document can only appear once in a commission record.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        commissions = self.env['reseller.commission'].browse(
            [v['commission_id'] for v in vals_list if v.get('commission_id')])
        commissions._check_editable()
        return super().create(vals_list)

    def write(self, vals):
        self.commission_id._check_editable()
        return super().write(vals)

    def unlink(self):
        self.commission_id._check_editable()
        return super().unlink()
