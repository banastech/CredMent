from odoo import fields, models,api

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    type_id = fields.Many2one('banas.loan.document.type', string='Loan Doc. Type')
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Very High')],
        string='Priority', default='1')

    gold_loan_id = fields.Many2one("banas.loan", string="Gold Loan")



class DocumentType(models.Model):
    _name = "banas.loan.document.type"
    _description = 'Document Type'
        
    name = fields.Char('Name', required=True)
    code = fields.Char("Code", required=True)    
    active = fields.Boolean("Active", default=True)


class Documents(models.Model):
    _name = 'banas.loan.document'
    _description = 'Loan Documents'

    _inherits = {
        'ir.attachment': 'ir_attachment_id',
    }
    _order = "priority desc, id desc"

    ir_attachment_id = fields.Many2one('ir.attachment', string='Related attachment', required=True, ondelete='cascade')
    active = fields.Boolean('Active', default=True)
    type_id = fields.Many2one('banas.loan.document.type', 'Loan Doc. Type', widget="selection", required=True)
    state = fields.Selection([
            ('draft','Draft'),
            ('apply','Under Verification'),
            ('done','Verified'),
            ('cancel','Cancel')], 'State', readonly=True)
    loan_id = fields.Many2one("banas.loan", string="Loan")
    gold_loan_id = fields.Many2one("banas.loan", string="Gold Loan")
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Low'),
        ('2', 'High'),
        ('3', 'Very High')], string="Priority", help='Gives the sequence order when displaying a list of MRP documents.')



class PartnerDocuments(models.Model):
    _name = 'banas.partner.document'
    _description = 'Partner Documents'

    _inherits = {
        'ir.attachment': 'ir_attachment_id',
    }
    _order = "priority desc, id desc"

    ir_attachment_id = fields.Many2one('ir.attachment', string='Related attachment', required=True, ondelete='cascade')
    active = fields.Boolean('Active', default=True)
    type_id = fields.Many2one('banas.loan.document.type', 'Document Type', widget="selection", required=True)
    state = fields.Selection([
            ('draft','Draft'),
            ('apply','Under Verification'),
            ('done','Verified'),
            ('cancel','Cancel')], 'State', readonly=True)
    partner_id = fields.Many2one("res.partner", string="Partner")
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Low'),
        ('2', 'High'),
        ('3', 'Very High')], string="Priority", help='Gives the sequence order when displaying a list of MRP documents.')

    # @api.onchange("type_id")
    # def onchange_type_id(self):
    #     if self.type_id:
    #         self.name = self.type_id.name
    #     else:
    #         self.name = ''

    

    