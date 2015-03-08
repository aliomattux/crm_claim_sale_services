{
    'name': 'CRM - Claim Sale Services',
    'version': '1.1',
    'author': 'Kyle Waid',
    'category': 'Sales Management',
    'depends': ['crm_claim', 'sale'],
    'website': 'https://www.gcotech.com',
    'description': """ 
    """,
    'data': ['views/sale.xml',
	     'views/claim.xml',
	     'views/stock.xml',
	     'views/account_invoice.xml',
	     'data/claim_service_sequence.xml',
    ],
    'test': [
    ],
    'installable': True,
    'auto_install': False,
}
