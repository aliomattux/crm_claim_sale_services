from openerp.osv import osv, fields
from openerp import api
from openerp.tools.translate import _

class StockPicking(osv.osv):
    _inherit = 'stock.picking'
    _columns = {
	'claim': fields.many2one('crm.claim', 'Claim'),
    }


    @api.cr_uid_ids_context
    def do_transfer(self, cr, uid, picking_ids, context=None):
        """Launch Create invoice wizard if invoice state is To be Invoiced,
          after processing the picking.
        """
        if context is None:
            context = {}
        res = super(StockPicking, self).do_transfer(cr, uid, picking_ids, context=context)
	for picking in self.browse(cr, uid, picking_ids):
	    if picking.claim:
		if picking.claim.claim_action in ['return', 'send_out']:
		    picking.claim.state = 'done'
		elif picking.claim.claim_action == 'exchange':
		    ex_complete = False
		    for claim_pick in picking.claim.pickings:
			if claim_pick.picking_type_id.code == 'incoming' and claim_pick.state == 'done':
			    ex_complete = True

		    if ex_complete:
			picking.claim.state = 'done'
		    else:
			picking.claim.state = 'partial'


class StockMove(osv.osv):
    _inherit = 'stock.move'
    _columns = {
	'claim_line_id': fields.many2one('crm.claim.line', 'Claim Line'),
    }
