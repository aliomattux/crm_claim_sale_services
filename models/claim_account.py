from openerp.osv import osv, fields
from openerp.tools.translate import _
from datetime import datetime, timedelta
import openerp.addons.decimal_precision as dp
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP
from openerp.tools.float_utils import float_compare


class AccountInvoice(osv.osv):
    _inherit = 'account.invoice'
    _columns = {
	'claim': fields.many2one('crm.claim', 'Claim'),
    }

class AccountInvoiceLine(osv.osv):
    _inherit = 'account.invoice.line'
    _columns = {
	'claim_return_line': fields.many2one('crm.claim.line', 'Returned Line Id'),
	'claim_charge_line': fields.many2one('crm.claim.line', 'Charged Line Id'),
    }



class CrmClaim(osv.osv):
    _inherit = 'crm.claim'
    _columns = {
#	'refund_invoice_ids': fields.many2many('account.invoice', 'sale_order_invoice_rel', 'claim_id', 'invoice_id', 'Invoices', readonly=True, copy=False, help="This is the list of invoices that have been generated for this sales order. The same sales order may have been invoiced in several times (by line for example)."),
	'invoice_ids': fields.many2many('account.invoice', 'crm_claim_invoice_rel', 'claim_id', 'invoice_id', 'Invoices', readonly=True, copy=False, help="This is the list of invoices that have been generated for this sales order. The same sales order may have been invoiced in several times (by line for example)."),

    }

    def button_create_claim_refund(self, cr, uid, ids, context=None):
	return self.action_refund_create(cr, uid, ids, context=context)


    def button_create_claim_invoice(self, cr, uid, ids, context=None):
	return self.action_charge_invoice_create(cr, uid, ids, context=context)


    ###############  Refund Functions  ##################

    def _choose_account_from_return_line(self, cr, uid, line, context=None):
        fiscal_obj = self.pool.get('account.fiscal.position')
        property_obj = self.pool.get('ir.property')
        if line.product:
            acc_id = line.product.property_account_expense.id
            if not acc_id:
                acc_id = line.product.categ_id.property_account_expense_categ.id
            if not acc_id:
                raise osv.except_osv(_('Error!'), _('Define an expense account for this product: "%s" (id:%d).') % (line.product.name, line.product.id,))
        else:
            acc_id = property_obj.get(cr, uid, 'property_account_expense_categ', 'product.category', context=context).id

	fpos = False
#        fpos = line.claim.fiscal_position or False

        return fiscal_obj.map_account(cr, uid, fpos, acc_id)


    def _prepare_return_inv_line(self, cr, uid, account_id, line, context=None):
        """Collects require data from purchase order line that is used to create invoice line
        for that purchase order line
        :param account_id: Expense account of the product of PO line if any.
        :param browse_record order_line: Purchase order line browse record
        :return: Value for fields of invoice lines.
        :rtype: dict
        """
        return {
            'name': line.name,
            'account_id': account_id,
            'price_unit': line.sale_price_unit or 0.0,
            'quantity': line.order_qty,
            'product_id': line.product.id or False,
            'uos_id': line.product_uom.id or False,
            'invoice_line_tax_id': [(6, 0, [x.id for x in line.tax_id])],
#            'account_analytic_id': line.account_analytic_id.id or False,
            'return_claim_line_id': line.id,
        }


    def _prepare_refund_invoice(self, cr, uid, claim, line_ids, context=None):
        """Prepare the dict of values to create the new invoice for a
           purchase order. This method may be overridden to implement custom
           invoice generation (making sure to call super() to establish
           a clean extension chain).

           :param browse_record order: purchase.order record to invoice
           :param list(int) line_ids: list of invoice line IDs that must be
                                      attached to the invoice
           :return: dict of value to create() the invoice
        """
        journal_ids = self.pool['account.journal'].search(
                            cr, uid, [('type', '=', 'sale_refund'),
                                      ('company_id', '=', claim.company_id.id)],
                            limit=1)
        if not journal_ids:
            raise osv.except_osv(
                _('Error!'),
                _('Define Refund journal for this company: "%s" (id:%d).') % \
                    (claim.company_id.name, claim.company_id.id))

        return {
            'name': claim.name,
	    'claim': claim.id,
            'reference': claim.name,
            'account_id': claim.partner_id.property_account_payable.id,
            'type': 'out_refund',
            'partner_id': claim.partner_id.id,
 #           'currency_id': claim.currency_id.id,
            'journal_id': len(journal_ids) and journal_ids[0] or False,
            'invoice_line': [(6, 0, line_ids)],
            'origin': claim.name,
           # 'fiscal_position': claim.fiscal_position.id or False,
            'company_id': claim.company_id.id,
        }


    def action_refund_create(self, cr, uid, ids, context=None):
        """Generates invoice for given ids of purchase orders and links that invoice ID to purchase order.
        :param ids: list of ids of purchase orders.
        :return: ID of created invoice.
        :rtype: int
        """
        context = dict(context or {})
        
        inv_obj = self.pool.get('account.invoice')
        inv_line_obj = self.pool.get('account.invoice.line')

        res = False
        uid_company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        for claim in self.browse(cr, uid, ids, context=context):
            context.pop('force_company', None)
            if claim.company_id.id != uid_company_id:
                #if the company of the document is different than the current user company, force the company in the context
                #then re-do a browse to read the property fields for the good company.
                context['force_company'] = claim.company_id.id
                claim = self.browse(cr, uid, claim.id, context=context)
            
            # generate invoice line correspond to PO line and link that to created invoice (inv_id) and PO line
            inv_lines = []
            for line in claim.claim_return_lines:
                acc_id = self._choose_account_from_return_line(cr, uid, line, context=context)
                inv_line_data = self._prepare_return_inv_line(cr, uid, acc_id, line, context=context)
                inv_line_id = inv_line_obj.create(cr, uid, inv_line_data, context=context)
                inv_lines.append(inv_line_id)
                line.write({'refund_invoice_lines': [(4, inv_line_id)]})

            # get invoice data and create invoice
            inv_data = self._prepare_refund_invoice(cr, uid, claim, inv_lines, context=context)
            inv_id = inv_obj.create(cr, uid, inv_data, context=context)

            # compute the invoice
            inv_obj.button_compute(cr, uid, [inv_id], context=context, set_total=True)

            # Link this new invoice to related purchase order
            claim.write({'invoice_ids': [(4, inv_id)]})
            res = inv_id

        view_ref = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'invoice_form')
        view_id = view_ref and view_ref[1] or False,

        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer Refund'),
            'res_model': 'account.invoice',
            'context': {},
            'res_id': inv_id,
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'nodestroy': True,
        }

    ###############  Charge Functions  ##################
    def _make_charge_invoice(self, cr, uid, claim, lines, context=None):
        inv_obj = self.pool.get('account.invoice')
        obj_invoice_line = self.pool.get('account.invoice.line')
        if context is None:
            context = {}
	#Find invoiced lines from an existing claim
        invoiced_claim_delivery_line_ids = self.pool.get('crm.claim.line').search(cr, uid, [('claim', '=', claim.id), ('invoiced', '=', True), ('type', '=', 'delivery')], context=context)
        from_line_invoice_ids = []
	#Iterate over all invoice lines from each found claim line
        for claim_delivery_lines_invoiced in self.pool.get('crm.claim.line').browse(cr, uid, invoiced_claim_delivery_line_ids, context=context):
            for invoice_line in claim_delivery_lines_invoiced.charge_invoice_lines:
                if invoice_line.invoice_id.id not in from_line_invoice_ids:
                    from_line_invoice_ids.append(invoice_line.invoice_id.id)

	#For each existing invoice
        for preinv in claim.invoice_ids:
            if preinv.state not in ('cancel',) and preinv.id not in from_line_invoice_ids:
		#for each invoice line in an invoice
                for preline in preinv.invoice_line:
                    inv_line_id = obj_invoice_line.copy(cr, uid, preline.id, {'invoice_id': False, 'price_unit': -preline.price_unit})
                    lines.append(inv_line_id)

        inv = self._prepare_charge_invoice(cr, uid, claim, lines, context=context)
        inv_id = inv_obj.create(cr, uid, inv, context=context)
        inv_obj.button_compute(cr, uid, [inv_id])

        return inv_id


    def action_charge_invoice_create(self, cr, uid, ids, states=None, date_invoice = False, context=None):
        if states is None:
            states = ['draft', 'confirmed', 'done', 'exception']

        res = False
        invoices = {}
        invoice_ids = []
        invoice = self.pool.get('account.invoice')
        claim_line_obj = self.pool.get('crm.claim.line')
        partner_currency = {}
        # If date was specified, use it as date invoiced, usefull when invoices are generated this month and put the
        # last day of the last month as invoice date
        if date_invoice:
            context = dict(context or {}, date_invoice=date_invoice)

        for claim in self.browse(cr, uid, ids, context=context):
            currency_id = claim.pricelist_id.currency_id.id
            if (claim.partner_id.id in partner_currency) and (partner_currency[claim.partner_id.id] <> currency_id):
                raise osv.except_osv(
                    _('Error!'),
                    _('You cannot group Claims having different currencies for the same partner.'))

            partner_currency[claim.partner_id.id] = currency_id
            lines = []
            for line in claim.claim_delivery_lines:
                if line.invoiced:
                    continue
                elif (line.state in states):
                    lines.append(line.id)

            created_lines = claim_line_obj.charge_invoice_line_create(cr, uid, lines)

            if created_lines:
                invoices.setdefault(claim.partner_billing_address.id or claim.partner_id.id, []).append((claim, created_lines))

        if not invoices:
            for claim in self.browse(cr, uid, ids, context=context):
                for i in claim.invoice_ids:
                    if i.state == 'draft':
                        return i.id

        for val in invoices.values():
            for claim, il in val:
                res = self._make_charge_invoice(cr, uid, claim, il, context=context)
                invoice_ids.append(res)
#                self.write(cr, uid, [claim.id], {'state': 'progress'})
                cr.execute('insert into crm_claim_invoice_rel (claim_id,invoice_id) values (%s,%s)', (claim.id, res))
                self.invalidate_cache(cr, uid, ['invoice_ids'], [claim.id], context=context)

	inv_id = res
        view_ref = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'invoice_form')
        view_id = view_ref and view_ref[1] or False,

        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer Invoie'),
            'res_model': 'account.invoice',
            'context': {},
            'res_id': inv_id,
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
            'nodestroy': True,
        }



    def _prepare_charge_invoice(self, cr, uid, claim, lines, context=None):
        """Prepare the dict of values to create the new invoice for a
           sales order. This method may be overridden to implement custom
           invoice generation (making sure to call super() to establish
           a clean extension chain).

           :param browse_record order: sale.order record to invoice
           :param list(int) line: list of invoice line IDs that must be
                                  attached to the invoice
           :return: dict of value to create() the invoice
        """
        if context is None:
            context = {}

        journal_ids = self.pool.get('account.journal').search(cr, uid,
            [('type', '=', 'sale'), ('company_id', '=', claim.company_id.id)],
            limit=1)

        if not journal_ids:
            raise osv.except_osv(_('Error!'),
                _('Please define sales journal for this company: "%s" (id:%d).') % (claim.company_id.name, claim.company_id.id))

        invoice_vals = {
            'name': claim.name,
	    'claim': claim.id,
            'origin': claim.name,
            'type': 'out_invoice',
            'reference': claim.name,
            'account_id': claim.partner_id.property_account_receivable.id,
            'partner_id': claim.partner_billing_address.id,
            'journal_id': journal_ids[0],
            'invoice_line': [(6, 0, lines)],
            'currency_id': claim.pricelist_id.currency_id.id,
            'comment': claim.description,
 #           'fiscal_position': claim.fiscal_position.id or claim.partner_id.property_account_position.id,
            'date_invoice': context.get('date_invoice', False),
            'company_id': claim.company_id.id,
            'user_id': claim.user_id and claim.user_id.id or False,
#            'section_id' : claim.section_id.id
        }

        # Care for deprecated _inv_get() hook - FIXME: to be removed after 6.1
#        invoice_vals.update(self._inv_get(cr, uid, order, context=context))
        return invoice_vals


class CrmClaimLine(osv.osv):
    _inherit = 'crm.claim.line'
    _columns = {
	'invoiced': fields.boolean('Invoiced'),
	'return_invoice_lines': fields.many2many('account.invoice.line', 'crm_claim_line_invoice_rel', 'claim_line_id', 'invoice_id', 'Invoice Lines', readonly=True, copy=False, domain=[('claim_return_line', '!=', False)]),
	'charge_invoice_lines': fields.many2many('account.invoice.line', 'crm_claim_line_invoice_rel', 'claim_line_id', 'invoice_id', 'Invoice Lines', readonly=True, copy=False, domain=[('claim_charge_line', '!=', False)]),

    }


    def charge_invoice_line_create(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        create_ids = []
        claims = set()
        for line in self.browse(cr, uid, ids, context=context):
            vals = self._prepare_claim_line_charge_invoice_line(cr, uid, line, False, context)
            if vals:
                inv_id = self.pool.get('account.invoice.line').create(cr, uid, vals, context=context)
                self.write(cr, uid, [line.id], {'charge_invoice_lines': [(4, inv_id)]}, context=context)
                claims.add(line.claim.id)
                create_ids.append(inv_id)
        # Trigger workflow events
#        for sale_id in sales:
 #           workflow.trg_write(uid, 'sale.order', sale_id, cr)
        return create_ids


    def _prepare_claim_line_charge_invoice_line(self, cr, uid, line, account_id=False, context=None):
        """Prepare the dict of values to create the new invoice line for a
           sales order line. This method may be overridden to implement custom
           invoice generation (making sure to call super() to establish
           a clean extension chain).

           :param browse_record line: sale.order.line record to invoice
           :param int account_id: optional ID of a G/L account to force
               (this is used for returning products including service)
           :return: dict of values to create() the invoice line
        """
        res = {}
        if not line.invoiced:
            if not account_id:
                if line.product:
                    account_id = line.product.property_account_income.id
                    if not account_id:
                        account_id = line.product.categ_id.property_account_income_categ.id
                    if not account_id:
                        raise osv.except_osv(_('Error!'),
                                _('Please define income account for this product: "%s" (id:%d).') % \
                                    (line.product.name, line.product.id,))
                else:
                    prop = self.pool.get('ir.property').get(cr, uid,
                            'property_account_income_categ', 'product.category',
                            context=context)
                    account_id = prop and prop.id or False

	    uosqty = line.order_qty
	    uos_id = line.product_uom.id
#            uosqty = self._get_line_qty(cr, uid, line, context=context)
 #           uos_id = self._get_line_uom(cr, uid, line, context=context)
            pu = 0.0
            if uosqty:
                pu = round(line.sale_price_unit * line.order_qty / uosqty,
                        self.pool.get('decimal.precision').precision_get(cr, uid, 'Product Price'))
 #           fpos = line.claim.fiscal_position or False
	    fpos = False
            account_id = self.pool.get('account.fiscal.position').map_account(cr, uid, fpos, account_id)
            if not account_id:
                raise osv.except_osv(_('Error!'),
                            _('There is no Fiscal Position defined or Income category account defined for default properties of Product categories.'))
            res = {
                'name': line.name,
                'sequence': line.sequence,
                'origin': line.claim.name,
                'account_id': account_id,
                'price_unit': pu,
                'quantity': uosqty,
                'discount': line.discount,
                'uos_id': uos_id,
                'product_id': line.product.id or False,
                'invoice_line_tax_id': [(6, 0, [x.id for x in line.tax_id])],
#                'account_analytic_id': line.claim.project_id and line.claim.project_id.id or False,
            }

        return res

