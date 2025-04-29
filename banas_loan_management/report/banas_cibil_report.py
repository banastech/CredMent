from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from odoo.tools.misc import get_lang
import base64
import json

class ResPartner(models.Model):
    _inherit = 'res.partner'
    _description = 'Loan Parnter'

    def cibil_report(self):
        context = {}
        action = self.env.ref('banas_loan_management.action_banas_cibil_report').sudo().read()[0]
        context = {
            'default_partner_id': self.id,

        }
        print(context)
        action['context'] = context
        action['view_mode'] = 'form'
        form_view = [(self.env.ref('banas_loan_management.view_banas_cibil_report_form').id, 'form')]
        action['views'] = form_view

        return action

   
class CreditReport(models.AbstractModel):
    _name = 'report.banas_loan_management.report_credit_report'
    _description = 'Credit Report'


    @api.model
    def _get_report_values(self, docids, data=None):
        print("........1...............de............")
        data = data or {}

        param_obj = self.env['ir.config_parameter'].sudo()
        credit_report_response = param_obj.get_param('sample.credit.report.response')

        logo = self.env.user.company_id
        logo=logo.favicon
        if logo :
            logo_base64 = base64.b64encode(logo).decode('utf-8')
        else:
            logo_base64 = None

        data = json.loads(credit_report_response).get('data')
        score = [data.get('jsonExperianReport').get('SCORE')]
        CreditProfileHeader = data.get('jsonExperianReport').get('CreditProfileHeader')
        Credit_Account = data.get('jsonExperianReport').get('CAIS_Account').get('CAIS_Summary').get('Credit_Account')
        Total_Outstanding_Balance = data.get('jsonExperianReport').get('CAIS_Account').get('CAIS_Summary').get('Total_Outstanding_Balance')
        TotalCAPS_Summary = data.get('jsonExperianReport').get('TotalCAPS_Summary')
        NonCreditCAPS_Summary = data.get('jsonExperianReport').get('NonCreditCAPS').get('NonCreditCAPS_Summary')
        CAIS_Account_DETAILS = data.get('jsonExperianReport').get('CAIS_Account').get('CAIS_Account_DETAILS')
        Current_Application = data.get('jsonExperianReport').get('Current_Application').get('Current_Application_Details').get('Current_Applicant_Details')
        Current_Applicant_Address_Details = [data.get('jsonExperianReport').get('Current_Application').get('Current_Application_Details').get('Current_Applicant_Address_Details')]

        credit_data = {
            'score': score,
            'CreditProfileHeader': CreditProfileHeader,
            'Current_Application': Current_Application,
            'logo_base64': logo_base64,
            'Current_Application': Current_Application,
            'Current_Applicant_Address_Details':Current_Applicant_Address_Details,
            'Credit_Account': Credit_Account,
            'Total_Outstanding_Balance': Total_Outstanding_Balance,
            'TotalCAPS_Summary': TotalCAPS_Summary,
            'NonCreditCAPS_Summary': NonCreditCAPS_Summary,
            'CAIS_Account_DETAILS': CAIS_Account_DETAILS,
        }

        print("............credit_data................",credit_data)


        return {
            'doc_ids' : docids,
            'doc_model' : self.env['banas.cibil.report'],
            'credit_data' : credit_data,
            'docs' : self.env['banas.cibil.report'].browse(docids),
        }

class CibilReport(models.TransientModel):
    _name = 'banas.cibil.report'
    _description = 'Banas Cibil Report'

    partner_id = fields.Many2one('res.partner',string='Partners',readonly=True)

    def action_print_cibil_report(self):
        print(".................dee.............")

        param_obj = self.env['ir.config_parameter'].sudo()
        credit_report_response = param_obj.get_param('sample.credit.report.response')
     
        logo = self.partner_id.company_id
        logo=logo.favicon
        if logo :
            logo_base64 = base64.b64encode(logo).decode('utf-8')
        else:
            logo_base64 = None
        
        data = json.loads(credit_report_response).get('data')
        score = [data.get('jsonExperianReport').get('SCORE')]
        CreditProfileHeader =[data.get('jsonExperianReport').get('CreditProfileHeader')]
        Current_Application =[data.get('jsonExperianReport').get('Current_Application').get('Current_Application_Details').get('Current_Applicant_Details')]
        Current_Applicant_Address_Details =[data.get('jsonExperianReport').get('Current_Application').get('Current_Application_Details').get('Current_Applicant_Address_Details')]
        datas = {
            'score': score,
            'CreditProfileHeader': CreditProfileHeader,
            'logo_base64':logo_base64,
            'Current_Application':Current_Application,
            'Current_Applicant_Address_Details': Current_Applicant_Address_Details,
        }
        print (".....................", datas)
        return self.env.ref('banas_loan_management.action_report_credit_report').report_action(self, data=datas)



