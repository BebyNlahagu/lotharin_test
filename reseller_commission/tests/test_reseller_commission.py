from dateutil.relativedelta import relativedelta
from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tools import mute_logger

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestResellerCommission(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.Commission = cls.env['reseller.commission']
        for name, minimum, rate in [('T1', 0, 3), ('T2', 50_000_000, 5), ('T3', 150_000_000, 7)]:
            cls.env['reseller.commission.tier'].create({
                'name': name, 'min_amount': minimum, 'rate': rate, 'company_id': cls.company.id})
        cls.salesperson = new_test_user(
            cls.env, login='rc_sales', groups='reseller_commission.group_commission_user',
            company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        cls.manager = new_test_user(
            cls.env, login='rc_manager', groups='reseller_commission.group_commission_manager',
            company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        cls.accountant = new_test_user(
            cls.env, login='rc_acc', groups='reseller_commission.group_commission_accountant',
            company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        cls.reseller = cls.env['res.partner'].create({
            'name': 'Reseller One', 'is_reseller': True, 'user_id': cls.salesperson.id})
        cls.other_reseller = cls.env['res.partner'].create({'name': 'Reseller Two', 'is_reseller': True})
        cls.period = fields.Date.today().replace(day=1) - relativedelta(months=1)

    def _invoice(self, amount, move_type='out_invoice', partner=None, post=True, day=10):
        return self.init_invoice(
            move_type, partner=partner or self.reseller,
            invoice_date=self.period + relativedelta(days=day - 1), amounts=[amount], post=post)

    def _generate(self, resellers=None):
        return self.Commission.generate_for_period(
            self.period, resellers=resellers or self.reseller, company=self.company)

    def test_tier_boundaries(self):
        Tier = self.env['reseller.commission.tier']
        cases = {0: 3, 49_999_999: 3, 50_000_000: 5, 149_999_999: 5, 150_000_000: 7, 900_000_000: 7}
        for amount, rate in cases.items():
            self.assertEqual(Tier._get_tier_for_amount(amount, self.company).rate, rate, amount)

    def test_generate_is_idempotent(self):
        self._invoice(120_000_000)
        commission = self._generate()
        self.assertEqual(commission.total_sales, 120_000_000)
        self.assertEqual(commission.rate, 5)
        self.assertEqual(commission.commission_amount, 6_000_000)
        self.assertEqual(len(commission.line_ids), 1)
        again = self._generate()
        self.assertEqual(again, commission)
        self.assertEqual(self.Commission.search_count([('reseller_id', '=', self.reseller.id)]), 1)

    def test_refund_deducted_draft_and_non_reseller_ignored(self):
        self._invoice(100_000_000)
        self._invoice(30_000_000, move_type='out_refund')
        self._invoice(50_000_000, post=False)
        self._invoice(80_000_000, partner=self.partner_a)  # not a reseller
        commission = self._generate()
        self.assertEqual(commission.total_sales, 70_000_000)
        self.assertEqual(commission.rate, 5)
        self.assertFalse(self.Commission.search([('reseller_id', '=', self.partner_a.id)]))

    def test_negative_month_gives_zero_commission(self):
        self._invoice(10_000_000)
        self._invoice(40_000_000, move_type='out_refund')
        commission = self._generate()
        self.assertEqual(commission.total_sales, -30_000_000)
        self.assertEqual(commission.commission_amount, 0)

    def test_locked_after_confirm_and_regeneration_skips_it(self):
        self._invoice(60_000_000)
        commission = self._generate()
        commission.with_user(self.manager).action_confirm()
        self.assertEqual(commission.state, 'confirmed')
        with self.assertRaises(UserError):
            commission.write({'rate': 99})
        with self.assertRaises(UserError):
            commission.unlink()
        with self.assertRaises(UserError):
            commission.line_ids.write({'amount': 1})
        self._invoice(100_000_000, day=20)
        self.assertFalse(self._generate())  # confirmed record is skipped
        self.assertEqual(commission.total_sales, 60_000_000)

    def test_confirm_refused_when_invoices_changed(self):
        self._invoice(60_000_000)
        commission = self._generate()
        self._invoice(10_000_000, day=20)
        with self.assertRaises(UserError):
            commission.with_user(self.manager).action_confirm()
        commission.with_user(self.manager).action_recompute()
        commission.with_user(self.manager).action_confirm()
        self.assertEqual(commission.total_sales, 70_000_000)

    def test_workflow_permissions(self):
        self._invoice(60_000_000)
        commission = self._generate()
        with self.assertRaises(AccessError):
            commission.with_user(self.salesperson).action_confirm()
        with self.assertRaises(AccessError):
            commission.with_user(self.accountant).action_confirm()
        commission.with_user(self.manager).action_confirm()
        with self.assertRaises(AccessError):
            commission.with_user(self.manager).action_mark_paid()
        commission.with_user(self.accountant).action_mark_paid()
        self.assertEqual(commission.state, 'paid')
        self.assertTrue(commission.paid_date)
        with self.assertRaises(UserError):
            commission.with_user(self.manager).action_reset_to_draft()

    def test_salesperson_sees_only_own_resellers(self):
        self._invoice(60_000_000)
        self._invoice(60_000_000, partner=self.other_reseller)
        both = self._generate(self.reseller | self.other_reseller)
        self.assertEqual(len(both), 2)
        visible = self.Commission.with_user(self.salesperson).search([])
        self.assertEqual(visible.reseller_id, self.reseller)
        self.assertEqual(self.Commission.with_user(self.manager).search_count([('id', 'in', both.ids)]), 2)
        partners = self.env['res.partner'].with_user(self.salesperson).search([('is_reseller', '=', True)])
        self.assertEqual(partners, self.reseller)
        all_partners = self.env['res.partner'].with_user(self.manager).search([('is_reseller', '=', True)])
        self.assertEqual(all_partners, self.reseller | self.other_reseller)

    def test_constraints(self):
        self._invoice(60_000_000)
        commission = self._generate()
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            self.Commission.create({
                'reseller_id': self.reseller.id, 'date_from': self.period, 'company_id': self.company.id})
        with self.assertRaises(ValidationError):
            self.Commission.create({
                'reseller_id': self.other_reseller.id, 'date_from': self.period + relativedelta(days=3),
                'company_id': self.company.id})
        child = self.env['res.partner'].create({'name': 'Contact', 'parent_id': self.reseller.id})
        with self.assertRaises(ValidationError):
            child.is_reseller = True
        with self.assertRaises(ValidationError):
            self.reseller.is_reseller = False  # has commission records
        self.assertTrue(commission.exists())
