{
    'name': 'Sale Discount Approval',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'This module allows you to set up a discount approval process for sales orders in Odoo. It enables you to define approval rules based on discount thresholds and user roles, ensuring that discounts are properly reviewed and authorized before being applied to sales orders.',
    'description': """
        This module allows you to set up a discount approval process for sales orders in Odoo.
        It enables you to define approval rules based on discount thresholds and user roles, ensuring that discounts are properly reviewed and authorized before being applied to sales orders.
    """,
    'depends': ['sale_management', 'mail'],
    'data': [
        'security/security.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
