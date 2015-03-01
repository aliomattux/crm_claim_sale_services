from openerp.osv import osv, fields


class CrmClaimMultifunctionStock(osv.osv_memory):
    _name = 'crm.claim.multifunction.stock'
    _columns = {
	'move_lines': fields.one2many('crm.claim.multifunction.stock.line', 'wizard', 'Items'),
	'wizard_action': fields.selection([('incoming', 'Incoming'), 
					   ('outgoing', 'Outgoing')], 'Action Taken'),
	'partner_id': fields.many2one('res.partner', 'Customer'),
	'partner_shipping_address': fields.many2one('res.partner', 'Shipping Address'),
	'claim': fields.many2one('crm.claim', 'Claim'),
    }


    def prepare_line(self, cr, uid, item, context=None):
	return {
		'product': item.product.id,
		'name': item.name,
		'order_qty': item.order_qty,
		'action_qty': item.order_qty,
		'claim_line': item.id,
	}


    def default_get(self, cr, uid, fields, context=None):
        if context is None: context = {}
        res = super(CrmClaimMultifunctionStock, self).default_get(cr, uid, fields, context=context)
        action_ids = context.get('active_ids', [])
        active_model = context.get('active_model')

        if not action_ids or len(action_ids) != 1:
            # Partial Picking Processing may only be done for one picking at a time
            return res

	assert active_model in ('crm.claim.multifunction.stock'), 'Bad context propagation'
	claim_obj = self.pool.get('crm.claim')
	claim = claim_obj.browse(cr, uid, action_ids[0])
	vals = {
		'partner_shipping_address': claim.partner_shipping_address.id,
		'claim': claim.id,
		'partner_id': claim.partner_id.id,
		'move_lines': []
	}

	for item in claim.claim_lines:
	    vals['move_lines'].append(self.prepare_line(cr, uid, item))

	res.update(vals)
	return res


class CrmClaimMultifunctionStockLine(osv.osv_memory):
    _name = 'crm.claim.multifunction.stock.line'
    _columns = {
	'wizard': fields.many2one('crm.claim.multifunction.stock', 'Wizard'),
	'product': fields.many2one('product.product', 'Product'),
	'name': fields.char('Description'),
	'order_qty': fields.float('Ordered Quantity'),
	'action_qty': fields.float('Quantity'),
	'claim_line': fields.many2one('crm.claim.line', 'Claim Line'),
    }
