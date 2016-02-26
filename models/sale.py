from openerp.osv import osv, fields
from openerp.tools.translate import _

class SaleOrder(osv.osv):
    _inherit = 'sale.order'
    _columns = {
	'allow_additional_claim': fields.boolean('Allow Additional Claim'),
	'claims': fields.one2many('crm.claim', 'sale', 'Claim'),
	'claim_invoices': fields.many2many('account.invoice', 'claim_sale_order_invoice_rel', 'order_id', 'invoice_id', 'Refund/Claim Invoices', readonly=True, copy=False),
    }

    def get_default_claim_vals(self, cr, uid, sale, items, context=None):
        default_vals = {
                'default_pricelist_id': sale.pricelist_id.id,
                'default_warehouse': sale.warehouse_id.id,
                'default_hidden_sale': sale.id,
                'default_sale': sale.id,
                'default_partner_id': sale.partner_id.id,
                'default_claim_return_lines': items,
                'default_hidden_partner_id': sale.partner_id.id,
                'default_hidden_partner_billing_address': sale.partner_invoice_id.id,
                'default_hidden_partner_shipping_address': sale.partner_shipping_id.id,
                'default_partner_billing_address': sale.partner_invoice_id.id,
                'default_partner_shipping_address': sale.partner_shipping_id.id,
        }

	return default_vals


    def button_create_claim(self, cr, uid, ids, context=None):
        view_ref = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'crm_claim_sale_services', 'crm_claim_services_form')
        view_id = view_ref and view_ref[1] or False,
	sale = self.browse(cr, uid, ids[0])
	if sale.claims and not sale.allow_additional_claim:
	    raise osv.except_osv(_('Claim already filed!'), _('A claim exists already for this order.\nIf you want to create a new claim, please set this order to allow additional claims.'))

	sale.allow_additional_claim = False

	items = []
	for item in sale.order_line:
	    items.append({
		'type': 'return',
		'product': item.product_id.id,
		'product_uom': item.product_uom.id,
		'order_qty': item.product_uom_qty,
		'tax_id': [(6, 0, [x.id for x in item.tax_id])] if item.tax_id else [],
		'sale_price_unit': item.price_unit,
		'route_id': item.route_id and [(4, line.route_id.id)] or [],
		'state': 'draft',
		'name': item.name,
		'discount': item.discount,
		'sequence': item.sequence
	     })

	default_vals = self.get_default_claim_vals(cr, uid, sale, items)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Sales Claim'),
            'res_model': 'crm.claim',
	    'context': default_vals,
            'res_id': False,
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'nodestroy': True,
        }
