from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from odoo.tools.misc import get_lang

class ReportPartnerLedger(models.TransientModel):
    _inherit = "account.report.partner.ledger"
    _description = "Account Partner Ledger"

    amount_currency = fields.Boolean("With Currency",
                                     help="It adds the currency column on report if the "
                                          "currency differs from the company currency.")
    partner_ids = fields.Many2many('res.partner', 'account_partner_ledger_partner_rel', 'account_report_id', 'partner_id', string='Partners')
    reconciled = fields.Boolean('Reconciled Entries' )
    loan_ids = fields.Many2many('banas.loan', 'account_partner_ledger_loan_rel', 'account_report_id', 'loan_id', string='Loans')

    def _build_contexts(self, data):
        result = super(ReportPartnerLedger, self)._build_contexts(data)
        result['loan_ids'] = self.loan_ids.ids or False
        result['partner_ids'] = self.partner_ids.ids
        return result


    def _print_report(self, data):
        data = self.pre_print_report(data)
        data['form'].update({'reconciled': self.reconciled, 'amount_currency': self.amount_currency,
            'partner_ids': self.partner_ids.ids, 'loan_ids': self.loan_ids.ids})    
        return self.env.ref('base_accounting_kit.action_report_partnerledger').report_action(self, data=data) 

   
    