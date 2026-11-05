from odoo import api, fields, models, _
from odoo.exceptions import UserError

APPROVER_GROUP = 'sale_discount_approval.group_discount_approver'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    approval_state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('to_approve', 'Waiting for Approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Discount Approval Status',
        default='draft', copy=False, tracking=True,
    )
    max_discount = fields.Float(
        string='Highest Discount (%)', compute='_compute_need_discount_approval')
    need_discount_approval = fields.Boolean(
        compute='_compute_need_discount_approval')
    approved_by_id = fields.Many2one('res.users', string='Approved By', copy=False, readonly=True)
    approval_date = fields.Datetime(string='Approval Date', copy=False, readonly=True)

    @api.depends('order_line.discount', 'company_id.discount_approval_threshold')
    def _compute_need_discount_approval(self):
        for order in self:
            discounts = order.order_line.filtered(lambda l: not l.display_type).mapped('discount')
            max_disc = max(discounts or [0.0])
            order.max_discount = max_disc
            threshold = order.company_id.discount_approval_threshold
            order.need_discount_approval = threshold > 0 and max_disc >= threshold

    # ------------------------------------------------------------------
    def _is_discount_approver(self):
        return self.env.user.has_group(APPROVER_GROUP)

    def action_request_approval(self):
        for order in self:
            if not order.need_discount_approval:
                raise UserError(_('Order %s does not require discount approval.', order.name))
            order.approval_state = 'to_approve'
            for user in self.env.ref(APPROVER_GROUP).users:
                order.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=user.id,
                    summary=_('Discount Approval %.2f%%', order.max_discount),
                    note=_('Order %(name)s has a discount of %(disc).2f%% and is waiting for approval.',
                           name=order.name, disc=order.max_discount),
                )
            order.message_post(body=_('Discount approval request for %.2f%% by %s.',
                                      order.max_discount, self.env.user.name))
        return True

    def action_approve_discount(self):
        if not self._is_discount_approver():
            raise UserError(_('You do not have permission to approve discounts.'))
        for order in self:
            order.write({
                'approval_state': 'approved',
                'approved_by_id': self.env.user.id,
                'approval_date': fields.Datetime.now(),
            })
            order.activity_feedback(['mail.mail_activity_data_todo'])
            order.message_post(body=_('Discount %.2f%% approved by %s.',
                                      order.max_discount, self.env.user.name))

        return True

    def action_reject_discount(self):
        if not self._is_discount_approver():
            raise UserError(_('You do not have permission to reject discounts.'))
        for order in self:
            order.write({'approval_state': 'rejected', 'approved_by_id': False, 'approval_date': False})
            order.activity_unlink(['mail.mail_activity_data_todo'])
            order.message_post(body=_('Discount %.2f%% rejected by %s. Please revise the discount.',
                                      order.max_discount, self.env.user.name))
        return True

    def action_confirm(self):
        for order in self:
            if order.need_discount_approval and order.approval_state != 'approved':
                if order._is_discount_approver():
                    # Approver boleh langsung konfirmasi = otomatis approve
                    order.action_approve_discount()
                else:
                    raise UserError(_(
                        'Order %(name)s has a discount of %(disc).2f%% (threshold %(thr).2f%%). '
                        'Please request approval before confirming.',
                        name=order.name, disc=order.max_discount,
                        thr=order.company_id.discount_approval_threshold))
        return super().action_confirm()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _reset_approval_if_needed(self):
        orders = self.order_id.filtered(
            lambda o: o.approval_state in ('approved', 'rejected') and o.state in ('draft', 'sent'))
        if orders:
            orders.write({'approval_state': 'draft', 'approved_by_id': False, 'approval_date': False})
            for o in orders:
                o.message_post(body=_('Order line changed, discount approval reset.'))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._reset_approval_if_needed()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if {'discount', 'price_unit', 'product_uom_qty', 'product_id'} & set(vals):
            self._reset_approval_if_needed()
        return res
