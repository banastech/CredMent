from odoo import api, fields, models,_
from odoo.exceptions import ValidationError,UserError
from email_validator import validate_email, EmailNotValidError
from datetime import datetime

PARTNER_TYPES = [
    ('contact', 'Contact'),
    ('customer', 'Customer'),
    ('vendor', 'Vendor'),
    ('rto_office', 'RTO Office'),
    ('salesperson', 'Salesperson'),
]


class Partner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'
    # _inherit = ['res.partner', 'approval.fields.method']

    partner_type = fields.Selection(PARTNER_TYPES, string="Partner Type", required=True,readonly=True, default='customer')
    type = fields.Selection(selection_add=[
            ('family', 'Family Member'),
            ('applicant', 'Applicant'),
            ('contact', 'Contact')], string='Contact Type', help="")
    individual_type = fields.Selection([
            ('family', 'Family Member'),
            ('contact', 'Contact')], string='Contact Type', default='family', help="")
    child_company_type = fields.Selection([
            ('applicant', 'Applicant'),
            ('contact', 'Contact')], string='Contact Type', default='applicant', help="")
    # parent_company_type = fields.Selection(related='parent_id.company_type', store=True)
    branch_ids = fields.Many2many("banas.res.branch", "res_partner_branch_rel", string="Branches",)
    rto = fields.Boolean('RTO Office')
    loan_ids = fields.One2many('banas.loan', 'partner_id', string="Loans")
    loan_count_num=fields.Integer(string="Loan Count" ,compute='compute_loan_count_num')
    create_date = fields.Datetime(
                        string = "Created on",
                        default = fields.Date.context_today,
                        required = False)
    write_date = fields.Datetime(
                        string = "Last Account Updated",
                        default = fields.Date.context_today,
                        required = False,
                        store=True,
                        compute='_compute_last_modified')
    first_name = fields.Char("First Name",store="True")
    middle_name = fields.Char("Middle Name" ,store="True")
    last_name = fields.Char("Last Name" ,store="True")
    gender = fields.Selection([
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other')
    ], string="Gender")
    date_of_birth = fields.Date("Date Of Birth")
    date_of_registration = fields.Date(related='date_of_birth', string="Registration Date", readonly=False)
    function = fields.Char("Position")
    marital_status = fields.Selection([
        ('Single', 'Single'),
        ('Married', 'Married'),
        ('Widowed', 'Widowed'),
        ('Separated', 'Separated'),
        ('Divorced', 'Divorced'),
    ], string="Marital Status", help="""
        1 - Single (This category includes persons who have never married)\n
        2 - Married (This category includes persons whose spouse is living.)\n
        3 - Widowed (This category includes persons who have lost their legally-married spouse through death and have not remarried.)
        4 - Separated (This category includes persons currently legally married but who are no longer living with their spouse.)
        5 - Divorced (This category includes persons who have obtained a legal divorce and have not remarried.)
    """)
    relationship_id = fields.Many2one('res.relationship', string="Relationship")
    document_ids = fields.One2many('banas.partner.document', 'partner_id', string='Identities Doc')
    date_approved = fields.Datetime("Approved Date", readonly=True)
    pan_number = fields.Char("PAN Number")
    cin_number = fields.Char("CIN Number")
    tan_number = fields.Char("TAN Number")
    aadhaar_number = fields.Char("Aadhaar Number")
    meter_number = fields.Char("Meter Number")
    ci_relation = fields.Char("CI Relation")
    voter_id_number = fields.Char("Voter ID No")
    ration_card_number = fields.Char("Ration Card No.")
    ci_number = fields.Char("CI No.")
    dl_number = fields.Char("DL No.")
    cibil_score=fields.Integer("Cibile Score")
    # credit_score=fields.Integer("Credit Score")
    # state = fields.Selection([
    #   ('draft', 'Draft'),
    #   ('approval_by_manager', 'Waiting Approval of Manager'),
    #   ('approved_by_manager', 'Approved by Manager'),
    #   ('rejected_by_manager', 'Rejected by Manager'),
        
    # ],default = 'draft',string = "States",required=False, track_visibility='onchange')
    # approval_ids = fields.One2many(
    #     'banas.engine.track',
    #     'approval_id',string = "approval id") 
    ref=fields.Char(string="Internal Reference")
    user_id = fields.Many2one('res.partner.category', string="Tags", store=False)
    company_id=fields.Many2one('res.company',string="Company")
    user_id=fields.Many2one('res.users',string="Sales Person")
    
    
    _sql_constraints = [
        ('aadhaar_number_uniq', 'unique (aadhaar_number)', 'The Aadhaar Number must be unique !'),
        ('pan_number_uniq', 'unique (pan_number)', 'The PAN Number must be unique !')
    ]

    @api.depends('parent_id', 'individual_type', 'child_company_type')
    def _get_compute_type(self):
        for child in self:
            if child.parent_id and child.parent_id.company_type == 'person':
                child.type = child.individual_type
            elif child.parent_id and child.parent_id.company_type == 'company':
                child.type = child.child_company_type
 
    
    # @api.onchange('first_name', 'middle_name', 'last_name')
    # def onchange_names(self):
    #     if not self.is_company:
    #         if self.first_name and self.middle_name and self.last_name:
    #             self.name =  _(("%s %s %s")%(self.first_name, self.middle_name, self.last_name))
    #         elif self.first_name and self.last_name:
    #             self.name =  _(("%s %s")%(self.first_name, self.last_name))
    #         else:
    #             self.name = self.first_name

    def compute_loan_count_num(self):
        for partner in self:
            partner.loan_count_num = len(partner.loan_ids)


    def action_create_loan(self):
        partner_id = self.id
        contact_id = self.child_ids and self.child_ids[0].id or False
        form_view_id = self.env.ref('banas_loan_management.view_banas_loan_form').id
        address = str(self.street) + ', '
        if self.street2:
            address += str(self.street2)

        # address += str(self.city) + str(self.state_id)

        #Trigger a warning message
        return {
            'name': 'abc',
            'view_mode': 'form',
            'res_model': 'banas.loan',
            'view_id': form_view_id,
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_partner_id': partner_id, 
                'default_contact_id': contact_id,
                'default_address': address,

            }
            
        }
    

    # def action_create_loan(self):
    #     context = {}
    #     # if not self.stage_id.final_stage:
    #     #     raise ValidationError(_("For loan creation you should approve customer."))

    #     action = self.env.ref('banas_loan_management.view_banas_loan_form').read()[0]
    #     action['context'] = {
    #         'default_partner_id': self.id,
    #         'default_contact_id': self.child_ids and self.child_ids[0].id or False
    #     }
    #     action['view_mode'] = 'form'
    #     form_view = [(self.env.ref('banas_loan_management.view_banas_loan_form').id, 'form')]
    #     if 'views' in action:
    #         action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
    #     else:
    #         action['views'] = form_view
    #     return action


    # def action_loan_count(self):
    #     context = {}
    #     # if not self.stage_id.final_stage:
    #     #     raise ValidationError(_("For loan creation you should approve customer."))

    #     action = self.env.ref('banas_loan_management.view_banas_loan_form').read()[0]
    #     context = {
    #         'default_partner_id': self.id,
    #         'default_contact_id': self.child_ids and self.child_ids[0].id or False
    #     }
        
    #     action['context'] = context
    #     loan_ids = self.loan_ids.ids
    #     if len(loan_ids) == 1:
    #         loan = loan_ids[0]
    #         action['res_id'] = loan
    #         action['view_mode'] = 'form'
    #         form_view = [(self.env.ref('banas_loan_management.view_banas_loan_form').id, 'form')]
    #         if 'views' in action:
    #             action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
    #         else:
    #             action['views'] = form_view
    #     else:
    #         action['view_mode'] = 'tree,form'
    #         action['domain'] = [('id', 'in', loan_ids)]
    #     return action


    @api.model
    def create(self, vals):
        if not vals.get('ref', ''):
            vals['ref'] = self.env['ir.sequence'].next_by_code('res.partner') or ''
        return super(Partner, self).create(vals)

    # @api.onchange('approval_stage_id')
    # def approval_date(self):
    #     stage_id = self.env.ref('banas_partner_approval.res_partner_stage_3')
    #     if self.approval_stage_id == stage_id:
    #         self.write({'date_approved': datetime.now()})


    # def action_approve(self):
    #     pass
    # #     for partner in self:
    # #         partner.states = "approval_by_manager"
    # #         track_vals = {
    # #             'approval_id': partner.id,
    # #             'name': 'Waiting Approval of Manager', 
    # #             'template_stage_id': "Waiting Approval of Manager", 
    # #             'is_approved': True,
    # #             'status': "approved"
    # #         }
    # #         self.env['banas.engine.track'].create(track_vals)

    # def action_approving(self):
    #     pass
    # #     for partner in self:
    # #         partner.states = "approved_by_manager"
    # #         partner.date_approved = fields.Datetime.now()
    # #         track_vals = {
    # #             'approval_id': partner.id,
    # #             'name': 'Approved by Manager',
    # #             'template_stage_id': "Approved by Manager", 
    # #             'is_approved': True,
    # #             'status': "approved"
    # #         }

    # #         self.env['banas.engine.track'].create(track_vals)
    # #         self.write({'date_approved': datetime.now()})
        

    # # def action_reject(self):
    # #     pass
    # #      for partner in self:
    # #         partner.states = "rejected_by_manager"
    # #         track_vals = {
    # #            'approval_id': partner.id,
    # #            'name': 'Rejected by Manager',  
    # #            'template_stage_id': "Rejected by Manager",
    # #            'is_rejected': True,
    # #            'status': "rejected"
    # #         }
    # #         self.env['banas.engine.track'].create(track_vals)
  
   
    def action_loan_count(self):
        self.ensure_one()
        return {
            'name': f'Banas Loans ({self.loan_count_num})',
            'type': 'ir.actions.act_window',
            'res_model': 'banas.loan',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
        }

    def archive_me(self):
        for x in self:
           # if x.states == "draft":
                x.sudo().write({"active": not x.active})
           # else:
              #  raise ValidationError("You can archive only  in draft")
   
    def _compute_last_modified(self):
        for record in self:
            record.write_date = fields.Datetime.now()

    # def partner_ledger(self):
    #     context = {}
    #     action = self.env.ref('base_accounting_kit.action_partner_leadger').sudo().read()[0]
    #     loan_ids = self.env['banas.loan'].search([('partner_id', 'in', self.ids)]).ids
    #     context = {

    #         'default_partner_ids':self.ids,
    #         'default_loan_ids': loan_ids,
    #     }

    #     action['context'] = context
    #     action['view_mode'] = 'form'
    #     form_view = [(self.env.ref('base_accounting_kit.account_report_partner_ledger_view').id, 'form')]
    #     action['views'] = form_view

    #     return action


class Relationship(models.Model):
    _name = 'res.relationship'
    _order = "sequence"
    _description = 'Relationship'

    sequence = fields.Integer("Sequence", default=10,)
    name = fields.Char("Relationship", required=True)
    active = fields.Boolean("Active", default=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.user.company_id.id,
    )


# class ResUsers(models.Model):
#     _inherit = 'res.users'

#     def _branches_count(self):
#         return self.env['banas.res.branch'].sudo().search_count([])

#     branch_ids = fields.Many2many("banas.res.branch", "branch_id",  string="Branches")
#     branch_id = fields.Many2one("banas.res.branch", string="Branch", required=False)
#     branches_count = fields.Integer(compute='_compute_branches_count', string="Number of Branches", default=_branches_count)

#     def _compute_branches_count(self):
#         branches_count = self._branches_count()
#         for user in self:
#             user.branches_count = branches_count





    