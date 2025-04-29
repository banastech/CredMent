# -*- coding: utf-8 -*-
from datetime import datetime


from odoo import api, fields, models, _

class LoanStatement(models.AbstractModel):
	_name = 'report.banas_loan_management.action_report_loan_statement'
	_description = "This is Loan Statement report form"

	@api.model
	def _get_report_values(self, docids, data=None):

		docs = self.env['banas.loan'].browse(docids)
	
		return {
			'docids': docids,
			'data': data,
			'doc_model': 'account.loan.line',  
			'docs': docs,
		}

	
