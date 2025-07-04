from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

# class AccountChartTemplate(models.Model):
#     _inherit = 'account.chart.template'


#     def _prepare_all_journals(self, acc_template_ref, company, journals_dict=None):
#         res = super(AccountChartTemplate, self)._prepare_all_journals(
#             acc_template_ref, company, journals_dict=journals_dict)
#         res +=  [
#             {'type': 'sale', 'name': _('Processing Fees'), 'code': 'PROFE', 'company_id': company.id, 'show_on_dashboard': False,},
#             {'type': 'sale', 'name': _('Loans'), 'code': 'LOAN', 'company_id': company.id, 'show_on_dashboard': False,},
#             {'type': 'sale', 'name': _('Debit Notes'), 'code': 'DEBNT', 'company_id': company.id, 'show_on_dashboard': False,},
#             {'type': 'sale', 'name': _('Other Fees'), 'code': 'OTHFE', 'company_id': company.id, 'show_on_dashboard': False,},
#             {'type': 'purchase', 'name': _('Loan Expenses - Sales Persons'), 'code': 'EXPSAL', 'company_id': company.id, 'show_on_dashboard': False,},
#         ]
#         return res

from odoo import models, fields, _


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    property_account_debit_note_id = fields.Many2one('account.account.template', string='Debit Note Account')
    property_account_processing_fees_id = fields.Many2one('account.account.template', string='Processing Fees Account')
    property_account_other_fees_id = fields.Many2one('account.account.template', string='Other Fees Account')
    property_account_penalty_fee_id = fields.Many2one('account.account.template', string='Penalty Fee Account')

    def _get_journal_templates(self):
        self.ensure_one()
        return [
            {
                'name': _('Processing Fees'),
                'code': 'PROFE',
                'type': 'sale',
                'color': 11,
                'sequence': 5,
                'default_account_id': self.property_account_processing_fees_id.id
            },
            {
                'name': _('Loan Journal'),
                'code': 'ESP',
                'type': 'sale',
                'color': 11,
                'sequence': 5,
                'default_account_id': self.property_account_other_fees_id.id
            },
            {
                'name': _('Debit Notes'),
                'code': 'DEBNT',
                'type': 'sale',
                'color': 11,
                'sequence': 5,
                'default_account_id': self.property_account_debit_note_id.id
            },
            {
                'name': _('Other Fees'),
                'code': 'OTHFE',
                'type': 'sale',
                'color': 11,
                'sequence': 5,
                'default_account_id': self.property_account_other_fees_id.id
            },
            {
                'name': _('Penalty Fee'),
                'code': 'PNF',
                'type': 'sale',
                'color': 11,
                'sequence': 5,
                'default_account_id': self.property_account_penalty_fee_id.id
            },
            {
                'name': _('Loan Sales Person Journal'),
                'code': 'ESPs',
                'type': 'purchase',
                'color': 11,
                'sequence': 5,
                'default_account_id': self.property_account_other_fees_id.id
            },
        ]



class Company(models.Model):
    _inherit = 'res.company'
    adv_pay_interest = fields.Float("Advance Payment Interest Rate", default=3)
    processing_fees = fields.Float('Processing Fees (%)', required=True, default=2)
    advance_payment_method = fields.Selection([('partial', 'Interest of Days'), ('full', 'Interest of Month')], default='partial')
    day_interest_rate = fields.Float('Day Interest Rate(%)', digits=(8, 6), default=0.049315068)
    journal_processing_fee_id = fields.Many2one('account.journal', string="Processing Fee Journal", required=False)
    journal_loan_id = fields.Many2one('account.journal', string="Loan Journal", required=False , domain=[('type','=','sale')])
    journal_debit_id = fields.Many2one('account.journal', string="Debit Note Journal", required=False)
    journal_other_fee_id = fields.Many2one('account.journal', string="Other Fee Journal", required=False)
    sales_expense_journal_id = fields.Many2one('account.journal', string="Sales Expense Journal", required=False)
    interest_revenue_account_id = fields.Many2one('account.account', string="Interest Account", required=False)
    transfer_account_id = fields.Many2one('account.account', string="Liquidity Account", required=False)
    penalty_account_id = fields.Many2one('account.account', string="Penalty Account", required=False)
    application_seq_id = fields.Many2one('ir.sequence', 'Application Sequence')
    loan_seq_id = fields.Many2one('ir.sequence', 'Loan Sequence')

    #Product Category
    # product_cat_service_id = fields.Many2one('product.category', string="Service Product Categ")
    # product_cat_gold_id = fields.Many2one('product.category', string="Gold Product Categ")

    #Products
    product_process_fee_id = fields.Many2one('product.product', string="Processing Fee Product")
    product_other_fee_id = fields.Many2one('product.product', string="Other Fee Product")
    product_sales_person_id = fields.Many2one('product.product', string="Sales Person Expense Product")
    product_debit_note_id = fields.Many2one('product.product', string="Debit Note Product")


    pan_number = fields.Char(related="partner_id.pan_number", readonly=False)
    cin_number = fields.Char(related="partner_id.cin_number", readonly=False)
    tan_number = fields.Char(related="partner_id.tan_number", readonly=False)
    date_of_registration = fields.Date(related="partner_id.date_of_registration", readonly=False)

class AccountJournal(models.Model):
    """Inheriting Account Journal Model"""
    _inherit = "account.journal"

    multiple_invoice_type = fields.Selection(
        [('text', 'Text'), ('watermark', 'Watermark')], required=True,
        default='text', string="Display Type")
    commission_percentage=fields.Float(string="Commission(%)")




