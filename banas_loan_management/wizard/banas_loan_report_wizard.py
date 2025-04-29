from odoo import api, fields, models
import base64 
TYPES = [
    ('cooperative_officer', 'Cooperative Officer'),
    ('statement', 'Loan Statement')
]


class LoanReportWizard(models.TransientModel):
    _name = 'banas.loan.report.wizard'
    _description = 'Loan Report Wizard'

    type = fields.Selection(
        TYPES,
        string="Select Report",
        required=True,
        default ="statement"
    )
    branch_id = fields.Many2one('banas.res.branch', required=False)
    loan_ids = fields.Many2many('banas.loan', 'account_loan_report_wizard_rel', 'wiz_id', 'loan_id', string="Loans", default=lambda self: self._context.get('active_ids', []))
    statement_type = fields.Selection([('all', 'All'), ('installment', 'Installments'), ('date', 'Dates Range')], string="Statement Type", default='all')
    installment_from = fields.Integer("Installment from")
    installment_to = fields.Integer("Installment to")
    date_start = fields.Date("Date from")
    date_end= fields.Date("Date to")


    def action_print_statement(self):
        loans = self.env['banas.loan'].search_read([('id', 'in', self.loan_ids.ids)])
        # selected_loan_ids = self.loan_ids.ids
        if self.loan_ids:
            selected_loan_ids = self.loan_ids.ids
        else:
            selected_loan_ids = []
        # print(self.loan_ids.partner_id.address,"----------")
        
        if self.statement_type == 'installment':
            installment_from = self.installment_from
            installment_to = self.installment_to
            lines = self.env['account.loan.line'].search_read([
                ('loan_id', 'in', selected_loan_ids),
                ('instl_no', '>=', installment_from),
                ('instl_no', '<=', installment_to),
            ])
        elif self.statement_type == 'date':
            date_start = self.date_start
            date_end = self.date_end
            lines = self.env['account.loan.line'].search_read([
                ('loan_id', 'in', selected_loan_ids),
                ('date', '>=', date_start),
                ('date', '<=', date_end), ])
        else:
            lines = self.env['account.loan.line'].search_read([('loan_id', 'in', selected_loan_ids)])
            # print(lines[0].payment_ids[0].date,"-------")

        lines_per_page = 28
        paginated_lines = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)]

        try:
            form_data = self.sudo().read()[0]
            print("✅ Form data read:", form_data)
        except Exception as e:
            print("❌ Error reading form data:", e)
            form_data = {}

        # Safe data packaging
        data = {
            'form': form_data,
            'loans': loans,
            'lines': lines
        }

        # data = {
        #     'form': self.sudo().read()[0],
        #     'loans': loans,
        #     'lines': lines
        # }
        print(type(lines),loans)
        return self.env.ref('banas_loan_management.action_report_loan_statement').report_action(self, data=data)





 
    # def action_print_statement(self):
    #     ctx = self._context.copy()
    #     loans = self.env['banas.loan'].browse(self._context.get('active_ids'))
    #     ctx.update({
    #         'discard_logo_check': True
    #     })
    #     return self.env.ref('banas_loan_management.action_report_loan_statement')\
    #         .with_context(ctx).report_action(self)


    # def installments_group_by_page(self, loan):
    #     values = {}
    #     sr = 1
    #     page = 1
    #     additional_pending_amount = 0
    #     line_ids = self.env['account.loan.line']
    #     if self.statement_type == 'installment':
    #         line_ids = loan.line_ids.filtered(lambda l: l.sequence >= self.installment_from and l.sequence <= self.installment_to)
    #         additional_pending_amount = loan.line_ids.filtered(lambda l: l.sequence >= self.installment_from)
    #         additional_pending_amount = sum(additional_pending_amount.mapped('payment_amount')) or 0.
    #     elif self.statement_type == 'date':
    #         line_ids = loan.line_ids.filtered(lambda l: l.date >= self.date_start and l.date <= self.date_end)
    #         additional_pending_amount = loan.line_ids.filtered(lambda l: l.date >= self.date_start)
    #         additional_pending_amount = sum(additional_pending_amount.mapped('payment_amount')) or 0.
    #     else:
    #         line_ids = loan.line_ids

    #     payment_amount = sum(line_ids.filtered(lambda r: r.payment_ids).mapped('payment_amount')) or 0.
    #     interests_amount = sum(line_ids.filtered(lambda r: r.payment_ids).mapped('interests_amount')) or 0.

    #     total_payment_amount = sum(line_ids.mapped('payment_amount')) or 0.
    #     debit_note_remain_amount = sum(line_ids.mapped('debit_note_ids').mapped('amount_residual'))
    #     if self.statement_type in ('installment', 'date'):
    #         pending_payment_amount = additional_pending_amount - payment_amount
    #     else:
    #         pending_payment_amount = (total_payment_amount + debit_note_remain_amount) - payment_amount


    #     for line in line_ids:
    #         if (sr%28) == 0:
    #             page += 1
    #         if page in values:
    #             values[page].append(line)
    #         else:
    #             values[page] = [line]
    #         sr += 1
    #     data = [values.items(),[payment_amount, interests_amount, pending_payment_amount]]
    #     return data


    
   