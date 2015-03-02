from openerp.osv import osv, fields
from openerp.tools.translate import _

class SaleOrder(osv.osv):
    _inherit = 'sale.order'
    _columns = {
	'claims': fields.one2many('crm.claim', 'sale', 'Claim'),
        'product_policy': fields.selection([('user_select', 'User Select'),
                                        ('from_delivery', 'Return from Delivered Goods'),
                                        ('from_sale', 'Return from Sold Goods'),
        ], 'Product Policy', readonly=True),
        'strict_return': fields.boolean('Strict Return', readonly=True, help="""If you want to restrict what \
                can be returned based on the product policy. Note: This does not apply to \
                User Select Policy"""),
    }

    def button_create_claim(self, cr, uid, ids, context=None):
        view_ref = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'crm_claim_sale_services', 'crm_claim_services_form')
        view_id = view_ref and view_ref[1] or False,
	sale = self.browse(cr, uid, ids[0])
	items = []
	for item in sale.order_line:
	    items.append({
		'type': 'return',
		'product': item.product_id.id,
		'product_uom': item.product_uom.id,
		'order_qty': item.product_uom_qty,
	#	'tax_id': item.tax_id,
		'sale_price_unit': item.price_unit,
		'route_id': item.route_id and [(4, line.route_id.id)] or [],
		'state': 'draft',
		'name': item.name,
		'discount': item.discount,
		'sequence': item.sequence
	     })

	default_vals = {
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
