from openerp.osv import osv, fields
from openerp.tools.translate import _
from datetime import datetime, timedelta
import openerp.addons.decimal_precision as dp
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP
from openerp.tools.float_utils import float_compare

CLAIM_SEQ_DICT = {'return': 'crm.claim.return',
		'refund': 'crm.claim.refund',
		'exchange': 'crm.claim.exchange'
}

class CrmClaim(osv.osv):
    _inherit = 'crm.claim'


    def _get_picking_in(self, cr, uid, context=None):
        obj_data = self.pool.get('ir.model.data')
        type_obj = self.pool.get('stock.picking.type')
        user_obj = self.pool.get('res.users')
        company_id = user_obj.browse(cr, uid, uid, context=context).company_id.id
        types = type_obj.search(cr, uid, [('code', '=', 'incoming'), ('warehouse_id.company_id', '=', company_id)], context=context)
        if not types:
            types = type_obj.search(cr, uid, [('code', '=', 'incoming'), ('warehouse_id', '=', False)], context=context)
            if not types:
                raise osv.except_osv(_('Error!'), _("Make sure you have at least an incoming picking type defined"))
        return types[0]


    def _get_return_journal(self, cr, uid, context=None):
        if context is None:
            context = {}
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        company_id = context.get('company_id', user.company_id.id)
        journal_obj = self.pool.get('account.journal')
        res = journal_obj.search(cr, uid, [('type', '=', 'claim_return'),
                                            ('company_id', '=', company_id)],
                                                limit=1)
        return res and res[0] or False


    _columns = {
	'name': fields.char('Name', required=True),
	'pricelist_id': fields.many2one('product.pricelist', 'Pricelist', required=True, readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}),
	'user_id': fields.many2one('res.users', 'CS Representative', track_visibility='always'),
	'warehouse': fields.many2one('stock.warehouse', 'Warehouse'),
	'hidden_partner_id': fields.many2one('res.partner', 'Customer', help="Needed because stupid OpenERP doesn't understand the concept of readonly field"),
	'claim_return_lines': fields.one2many('crm.claim.line', 'claim', string='Returned Items', domain=[('type', '=', 'return')]),
	'claim_delivery_lines': fields.one2many('crm.claim.line', 'claim', string='Delivered Items', domain=[('type', '=', 'delivery')]),
	'partner_id': fields.many2one('res.partner', 'Customer'),
	'hidden_partner_shipping_address': fields.many2one('res.partner', 'Shipping Address', help="Needed because stupid OpenERP doesn't understand the concept of readonly field"),
	'hidden_partner_billing_address': fields.many2one('res.partner', 'Billing Address', help="Needed because stupid OpenERP doesn't understand the concept of readonly field"),
	'hidden_sale': fields.many2one('sale.order', 'Created From Sale', help="Needed because stupid OpenERP doesn't understand the concept of readonly field"),
	'partner_billing_address': fields.many2one('res.partner', 'Billing Address'),
	'partner_shipping_address': fields.many2one('res.partner', 'Shipping Address'),
        'picking_type_id': fields.many2one('stock.picking.type', 'Deliver To', help="This will determine picking type of incoming shipment"),
        'state': fields.selection(
                [('cancel', 'Cancelled'),('draft', 'Draft'),('confirmed', 'Confirmed'),('exception', 'Exception'),('done', 'Done')],
                'Status', required=True, readonly=True, copy=False,
                help='* The \'Draft\' status is set when the related sales order in draft status. \
                    \n* The \'Confirmed\' status is set when the related sales order is confirmed. \
                    \n* The \'Exception\' status is set when the related sales order is set as exception. \
                    \n* The \'Done\' status is set when the sales order line has been picked. \
                    \n* The \'Cancelled\' status is set when a user cancel the sales order related.'),
	'sale': fields.many2one('sale.order', 'Created From Sale', readonly=True),
	'claim_reason': fields.many2one('crm.claim.reason', 'Reason', required=True),
	'claim_action': fields.selection([('return', 'Return'),
					  ('refund', 'Refund Only'),
					  ('exchange', 'Exchange')], 
	'Action Taken', required=True),
    }


    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if vals.get('name', '/') == '/':
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, \
		CLAIM_SEQ_DICT[vals['claim_action']]) or '/'

	#Bad code required to support readonly field user experience
	#Bad design requires bad code to solve simple problem supported in other software :(
	hidden_vals = {'hidden_partner_id': 'partner_id',
			'hidden_sale': 'sale',
			'hidden_shipping_address': 'partner_shipping_address',
			'hidden_billing_address': 'partner_billing_address'
	}
	for k, v in hidden_vals.items():
	    if k in vals.keys() and vals[k]:
		vals[v] = vals[k]

	#End bad code required

        ctx = dict(context or {}, mail_create_nolog=True)
        new_id = super(CrmClaim, self).create(cr, uid, vals, context=ctx)
 #       self.message_post(cr, uid, [new_id], body=_("Quotation created"), context=ctx)
        return new_id

    #Pricelist hardcode is to bypass problem temporarily
    _defaults = {
        'name': lambda obj, cr, uid, context: '/',
	'pricelist_id': 1,
	'state': 'draft',
	'picking_type_id': _get_picking_in,
    }


    def _prepare_procurement_group(self, cr, uid, claim, context=None):
        return {'name': claim.name, 'partner_id': claim.partner_shipping_address.id}


#    def _get_date_planned(self, cr, uid, claim, line, start_date, context=None):
 #       date_planned = datetime.strptime(start_date, DEFAULT_SERVER_DATETIME_FORMAT) + timedelta(days=line.delay or 0.0)
  #      return date_planned


    def _prepare_claim_line_procurement(self, cr, uid, claim, line, group_id=False, context=None):
#        date_planned = self._get_date_planned(cr, uid, claim, line, claim.date, context=context)
        routes = line.route and [(4, line.route_id.id)] or []

        return {
            'name': line.name,
            'origin': claim.name,
            'date_planned': claim.date,
            'product_id': line.product.id,
            'product_qty': line.order_qty,
            'product_uom': line.product_uom.id,
            'product_uos_qty': line.order_qty,
            'product_uos': line.product_uom.id,
            'company_id': claim.company_id.id,
            'group_id': group_id,
            'invoice_state': 'none',
            'claim_line_id': line.id,
	    'location_id': claim.partner_shipping_address.property_stock_customer.id,
            'route_ids': routes,
            'warehouse_id': claim.warehouse and claim.warehouse.id or False,
            'partner_dest_id': claim.partner_shipping_address.id
        }


    def onchange_picking_type_id(self, cr, uid, ids, picking_type_id, context=None):
        value = {}
        if picking_type_id:
            picktype = self.pool.get("stock.picking.type").browse(cr, uid, picking_type_id, context=context)
            if picktype.default_location_dest_id:
                value.update({'location_id': picktype.default_location_dest_id.id})
            value.update({'related_location_id': picktype.default_location_dest_id and picktype.default_location_dest_id.id or False})
        return {'value': value}


    def _prepare_claim_return_line_move(self, cr, uid, claim, line, picking_id, group_id, context=None):
        ''' prepare the stock move data from the PO line. This function returns a list of dictionary ready to be used in stock.move's create()'''
        product_uom = self.pool.get('product.uom')
        price_unit = line.sale_price_unit
        if line.product_uom.id != line.product.uom_id.id:
            price_unit *= line.product_uom.factor / line.product.uom_id.factor
        res = []
        move_template = {
            'name': line.name or '',
            'product_id': line.product.id,
            'product_uom': line.product_uom.id,
            'product_uos': line.product_uom.id,
            'date': claim.date,
            'date_expected': fields.date.date_to_datetime(self, cr, uid, line.date_planned, context),
            'location_id': claim.partner_id.property_stock_customer.id,
            'location_dest_id': claim.picking_type_id.default_location_dest_id.id,
            'picking_id': picking_id,
            'partner_id': claim.partner_shipping_address.id or claim.partner_id.id,
            'move_dest_id': False,
            'state': 'draft',
            'claim_line_id': line.id,
            'company_id': claim.company_id.id,
            'price_unit': price_unit,
            'picking_type_id': claim.picking_type_id.id,
            'group_id': group_id,
            'procurement_id': False,
            'origin': claim.name,
            'route_ids': claim.picking_type_id.warehouse_id and [(6, 0, [x.id for x in claim.picking_type_id.warehouse_id.route_ids])] or [],
            'warehouse_id': claim.picking_type_id.warehouse_id.id,
	    'invoice_state': 'none',
#            'invoice_state': claim.invoice_method == 'picking' and '2binvoiced' or 'none',
        }

        diff_quantity = line.order_qty
        for procurement in line.procurement_ids:
            procurement_qty = product_uom._compute_qty(cr, uid, procurement.product_uom.id, procurement.product_qty, to_uom_id=line.product_uom.id)
            tmp = move_template.copy()
            tmp.update({
                'product_uom_qty': min(procurement_qty, diff_quantity),
                'product_uos_qty': min(procurement_qty, diff_quantity),
                'move_dest_id': procurement.move_dest_id.id,  #move destination is same as procurement destination
                'group_id': procurement.group_id.id or group_id,  #move group is same as group of procurements if it exists, otherwise take another group
                'procurement_id': procurement.id,
                'invoice_state': procurement.rule_id.invoice_state or (procurement.location_id and procurement.location_id.usage == 'customer' and procurement.invoice_state=='picking' and '2binvoiced') or (claim.invoice_method == 'picking' and '2binvoiced') or 'none', #dropship case takes from sale
                'propagate': procurement.rule_id.propagate,
            })
            diff_quantity -= min(procurement_qty, diff_quantity)
            res.append(tmp)
        #if the order line has a bigger quantity than the procurement it was for (manually changed or minimal quantity), then
        #split the future stock move in two because the route followed may be different.
        if float_compare(diff_quantity, 0.0, precision_rounding=line.product_uom.rounding) > 0:
            move_template['product_uom_qty'] = diff_quantity
            move_template['product_uos_qty'] = diff_quantity
            res.append(move_template)
        return res


    def _create_stock_moves(self, cr, uid, claim, claim_return_lines, picking_id=False, context=None):
        """Creates appropriate stock moves for given order lines, whose can optionally create a
        picking if none is given or no suitable is found, then confirms the moves, makes them
        available, and confirms the pickings.

        If ``picking_id`` is provided, the stock moves will be added to it, otherwise a standard
        incoming picking will be created to wrap the stock moves (default behavior of the stock.move)

        Modules that wish to customize the procurements or partition the stock moves over
        multiple stock pickings may override this method and call ``super()`` with
        different subsets of ``order_lines`` and/or preset ``picking_id`` values.

        :param browse_record order: purchase order to which the order lines belong
        :param list(browse_record) order_lines: purchase order line records for which picking
                                                and moves should be created.
        :param int picking_id: optional ID of a stock picking to which the created stock moves
                               will be added. A new picking will be created if omitted.
        :return: None
        """
        stock_move = self.pool.get('stock.move')
        todo_moves = []
	new_group = claim.sale.procurement_group_id.id
#        new_group = self.pool.get("procurement.group").create(cr, uid, {'name': claim.name, 'partner_id': claim.partner_id.id}, context=context)

        for line in claim_return_lines:
            if not line.product:
                continue

            if line.product.type in ('product', 'consu'):
                for vals in self._prepare_claim_return_line_move(cr, uid, claim, line, picking_id, new_group, context=context):
                    move = stock_move.create(cr, uid, vals, context=context)
                    todo_moves.append(move)

        todo_moves = stock_move.action_confirm(cr, uid, todo_moves)
        stock_move.force_assign(cr, uid, todo_moves)

	return True


    def button_create_claim_delivery_order(self, cr, uid, ids, context=None):
        return self.action_ship_create(cr, uid, ids, context=context)


    def button_create_claim_return(self, cr, uid, ids, context=None):
        return self.action_return_create(cr, uid, ids, context=context)


    def button_create_claim_refund(self, cr, uid, ids, context=None):
        return False


    def action_return_create(self, cr, uid, ids, context=None):
        for claim in self.browse(cr, uid, ids):
            vals = {
                'picking_type_id': claim.picking_type_id.id,
                'partner_id': claim.partner_shipping_address.id or claim.partner_id.id,
  #              'date': max([l.date_planned for l in claim.claim_return_lines]),
                'origin': claim.name,
		'claim': claim.id,
            }

            picking_id = self.pool.get('stock.picking').create(cr, uid, vals, context=context)
            self._create_stock_moves(cr, uid, claim, claim.claim_return_lines, picking_id, context=context)

        view_ref = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_form')
        view_id = view_ref and view_ref[1] or False,

        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer Return'),
            'res_model': 'stock.picking',
            'context': {},
            'res_id': picking_id,
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'nodestroy': True,
        }

    def action_ship_create(self, cr, uid, ids, context=None):
        """Create the required procurements to supply sales order lines, also connecting
        the procurements to appropriate stock moves in order to bring the goods to the
        sales order's requested location.

        :return: True
        """
        context = dict(context)
        context['lang'] = self.pool['res.users'].browse(cr, uid, uid).lang
        procurement_obj = self.pool.get('procurement.order')
        claim_line_obj = self.pool.get('crm.claim.line')
        for claim in self.browse(cr, uid, ids, context=context):
            proc_ids = []
            vals = self._prepare_procurement_group(cr, uid, claim, context=context)
          #  if not claim.procurement_group_id:
#		group_id = claim.sale.procurement_group_id.id
            group_id = self.pool.get("procurement.group").create(cr, uid, vals, context=context)
#                claim.write({'procurement_group_id': group_id})

            for line in claim.claim_delivery_lines:
                #Try to fix exception procurement (possible when after a shipping exception the user choose to recreate)
                if line.procurement_ids:
		    print 'Call Primary'
                    #first check them to see if they are in exception or not (one of the related moves is cancelled)
                    procurement_obj.check(cr, uid, [x.id for x in line.procurement_ids if x.state not in ['cancel', 'done']])
                    line.refresh()
                    #run again procurement that are in exception in order to trigger another move
                    proc_ids += [x.id for x in line.procurement_ids if x.state in ('exception', 'cancel')]
                    procurement_obj.reset_to_confirmed(cr, uid, proc_ids, context=context)
		elif True:
#                elif claim_line_obj.need_procurement(cr, uid, [line.id], context=context):
		    print 'Call Secondary'
                    if (line.state == 'done') or not line.product:
                        continue
                    vals = self._prepare_claim_line_procurement(cr, uid, claim, line, group_id=group_id, context=context)
                    proc_id = procurement_obj.create(cr, uid, vals, context=context)
                    proc_ids.append(proc_id)
            #Confirm procurement order such that rules will be applied on it
            #note that the workflow normally ensure proc_ids isn't an empty list
            procurement_obj.run(cr, uid, proc_ids, context=context)

            #if shipping was in exception and the user choose to recreate the delivery order, write the new status of SO
            if claim.state == 'shipping_except':
                val = {'state': 'progress', 'shipped': False}

                if (claim.order_policy == 'manual'):
                    for line in claim.claim_return_lines:
                        if (not line.invoiced) and (line.state not in ('cancel', 'draft')):
                            val['state'] = 'manual'
                            break
                claim.write(val)
        return True



class CrmClaimLine(osv.osv):
    _name = 'crm.claim.line'

    def need_procurement(self, cr, uid, ids, context=None):
        #when sale is installed only, there is no need to create procurements, that's only
        #further installed modules (sale_service, sale_stock) that will change this.
        prod_obj = self.pool.get('product.product')
        for line in self.browse(cr, uid, ids, context=context):
            if prod_obj.need_procurement(cr, uid, [line.product.id], context=context):
                return True
        return False

    def onchange_product(self, cr, uid, ids, product, name, order_qty, product_uom, type, partner_id, warehouse_id, context=None):
        context = context or {}
        lang = context.get('lang', False)
	flag = False
        product_uom_obj = self.pool.get('product.uom')
        partner_obj = self.pool.get('res.partner')
        product_obj = self.pool.get('product.product')
        context = {'lang': lang, 'partner_id': partner_id}
        partner = partner_obj.browse(cr, uid, partner_id)
        lang = partner.lang
        context_partner = {'lang': lang, 'partner_id': partner_id}
	warehouse_obj = self.pool.get('stock.warehouse')
        if not product:
            return {'value': {'order_qty': order_qty}, 'domain': {'product_uom': []}}

#        if not date_order:
 #           date_order = time.strftime(DEFAULT_SERVER_DATE_FORMAT)

        result = {'type': type}
        warning_msgs = ''
        product = product_obj.browse(cr, uid, product, context=context_partner)

        uom2 = False
        if product_uom:
            uom2 = product_uom_obj.browse(cr, uid, product_uom)
            if product.uom_id.category_id.id != uom2.category_id.id:
                product_uom = False

#        fpos = False
 #       if not fiscal_position:
  #          fpos = partner.property_account_position or False
   #     else:
    #        fpos = self.pool.get('account.fiscal.position').browse(cr, uid, fiscal_position)
     #   if update_tax: #The quantity only have changed
      #      result['tax_id'] = self.pool.get('account.fiscal.position').map_tax(cr, uid, fpos, product_obj.taxes_id)

        if not flag:
            result['name'] = self.pool.get('product.product').name_get(cr, uid, [product.id], context=context_partner)[0][1]
            if product.description_sale:
                result['name'] += '\n'+product.description_sale

        domain = {}
        if not product_uom:
            result['product_uom'] = product.uom_id.id
            domain = {'product_uom':
                        [('category_id', '=', product.uom_id.category_id.id)]
	    }

        if not uom2:
            uom2 = product.uom_id
        # get unit price
	warning = False


        if product.type == 'product':
            #determine if the product is MTO or not (for a further check)
            isMto = False
            if warehouse_id:
                warehouse = warehouse_obj.browse(cr, uid, warehouse_id, context=context)
                for product_route in product.route_ids:
                    if warehouse.mto_pull_id and warehouse.mto_pull_id.route_id and warehouse.mto_pull_id.route_id.id == product_route.id:
                        isMto = True
                        break
            else:
                try:
                    mto_route_id = warehouse_obj._get_mto_route(cr, uid, context=context)
                except:
                    # if route MTO not found in ir_model_data, we treat the product as in MTS
                    mto_route_id = False
                if mto_route_id:
                    for product_route in product.route_ids:
                        if product_route.id == mto_route_id:
                            isMto = True
                            break

            #check if product is available, and if not: raise a warning, but do this only for products that aren't processed in MTO
            if not isMto:
                uom_record = False
                if uom:
                    uom_record = product_uom_obj.browse(cr, uid, uom, context=context)
                    if product.uom_id.category_id.id != uom_record.category_id.id:
                        uom_record = False
                if not uom_record:
                    uom_record = product.uom_id
                compare_qty = float_compare(product.virtual_available, qty, precision_rounding=uom_record.rounding)
                if compare_qty == -1:
                    warn_msg = _('You plan to sell %.2f %s but you only have %.2f %s available !\nThe real stock is %.2f %s. (without reservations)') % \
                        (qty, uom_record.name,
                         max(0,product.virtual_available), uom_record.name,
                         max(0,product.qty_available), uom_record.name)
                    warning_msgs += _("Not enough stock ! : ") + warn_msg + "\n\n"	    

        return {'value': result, 'domain': domain, 'warning': warning}



    def _amount_line(self, cr, uid, ids, field_name, arg, context=None):
        tax_obj = self.pool.get('account.tax')
        res = {}
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            price = line.sale_price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = tax_obj.compute_all(cr, uid, line.tax_id, price, line.order_qty, line.product, line.claim.partner_id)
            res[line.id] = taxes['total']
        return res


    _columns = {
	'route': fields.many2one('stock.location.route', 'Route', domain=[('sale_selectable', '=', True)]),
	'type': fields.selection([('return', 'Returned'), ('delivery', 'Delivery')], 'Line Type', required=True),
        'claim': fields.many2one('crm.claim', 'Order Reference', required=True, ondelete='cascade', select=True, readonly=True, states={'draft':[('readonly',False)]}),
        'name': fields.text('Description', required=True, readonly=True, states={'draft': [('readonly', False)]}),
	'date_planned': fields.related('claim', 'date', type="date", string="Date Planned"),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying a list of sales order lines."),
        'product': fields.many2one('product.product', 'Product', domain=[('sale_ok', '=', True)], change_default=True, readonly=True, states={'draft': [('readonly', False)]}, ondelete='restrict'),
	'order_qty': fields.float('Order Quantity'),
	'product_uom': fields.many2one('product.uom', 'UOM'),
	'discount': fields.float('Discount'),
	'tax_id': fields.many2many('account.tax', 'crm_claim_line_tax', 'claim_line_id', 'tax_id', 'Taxes', readonly=True),
	'sale_price_unit': fields.float('Paid Unit Price', digits=(12, 2)),
#        'price_unit': fields.float('Unit Price', required=True, digits_compute= dp.get_precision('Product Price'), readonly=True, states={'draft': [('readonly', False)]}),
        'price_subtotal': fields.function(_amount_line, string='Subtotal', digits_compute= dp.get_precision('Account')),
	'procurement_ids': fields.one2many('procurement.order', 'claim_line_id', 'Procurements'),
        'state': fields.selection(
                [('cancel', 'Cancelled'),('draft', 'Draft'),('confirmed', 'Confirmed'),('exception', 'Exception'),('done', 'Done')],
                'Status', required=True, readonly=True, copy=False,
                help='* The \'Draft\' status is set when the related sales order in draft status. \
                    \n* The \'Confirmed\' status is set when the related sales order is confirmed. \
                    \n* The \'Exception\' status is set when the related sales order is set as exception. \
                    \n* The \'Done\' status is set when the sales order line has been picked. \
                    \n* The \'Cancelled\' status is set when a user cancel the sales order related.'),

    }

    _defaults = {
	'state': 'draft',
    }


class ProcurementOrder(osv.osv):
    _inherit = 'procurement.order'
    _columns = {
        'claim_line_id': fields.many2one('crm.claim.line', 'CRM Claim Line'),
        'claim_id': fields.related('claim_line_id', 'claim_id', type='many2one', relation='crm.claim', string='Claim'),
    }


class CrmClaimReason(osv.osv):
    _name = 'crm.claim.reason'
    _columns = {
	'name': fields.char('Claim Reason', required=True),
    }
