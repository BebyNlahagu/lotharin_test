{
    'name': 'Reseller Commission',
    'summary': 'Monthly tiered commission for resellers, calculated from posted invoices',
    'description': """
Reseller commission
===================
* Flag partners as resellers.
* Client-configurable commission tiers (lower bound + rate).
* One commission record per reseller per month, computed from posted customer
  invoices (credit notes deducted, taxes excluded), with detail lines linking to the invoices.
* Draft / Confirmed / Paid workflow with dedicated security groups.
* Monthly scheduled action and a manual generation wizard.
    """,
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'author': 'Candidate (Lotharin screening challenge)',
    'license': 'LGPL-3',
    'depends': ['account', 'contacts', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/security_rules.xml',
        'data/ir_sequence_data.xml',
        'data/reseller_commission_tier_data.xml',
        'data/ir_cron_data.xml',
        'views/res_partner_views.xml',
        'views/reseller_commission_tier_views.xml',
        'views/reseller_commission_views.xml',
        'wizard/reseller_commission_generate_wizard_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/demo_users_partners.xml',
        'demo/demo_invoices.xml',
    ],
    'application': True,
    'installable': True,
}
