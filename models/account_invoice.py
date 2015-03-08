from openerp.osv import osv, fields

class AccountInvoice(osv.osv):
    _inherit = 'account.invoice'
    _columns = {
	'claim': fields.many2one('crm.claim', 'Claim'),
    }
