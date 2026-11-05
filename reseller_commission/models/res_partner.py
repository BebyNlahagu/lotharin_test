from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_reseller = fields.Boolean(
        string='Is a Reseller',
        tracking=True,
        help='Only partners flagged as reseller receive a monthly commission.',
    )

    reseller_commission_count = fields.Integer(
        compute='_compute_reseller_commission_count',
        groups='reseller_commission.group_commission_user')

    def _compute_reseller_commission_count(self):
        data = self.env['reseller.commission']._read_group(
            [('reseller_id', 'in', self.ids)], ['reseller_id'], ['__count'])
        counts = {partner.id: count for partner, count in data}
        for partner in self:
            partner.reseller_commission_count = counts.get(partner.id, 0)

    def action_view_reseller_commissions(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'reseller_commission.reseller_commission_action')
        action['domain'] = [('reseller_id', '=', self.id)]
        action['context'] = {'default_reseller_id': self.id}
        return action

    @api.constrains('is_reseller', 'parent_id')
    def _check_reseller_is_commercial_entity(self):
        """Invoices are grouped on the commercial entity, so the flag must sit there."""
        for partner in self:
            if partner.is_reseller and partner.parent_id:
                raise ValidationError(_(
                    "Flag the company itself as reseller, not one of its contacts (%s).",
                    partner.display_name))

    @api.constrains('is_reseller')
    def _check_reseller_flag_not_in_use(self):
        unflagged = self.filtered(lambda p: not p.is_reseller)
        if not unflagged:
            return
        in_use = self.env['reseller.commission'].sudo().search(
            [('reseller_id', 'in', unflagged.ids)], limit=1)
        if in_use:
            raise ValidationError(_(
                "%s already has commission records; it cannot be unflagged as reseller.",
                in_use.reseller_id.display_name))
