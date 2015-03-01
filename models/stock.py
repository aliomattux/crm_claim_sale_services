from openerp.osv import osv, fields

class StockPicking(osv.osv):
    _inherit = 'stock.picking'
    _columns = {
	'claim': fields.many2one('crm.claim', 'Claim'),
    }

class StockMove(osv.osv):
    _inherit = 'stock.move'
    _columns = {
	'claim_line_id': fields.many2one('crm.claim.line', 'Claim Line'),
    }
