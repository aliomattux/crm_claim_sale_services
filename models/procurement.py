from openerp.osv import osv, fields

class ProcurementOrder(osv.osv):
    _inherit = 'procurement.order'
    _columns = {
        'claim_line_id': fields.many2one('crm.claim.line', 'CRM Claim Line'),
        'claim_id': fields.related('claim_line_id', 'claim_id', type='many2one', relation='crm.claim', string='Claim'),
    }
