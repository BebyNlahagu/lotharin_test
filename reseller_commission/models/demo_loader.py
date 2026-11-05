import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# key, partner xml id, month (1 = last month, 2 = month before), day, type, label, amount, post?
SEED_MOVES = [
    ('A-M1-1', 'partner_reseller_andalas', 1, 5, 'out_invoice', 'Meja makan jati 6 kursi', 25_000_000, True),
    ('A-M1-2', 'partner_reseller_andalas', 1, 18, 'out_invoice', 'Lemari pakaian 3 pintu', 15_000_000, True),
    ('A-M2-1', 'partner_reseller_andalas', 2, 9, 'out_invoice', 'Set sofa ruang tamu', 55_000_000, True),
    ('B-M1-1', 'partner_reseller_bangun', 1, 7, 'out_invoice', 'Kitchen set custom', 70_000_000, True),
    ('B-M1-2', 'partner_reseller_bangun', 1, 21, 'out_invoice', 'Lemari display toko', 50_000_000, True),
    ('B-M1-3', 'partner_reseller_bangun', 1, 25, 'out_invoice', 'Draft quotation not yet posted', 30_000_000, False),
    ('B-M2-1', 'partner_reseller_bangun', 2, 12, 'out_invoice', 'Furnitur kantor 20 unit', 160_000_000, True),
    ('C-M1-1', 'partner_reseller_griya', 1, 3, 'out_invoice', 'Furnitur apartemen 12 unit', 180_000_000, True),
    ('C-M1-2', 'partner_reseller_griya', 1, 20, 'out_refund', 'Retur 2 lemari cacat', 10_000_000, True),
    ('C-M2-1', 'partner_reseller_griya', 2, 15, 'out_invoice', 'Pesanan tepat Rp 50 juta (batas tier)', 50_000_000, True),
    ('X-M1-1', 'partner_customer_sari', 1, 11, 'out_invoice', 'Penjualan end customer (bukan reseller)', 20_000_000, True),
]


class ResellerCommissionDemoLoader(models.AbstractModel):
    _name = 'reseller.commission.demo.loader'
    _description = 'Seed loader for the reseller commission demo'

    @api.model
    def load(self):
        """Create the sample invoices. Idempotent: keyed on the customer reference."""
        company = self.env.ref('base.main_company')
        Move = self.env['account.move'].with_company(company)
        Journal = self.env['account.journal']
        sale_domain = [('type', '=', 'sale'), ('company_id', '=', company.id)]
        journal = Journal.search(sale_domain, limit=1)
        if not journal:
            # Empty database without accounting localisation: load the generic chart.
            try:
                with self.env.cr.savepoint():
                    self.env['account.chart.template'].try_loading('generic_coa', company)
            except Exception:  # noqa: BLE001 - seed must not break the install
                _logger.warning("Could not load the generic chart of accounts.", exc_info=True)
            journal = Journal.search(sale_domain, limit=1)
        if not journal or not journal.default_account_id:
            _logger.warning("No sales journal / income account: sample invoices skipped.")
            return
        first_of_month = fields.Date.context_today(self).replace(day=1)
        month_start = {1: first_of_month - relativedelta(months=1),
                       2: first_of_month - relativedelta(months=2)}
        for key, xmlid, month, day, move_type, label, amount, post in SEED_MOVES:
            ref = 'RCDEMO/%s' % key
            if Move.search_count([('ref', '=', ref), ('company_id', '=', company.id)]):
                continue
            partner = self.env.ref('reseller_commission.%s' % xmlid)
            invoice_date = month_start[month] + relativedelta(days=day - 1)
            move = Move.create({
                'move_type': move_type,
                'partner_id': partner.id,
                'invoice_date': invoice_date,
                'date': invoice_date,
                'ref': ref,
                'journal_id': journal.id,
                'invoice_line_ids': [(0, 0, {
                    'name': label,
                    'quantity': 1,
                    'price_unit': amount,
                    'account_id': journal.default_account_id.id,
                })],
            })
            if post:
                move.action_post()
