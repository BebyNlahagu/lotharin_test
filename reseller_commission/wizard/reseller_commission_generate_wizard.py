from dateutil.relativedelta import relativedelta

from odoo import _, fields, models
from odoo.exceptions import AccessError


class ResellerCommissionGenerateWizard(models.TransientModel):
    _name = 'reseller.commission.generate.wizard'
    _description = 'Generate Reseller Commissions'

    date_from = fields.Date(
        string='Month', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1) - relativedelta(months=1),
        help='Any day inside the month to calculate.')
    reseller_ids = fields.Many2many(
        'res.partner', string='Resellers', domain=[('is_reseller', '=', True)],
        help='Leave empty to generate for all resellers.')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    def action_generate(self):
        self.ensure_one()

        user = self.env.user

        if not user.has_group('reseller_commission.group_commission_manager') or user.has_group('reseller_commission.group_commission_accountant'):
            raise AccessError(_("Only commission managers and accountants can generate commissions."))
        commissions = self.env['reseller.commission'].generate_for_period(
            self.date_from, resellers=self.reseller_ids or None, company=self.company_id)
        action = self.env['ir.actions.act_window']._for_xml_id(
            'reseller_commission.reseller_commission_action')
        action['domain'] = [('id', 'in', commissions.ids)]
        return action
