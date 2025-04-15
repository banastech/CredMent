from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError




class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    product_process_fee_id = fields.Many2one('product.product', string='Processing Fee Product', related='company_id.product_process_fee_id', readonly=False)
    product_other_fee_id = fields.Many2one('product.product', string='Other Fee Product', related='company_id.product_other_fee_id', readonly=False)
    product_sales_person_id = fields.Many2one('product.product', string='Sales person Expense Product', related='company_id.product_sales_person_id', readonly=False)
    product_debit_note_id = fields.Many2one('product.product', string='Debit Note Product', related='company_id.product_debit_note_id', readonly=False)

    journal_processing_fee_id = fields.Many2one('account.journal', string='Processing Fee Journal', related='company_id.journal_processing_fee_id', readonly=False)
    journal_loan_id = fields.Many2one('account.journal', string='Loan Journal', related='company_id.journal_loan_id', readonly=False)
    journal_debit_id = fields.Many2one('account.journal', string='Debit Note Journal', related='company_id.journal_debit_id', readonly=False)
    journal_other_fee_id = fields.Many2one('account.journal', string='Other Fee Journal', related='company_id.journal_other_fee_id', readonly=False)
    sales_expense_journal_id = fields.Many2one('account.journal', string='Sales person Expense Journal', related='company_id.sales_expense_journal_id', readonly=False)

    interest_revenue_account_id = fields.Many2one('account.account', string='Interest Account', related='company_id.interest_revenue_account_id', readonly=False)
    transfer_account_id = fields.Many2one('account.account', string='Liquidity Account', related='company_id.transfer_account_id', readonly=False)
    penalty_account_id = fields.Many2one('account.account', string='Penalty Account', related='company_id.penalty_account_id', readonly=False)
   
    application_seq_id = fields.Many2one('ir.sequence', string='Application Sequence', related='company_id.application_seq_id', readonly=False)
    loan_seq_id = fields.Many2one('ir.sequence', string='Loan Sequence', related='company_id.loan_seq_id', readonly=False)
