from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    discount_approval_threshold = fields.Float(
        string='Discount Limit Requiring Approval (%)',
        default=10.0,
        help='A sales order with a discount on any line item equal to or greater than this value must be approved before it can be confirmed.',
    )
