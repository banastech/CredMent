from odoo import api, fields, models, _

class Invoice(models.Model):
    _inherit = 'account.move'

    loan_id = fields.Many2one('banas.loan', string="Loan")
    loan_line_id = fields.Many2one(
        'account.loan.line',
        readonly=True,
        ondelete='restrict',
    )
    debit_loan_id = fields.Many2one('banas.loan', string="Debit Note Loan")
    debit_loan_line_id = fields.Many2one('account.loan.line', string="Debit Note Installment")
    user_id = fields.Many2one('res.users', string='Salesperson', default=lambda self: self.env.user.id)
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approval', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('posted', 'Posted'),
        ('sent', 'Sent'),
        ('reconciled', 'Reconciled'),
        ('cancel', 'Cancelled')], readonly=True, default='draft', copy=False, string="Status")

    def finalize_invoice_move_lines(self, move_lines):
        vals = super().finalize_invoice_move_lines(move_lines)
        if self.loan_line_id:
            ll = self.loan_line_id
            if (
                ll.long_term_loan_account_id and
                ll.long_term_principal_amount != 0
            ):
                vals.append((0, 0, {
                    'account_id': ll.loan_id.short_term_loan_account_id.id,
                    'credit': ll.long_term_principal_amount,
                    'debit': 0,
                }))
                vals.append((0, 0, {
                    'account_id': ll.long_term_loan_account_id.id,
                    'credit': 0,
                    'debit': ll.long_term_principal_amount,
                }))
        return vals

    # def _post(self, soft=True):
    #     res = super(Invoice, self)._post(soft=soft)
    #     for record in self:
    #         if record.loan_id:
    #             record.payment_state=='partial' and record.move_type==''

    #         # if record.loan_line_id:
    #         #     record.loan_id = record.loan_line_id.loan_id
    #         #     record.loan_line_id.check_move_amount()
    #         #     record.loan_line_id.loan_id.compute_posted_lines()
    #         # if record.loan_id.pending_payment_amount == 0.0:
    #         #     record.loan_id.close()
    #     return res
    # @api.model
    # def _post(self, soft=True):
    #     to_post = super(Invoice, self)._post(soft=soft) 
    #     for move in to_post:
    #         base_move_id=move.loan_id.credit_invoice_id
    #         loan_id = move.loan_id 
    #         if  base_move_id.move_type == 'out_refund' and base_move_id.payment_state == 'paid':
    #             loan_id.write({'state': 'posted'})
    #     return to_post

    @api.depends('amount_residual', 'move_type', 'state', 'company_id', 'payment_state')
    def _compute_payment_state(self):
        super(Invoice, self)._compute_payment_state()   
        for invoice in self:
            if invoice.move_type == 'out_refund':
                if invoice.loan_id:
                    if invoice.payment_state == 'partial':
                        invoice.loan_id.write({'state': 'payment'})
                    elif invoice.payment_state == 'paid':
                        invoice.loan_id.write({'state': 'posted'})
                        # invoice.loan_line_id.installment_invoices()
            elif invoice.move_type == 'out_invoice' or invoice.move_type=='entry':
                if invoice.loan_line_id:
                    invoice.loan_id = invoice.loan_line_id.loan_id
                    invoice.loan_line_id.check_move_amount()

    def action_register_payment(self):
        super(Invoice, self).action_register_payment()
        if self.loan_line_id and self.loan_id:
            loan_payment_type='installment'
            payment_amount = sum(self.mapped('amount_residual'))
        if self.loan_id:
            loan_payment_type='transfer'
            payment_amount = sum(self.mapped('amount_residual'))
        else:
            loan_payment_type=''
            payment_amount = ''


        return{
            'name': _('Register Payment'),
            'res_model': 'account.payment.register',
            'view_mode': 'form',
            'context': {
                'active_model': 'account.move',
                'active_ids': self.ids,
                'default_loan_id': self.loan_id.id, 
                'default_loan_line_id': self.loan_line_id.id,
                'default_debit_loan_line_id' :self.debit_loan_line_id.id,
                'default_invoice_move_id': self.id,
                'default_loan_payment_type':loan_payment_type,
                'default_payment_amount': payment_amount,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }



class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    loan_id = fields.Many2one('banas.loan', compute='get_loan', string="Loan", store=True)
    loan_line_id = fields.Many2one(
        'account.loan.line',
        readonly=True,
        ondelete='restrict',
    )

    @api.depends('move_id', 'payment_id', 'move_id')
    def get_loan(self):
        for move in self:
            if move.move_id.loan_id:
                move.loan_id = move.move_id.loan_id.id
            elif move.move_id.loan_line_id:
                move.loan_id = move.move_id.loan_line_id.loan_id.id
            elif move.payment_id.loan_id:
                move.loan_id = move.payment_id.loan_id.id
            elif move.payment_id.loan_line_id:
                move.loan_id = move.payment_id.loan_line_id.loan_id.id
            elif move.payment_id.loan_line_id:
                move.loan_id = move.payment_id.loan_line_id.loan_id.id
            elif move.move_id.loan_id:
                move.loan_id = move.move_id.loan_id.id
            elif move.move_id.debit_loan_id:
                move.loan_id = move.move_id.debit_loan_id.id
    # @api.model
    # def _query_get(self, domain=None):
    #     domain=domain or []
    #     if not isinstance(domain, (list, tuple)):
    #         domain = safe_eval(domain)

    #     tables, where_clause, where_clause_params = super(AccountMoveLine, self)._query_get(domain=domain)
    #     if self._context.get('loan_ids'):
    #         domain += [('loan_id', 'in', self._context['loan_ids'])]

    #     if self._context.get('partner_ids'):
    #         domain += [('partner_ids', 'in', self._context['partner_ids'])]
    #     where_clause = ""
    #     where_clause_params = []
    #     tables = ''
    #     if domain:
    #         query = self._where_calc(domain)

    #         # Wrap the query with 'company_id IN (...)' to avoid bypassing company access rights.
    #         self._apply_ir_rules(query)

    #         tables, where_clause, where_clause_params = query.get_sql()

    #     return tables, where_clause, where_clause_params


    # @api.model
    # def _query_get(self, domain=None):
    #     self.check_access_rights('read')

    #     context = dict(self._context or {})

    #     domain = domain or []
    #     if not isinstance(domain, (list, tuple)):
    #         domain = safe_eval(domain)

    #     date_field = 'date'
    #     if context.get('aged_balance'):
    #         date_field = 'date_maturity'
    #     if context.get('date_to'):
    #         domain += [(date_field, '<=', context['date_to'])]
    #     if context.get('date_from'):
    #         if not context.get('strict_range'):
    #             domain += ['|', (date_field, '>=', context['date_from']), ('account_id.user_type_id.include_initial_balance', '=', True)]
    #         elif context.get('initial_bal'):
    #             domain += [(date_field, '<', context['date_from'])]
    #         else:
    #             domain += [(date_field, '>=', context['date_from'])]

    #     if context.get('journal_ids'):
    #         domain += [('journal_id', 'in', context['journal_ids'])]

    #     if context.get('loan_ids'):
    #         domain += [('loan_id', 'in', context['loan_ids'])]
    #     if context.get('partner_ids'):
    #         domain += [('partner_id', 'in', context['partner_ids'])]

    #     state = context.get('state')
    #     if state and state.lower() != 'all':
    #         domain += [('move_id.state', '=', state)]

    #     if context.get('company_id'):
    #         domain += [('company_id', '=', context['company_id'])]

    #     if 'company_ids' in context:
    #         domain += [('company_id', 'in', context['company_ids'])]

    #     if context.get('reconcile_date'):
    #         domain += ['|', ('reconciled', '=', False), '|', ('matched_debit_ids.max_date', '>', context['reconcile_date']), ('matched_credit_ids.max_date', '>', context['reconcile_date'])]

    #     if context.get('account_tag_ids'):
    #         domain += [('account_id.tag_ids', 'in', context['account_tag_ids'].ids)]

    #     if context.get('account_ids'):
    #         domain += [('account_id', 'in', context['account_ids'].ids)]

    #     if context.get('analytic_tag_ids'):
    #         domain += [('analytic_tag_ids', 'in', context['analytic_tag_ids'].ids)]

    #     if context.get('analytic_account_ids'):
    #         domain += [('analytic_account_id', 'in', context['analytic_account_ids'].ids)]

    #     if context.get('partner_categories'):
    #         domain += [('partner_id.category_id', 'in', context['partner_categories'].ids)]

    #     where_clause = ""
    #     where_clause_params = []
    #     tables = ''
    #     if domain:
    #         query = self._where_calc(domain)

    #         # Wrap the query with 'company_id IN (...)' to avoid bypassing company access rights.
    #         self._apply_ir_rules(query)

    #         tables, where_clause, where_clause_params = query.get_sql()
    #     return tables, where_clause, where_clause_params

# class ApprovalDupeModel(models.AbstractModel):
#     _inherit = 'banas.approval.model'

#     # @api.depends('approval_ids', 'approval_stage_id', 'env.user')
#     def _compute_approval_button_visibility(self):
#         super(ApprovalDupeModel, self)._compute_approval_button_visibility()

#         # for rec in self:
#         #     if self.env.user.has_group("banas_loan_management.group_banas_loan_user"):
#         #         rec.approval_button_visibility = False
            

