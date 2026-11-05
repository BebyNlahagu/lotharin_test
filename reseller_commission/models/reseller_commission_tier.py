from odoo import api, fields, models


class ResellerCommissionTier(models.Model):
    _name = 'reseller.commission.tier'
    _description = 'Reseller Commission Tier'
    _order = 'company_id, min_amount'

    name = fields.Char(required=True, translate=True)
    min_amount = fields.Monetary(
        string='From Monthly Sales',
        required=True,
        currency_field='currency_id',
        help='Lower bound (inclusive) of monthly net sales for this tier. '
             'A reseller falls in the tier with the highest bound not above their total.',
    )
    rate = fields.Float(string='Commission Rate (%)', digits=(5, 2), required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')

    _sql_constraints = [
        ('min_amount_company_uniq', 'unique(company_id, min_amount)',
         'Two tiers of the same company cannot start at the same amount.'),
        ('min_amount_positive', 'CHECK(min_amount >= 0)',
         'The lower bound of a tier cannot be negative.'),
        ('rate_range', 'CHECK(rate >= 0 AND rate <= 100)',
         'The commission rate must be between 0 and 100 percent.'),
    ]

    @api.model
    def _get_tier_for_amount(self, amount, company):
        """Highest active tier whose lower bound is <= amount (empty if none)."""
        return self.search([
            ('company_id', '=', company.id),
            ('min_amount', '<=', amount),
        ], order='min_amount desc', limit=1)
