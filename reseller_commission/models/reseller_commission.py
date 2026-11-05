import logging
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

GROUP_MANAGER = 'reseller_commission.group_commission_manager'
GROUP_ACCOUNTANT = 'reseller_commission.group_commission_accountant'

# (from state, to state) -> group allowed to perform the change
STATE_TRANSITIONS = {
    ('draft', 'confirmed'): GROUP_MANAGER,
    ('confirmed', 'draft'): GROUP_MANAGER,
    ('confirmed', 'paid'): GROUP_ACCOUNTANT,
}
# Business fields that cannot change once a record left draft.
LOCKED_FIELDS = {'reseller_id', 'date_from', 'company_id', 'line_ids', 'tier_id', 'rate'}


class ResellerCommission(models.Model):
    _name = 'reseller.commission'
    _description = 'Reseller Monthly Commission'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, reseller_id'

    name = fields.Char(default='/', readonly=True, copy=False)
    reseller_id = fields.Many2one(
        'res.partner', string='Reseller', required=True, index=True,
        domain=[('is_reseller', '=', True)], ondelete='restrict')
    date_from = fields.Date(
        string='Period Start', required=True, index=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1) - relativedelta(months=1),
        help='First day of the month the commission is calculated for.')
    date_to = fields.Date(string='Period End', compute='_compute_dates', store=True)
    payment_due_date = fields.Date(
        string='Payable From', compute='_compute_dates', store=True,
        help='Commission is paid the month after the period: this is the first day of that month.')
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    line_ids = fields.One2many('reseller.commission.line', 'commission_id', string='Source Documents')
    total_sales = fields.Monetary(
        string='Net Sales', compute='_compute_total_sales', store=True, currency_field='currency_id')
    tier_id = fields.Many2one('reseller.commission.tier', string='Applied Tier', readonly=True, ondelete='restrict')
    rate = fields.Float(string='Rate (%)', digits=(5, 2), readonly=True,
                        help='Snapshot of the tier rate at calculation time.')
    commission_amount = fields.Monetary(
        string='Commission', compute='_compute_commission_amount', store=True,
        currency_field='currency_id', tracking=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('confirmed', 'Confirmed'), ('paid', 'Paid')],
        default='draft', required=True, copy=False, tracking=True, index=True)
    confirmed_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    confirmed_date = fields.Datetime(readonly=True, copy=False)
    paid_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    paid_date = fields.Date(readonly=True, copy=False)
    note = fields.Text()

    _sql_constraints = [
        ('reseller_period_company_uniq', 'unique(reseller_id, date_from, company_id)',
         'There is already a commission record for this reseller and period.'),
    ]

    # ------------------------------------------------------------------
    # Constraints & computes
    # ------------------------------------------------------------------
    @api.constrains('date_from')
    def _check_period_start(self):
        for rec in self:
            if rec.date_from and rec.date_from.day != 1:
                raise ValidationError(_("The period must start on the first day of a month."))

    @api.constrains('reseller_id')
    def _check_reseller(self):
        for rec in self:
            if not rec.reseller_id.is_reseller:
                raise ValidationError(_("%s is not flagged as reseller.", rec.reseller_id.display_name))

    @api.depends('date_from')
    def _compute_dates(self):
        for rec in self:
            if rec.date_from:
                rec.date_to = rec.date_from + relativedelta(months=1, days=-1)
                rec.payment_due_date = rec.date_from + relativedelta(months=1)
            else:
                rec.date_to = rec.payment_due_date = False

    @api.depends('line_ids.amount')
    def _compute_total_sales(self):
        for rec in self:
            rec.total_sales = sum(rec.line_ids.mapped('amount'))

    @api.depends('total_sales', 'rate', 'currency_id')
    def _compute_commission_amount(self):
        for rec in self:
            base = max(0.0, rec.total_sales)
            # Net negative months (refunds > sales) never give a negative commission.
            currency = rec.currency_id or rec.company_id.currency_id or self.env.company.currency_id
            rec.commission_amount = currency.round(base * rec.rate / 100.0)

    # ------------------------------------------------------------------
    # ORM overrides: sequence, state machine and edit locks
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('reseller.commission') or '/'
            if vals.get('state', 'draft') != 'draft' and not self.env.su:
                raise UserError(_("A commission record must be created in draft."))
        return super().create(vals_list)

    def write(self, vals):
        if 'state' in vals:
            for rec in self:
                rec._check_state_transition(vals['state'])
        if LOCKED_FIELDS & set(vals):
            self._check_editable()
        return super().write(vals)

    def unlink(self):
        if any(rec.state != 'draft' for rec in self):
            raise UserError(_("Only draft commission records can be deleted."))
        return super().unlink()

    def _check_editable(self):
        if any(rec.state != 'draft' for rec in self):
            raise UserError(_("Confirmed or paid commission records cannot be modified. Reset to draft first."))

    def _check_state_transition(self, new_state):
        self.ensure_one()
        if self.state == new_state:
            return
        group = STATE_TRANSITIONS.get((self.state, new_state))
        if not group:
            raise UserError(_("Invalid status change: %(old)s to %(new)s.", old=self.state, new=new_state))
        if not self.env.su and not self.env.user.has_group(group):
            raise AccessError(_("You are not allowed to perform this status change."))

    # ------------------------------------------------------------------
    # Calculation
    # ------------------------------------------------------------------
    @api.model
    def _search_source_moves(self, company, date_from, date_to, resellers):
        """Posted customer invoices / credit notes of the resellers in the period.

        sudo(): the commission manager does not need accounting rights to see the
        figures; access to this feature is itself restricted to commission groups.
        """
        return self.env['account.move'].sudo().search([
            ('company_id', '=', company.id),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
            ('commercial_partner_id', 'in', resellers.ids),
        ], order='invoice_date, id')

    @api.model
    def _prepare_line_vals(self, move):
        # amount_untaxed_signed: company currency, excluding tax, negative for credit notes.
        return {'move_id': move.id, 'amount': move.amount_untaxed_signed}

    def _set_lines(self, moves):
        self.ensure_one()
        self.write({'line_ids': [(5, 0, 0)] + [(0, 0, self._prepare_line_vals(m)) for m in moves]})
        self._apply_tier()

    def _apply_tier(self):
        Tier = self.env['reseller.commission.tier']
        for rec in self:
            tier = Tier._get_tier_for_amount(rec.total_sales, rec.company_id)
            rec.write({'tier_id': tier.id, 'rate': tier.rate if tier else 0.0})

    @api.model
    def generate_for_period(self, date_from, resellers=None, company=None):
        """Create or refresh the draft commission of each reseller for the month of date_from.

        Idempotent: confirmed/paid records are never touched, draft ones are recalculated,
        and draft ones that no longer have any sales are removed.
        Returns the commission records created or refreshed.
        """
        date_from = fields.Date.to_date(date_from).replace(day=1)
        date_to = date_from + relativedelta(months=1, days=-1)
        company = company or self.env.company
        if resellers is None:
            resellers = self.env['res.partner'].search([
                ('is_reseller', '=', True), ('company_id', 'in', (False, company.id))])
        moves = self._search_source_moves(company, date_from, date_to, resellers)
        moves_by_partner = defaultdict(lambda: self.env['account.move'])
        for move in moves:
            moves_by_partner[move.commercial_partner_id] |= move

        existing = self.search([
            ('company_id', '=', company.id), ('date_from', '=', date_from),
            ('reseller_id', 'in', resellers.ids)])
        existing_by_partner = {rec.reseller_id: rec for rec in existing}

        result = self.browse()
        for partner, partner_moves in moves_by_partner.items():
            commission = existing_by_partner.get(partner)
            if commission and commission.state != 'draft':
                continue
            if not commission:
                commission = self.create({
                    'reseller_id': partner.id, 'date_from': date_from, 'company_id': company.id})
            commission._set_lines(partner_moves)
            result |= commission
        stale = existing.filtered(lambda r: r.state == 'draft' and r.reseller_id not in moves_by_partner)
        stale.unlink()
        return result

    @api.model
    def _cron_generate_previous_month(self):
        previous_month = fields.Date.context_today(self).replace(day=1) - relativedelta(months=1)
        for company in self.env['res.company'].search([]):
            created = self.with_company(company).generate_for_period(previous_month, company=company)
            _logger.info("Reseller commission: %s record(s) generated for %s (%s)",
                         len(created), previous_month, company.name)

    # ------------------------------------------------------------------
    # Workflow actions
    # ------------------------------------------------------------------
    def action_recompute(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft records can be recomputed."))
            rec._set_lines(self._search_source_moves(
                rec.company_id, rec.date_from, rec.date_to, rec.reseller_id))
        return True

    def _check_lines_up_to_date(self):
        for rec in self:
            fresh = self._search_source_moves(rec.company_id, rec.date_from, rec.date_to, rec.reseller_id)
            expected = {(m.id, m.amount_untaxed_signed) for m in fresh}
            current = {(l.move_id.id, l.amount) for l in rec.line_ids}
            if expected != current:
                raise UserError(_(
                    "The invoices of %s changed since this record was calculated. "
                    "Click Recompute before confirming.", rec.name))

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft records can be confirmed."))
        self._check_lines_up_to_date()
        self._apply_tier()
        self.write({
            'state': 'confirmed',
            'confirmed_by_id': self.env.user.id,
            'confirmed_date': fields.Datetime.now(),
        })
        return True

    def action_reset_to_draft(self):
        self.write({'state': 'draft', 'confirmed_by_id': False, 'confirmed_date': False})
        return True

    def action_mark_paid(self):
        self.write({
            'state': 'paid',
            'paid_by_id': self.env.user.id,
            'paid_date': fields.Date.context_today(self),
        })
        return True
