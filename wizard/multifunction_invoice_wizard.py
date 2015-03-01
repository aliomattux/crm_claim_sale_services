from openerp.osv import osv, fields


class CrmClaimMultifunctionInvoice(osv.osv_memory):
    _name = 'crm.claim.multifunction.invoice'
    _columns = {
	'move_lines': fields.one2many('crm.claim.multifunction.invoice.line', 'wizard', 'Items'),
	'wizard_action': fields.selection([('incoming', 'Incoming'), 
					   ('outgoing', 'Outgoing')], 'Action Taken'),
	'partner_id': fields.many2one('res.partner', 'Customer'),
	'partner_shipping_address': fields.many2one('res.partner', 'Shipping Address'),
	'claim': fields.many2one('crm.claim', 'Claim'),
    }


class CrmClaimMultifunctionInvoiceLine(osv.osv_memory):
    _name = 'crm.claim.multifunction.invoice.line'
    _columns = {
	'wizard': fields.many2one('crm.claim.multifunction.invoice', 'Wizard'),
	'product': fields.many2one('product.product', 'Product'),
	'name': fields.char('Description'),
	'order_qty': fields.float('Ordered Quantity'),
	'action_qty': fields.float('Quantity'),
	'claim_line': fields.many2one('crm.claim.line', 'Claim Line'),
    }
