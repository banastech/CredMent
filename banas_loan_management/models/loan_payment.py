from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from odoo.tools.misc import formatLang, format_date

PAYMENT_TYPES = [
    ('transfer', 'Transfer'),
    ('debit', 'Debit Note'),
    ('installment', 'Installment'),
    ('multi_installment', 'Multi Installment'),
    ('advance', 'Advance')
]

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    loan_id = fields.Many2one('banas.loan', string="Loan")
    debit_note_loan_id = fields.Many2one('banas.loan', string="Debit Loan")
    loan_line_id = fields.Many2one('account.loan.line', string="Loan Line")
    # approval_id = fields.Many2one("account.payment.approval", string="Approval Stage", readonly=True, copy=False)
    payment_amount = fields.Monetary(
        related=False,
        string='Installment amount', 
        readonly=True,
    )
    debit_note_amount = fields.Monetary(
        string='Debit note payment amount', readonly=False,
    )
    debit_note_remain_amount = fields.Monetary(
        related='loan_id.debit_note_remain_amount',
        string='Debit Note Remain', readonly=True,
    )
    fees = fields.Monetary(
        currency_field='currency_id',
        string='Bank fees',
    )
    fees_debit_note = fields.Boolean("Debit note against bank fees")
    fees_move_id = fields.Many2one('account.move', string="Fees Move")
    loan_payment_type = fields.Selection(PAYMENT_TYPES, string="Loan Payment Types")



class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    loan_id = fields.Many2one('banas.loan', string="Loan")
    debit_note_loan_id = fields.Many2one('banas.loan', string="Debit Loan")
    loan_line_id = fields.Many2one('account.loan.line', string="Loan Line")
    payment_amount = fields.Monetary(
        related='loan_line_id.payment_amount',
        string='Installment amount', 
        readonly=True,

    )
    debit_note_amount = fields.Monetary(
        string='Debit note payment amount', readonly=False,
    )
    debit_note_remain_amount = fields.Monetary(
        related='loan_id.debit_note_remain_amount',
        string='Debit Note Remain', 
        readonly=True,
    )
    fees = fields.Monetary(
        currency_field='currency_id',
        string='Bank fees',
        # compute='_compute_bank_fees'
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approval', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('posted', 'Posted'),
        ('sent', 'Sent'),
        ('reconciled', 'Reconciled'),
        ('cancelled', 'Cancelled')], readonly=True, default='draft', copy=False, string="Status")
    fees_debit_note = fields.Boolean("Debit note against bank fees")
    amount_in_words = fields.Char(compute='convert_amount_in_words', string="Amount in Words")
    fees_move_id = fields.Many2one('account.move', string="Fees Move")
    loan_payment_type = fields.Selection(PAYMENT_TYPES, string="Loan Payment Types")

    @api.onchange( 'payment_date')
    def _compute_bank_fees(self):
        for payment in self:
            if payment.loan_line_id and payment.payment_date:
                fees = payment.loan_line_id.calclate_day_interest(payment.payment_date)
                payment.fees = fees

    @api.onchange('payment_difference_handling')
    def _set_account_id(self):
        for account in self:
            if account.payment_difference_handling == 'reconcile' and account.fees > 0:
                account.writeoff_account_id = self.company_id.penalty_account_id
                account.writeoff_label=account.writeoff_account_id.name

    @api.onchange('loan_payment_type','payment_amount')
    def onchange_group_payment(self):
        for wizard in self:
            if wizard.loan_payment_type == 'multi_installment':
                wizard.group_payment = True
                

    @api.depends('early_payment_discount_mode')
    def _compute_payment_difference_handling(self):
        for wizard in self:
            if wizard.can_edit_wizard:
                wizard.payment_difference_handling = 'reconcile' if wizard.early_payment_discount_mode else 'open'
            if wizard.fees > 0:
                wizard.payment_difference_handling = 'reconcile'
            else:
                wizard.payment_difference_handling = False


    @api.depends('currency_id')
    def convert_amount_in_words(self):
        for payment in self:
            payment.amount_in_words = payment.currency_id.amount_to_text(payment.amount) if payment.currency_id else ''

    def _create_payment_vals_from_wizard(self, batch_result):
        vals = super(AccountPaymentRegister, self)._create_payment_vals_from_wizard(batch_result)
        vals.update({'loan_payment_type':self.loan_payment_type,
                      'loan_id':self.loan_id.id,
                      'loan_line_id':self.loan_line_id.id,
                      'payment_amount':self.payment_amount,
                      'debit_note_amount':self.debit_note_amount,
                      'debit_note_remain_amount':self.debit_note_remain_amount,
                      'fees':self.fees,
                      'debit_note_loan_id':self.debit_note_loan_id,
                      'fees_debit_note':self.fees_debit_note,
                      'fees_move_id':self.fees_move_id,})
        return vals

    @api.depends('fees','can_edit_wizard', 'source_amount', 'source_amount_currency', 'source_currency_id', 'company_id', 'currency_id', 'payment_date')
    def _compute_amount(self):
        total=super(AccountPaymentRegister,self)._compute_amount()
        if self.loan_id and self.loan_payment_type == 'multi_installment':
            lines = self.loan_id.line_ids.filtered(
            lambda r: r.date <= datetime.now().date()).sorted('sequence', reverse=True)
            if not self.fees_debit_note :
                # total = self.delay_payment_amount + self.fees
                total = self.payment_amount + self.fees
            else:
                # total = self.delay_payment_amount + self.fees
                total = self.payment_amount + self.fees
            return total
        if self.loan_line_id:
            total = self.loan_line_id.payment_amount-(self.loan_line_id.amount_total-self.loan_line_id.penalty_charges)
        if self.loan_payment_type == 'debit' and not self.fees_debit_note:
            total += self.fees

        return total
    


    @api.constrains('loan_payment_type')
    def check_loan_amounts(self):
        if self.loan_payment_type == 'transfer' and not self._context.get('force_save') and self.amount>self.loan_id.loan_amount:
            raise ValidationError(_('Payment not allowed more then loan amount.'))
        elif self.loan_payment_type == 'installment':
            if self.fees_debit_note:
                payment_amount = round(self.payment_amount, 2)
            else:
                payment_amount = round(self.payment_amount+(self.fees or 0), 2)
            if not self._context.get('force_save') and round(self.amount, 2) > payment_amount:
                raise ValidationError(_('Installment payment difference not allowed.'))
        elif self.loan_payment_type == 'debit' and self.debit_note_amount > self.debit_note_remain_amount:
            raise ValidationError(_('Debit note amount should not greater than debite note remain amount!'))

    def _prepare_invoice_line_for_fees(self):
        qty = 1
        debit_product = self.env.user.company_id.product_debit_note_id
        invoice_line = self.env['account.move.line']
        loan = self.loan_line_id.loan_id or self.loan_id
        account_id = invoice_line.with_context({'journal_id': loan.penalty_journal_id.id, 'type': 'out_invoice'}),
        data = []
        if not account_id:
            raise ValidationError(_("Default accounts not selected in debit journal!"))
        vals = {
            'name': str((self.communication or ''))+': '+str(debit_product and debit_product.name or ''),
            # 'origin': self.communication,
            'product_uom_id': debit_product.uom_po_id.id,
            'product_id': debit_product.id,
            'account_id': loan.penalty_account_id.id,
            'price_unit': self.fees,
            'quantity': 1,
            'discount': 0.0,
            'tax_ids': debit_product.taxes_id
        }

        if self.fees_debit_note:
            vals.update({
                'account_id': loan.debit_journal_id.default_account_id.id,
            })

        data.append((0, 0, vals))

        return data


    def create_fees_invoice(self):
        inv_obj = self.env['account.move']
        vals = {
            'partner_id': self.partner_id.id,
            'payment_reference': (self.communication or '')+'-'+'Penalty Fee',
            'move_type': 'out_invoice',
            'journal_id': self.loan_line_id.loan_id.penalty_journal_id.id,
            'currency_id': self.loan_line_id.currency_id.id,
            'company_id': self.company_id.id,
            'loan_id': self.loan_line_id.loan_id.id or self.loan_id.id or False, 
            'loan_line_id': self.loan_line_id.id or False,
            # 'debit_loan_line_id' : self.loan_line_id.loan_id.id or self.loan_id.id or False,
            'invoice_line_ids': self._prepare_invoice_line_for_fees()
        }
        if self.fees_debit_note:
            vals.update({
                'debit_loan_id': self.loan_line_id.loan_id.id or self.loan_id.id or False,
                'debit_loan_line_id': self.loan_line_id.id or False,
                'journal_id': self.loan_line_id.loan_id.debit_journal_id.id,
                'payment_reference': (self.communication or '')+'-'+'Debit Note',

            })
        inv_id = inv_obj.create(vals)
        inv_id.action_post()
        return inv_id

    def create_fees_invoice_multi_installment(self):
        inv_obj = self.env['account.move']
        vals = {
            'partner_id': self.partner_id.id,
            'payment_reference': self.communication+'-'+'Penalty Fee',
            'move_type': 'out_invoice',
            'journal_id': self.loan_id.penalty_journal_id.id,
            'currency_id': self.company_id.currency_id.id,
            'company_id': self.company_id.id,
            'debit_loan_id': self.loan_line_id.loan_id.id or self.loan_id.id or False,
            'invoice_line_ids': self._prepare_invoice_line_for_fees()
        }
        if self.fees_debit_note:
            vals.update({
                'journal_id': self.loan_line_id.loan_id.debit_journal_id.id,
                'payment_reference': self.communication+'-'+'Debit Note',

            })

        inv_id = inv_obj.create(vals)
        inv_id.action_post()


    def penalty_move_line_vals(self, loan_id=False, account_id=False):
        vals = []
        if not loan_id:
            loan_id = self.loan_line_id.loan_id
        if not account_id:
            account_id = loan_id.penalty_account_id
        partner = loan_id.partner_id.with_context(
            force_company=loan_id.company_id.id)
        vals.append({
            'account_id': partner.property_account_receivable_id.id,
            'credit': 0,
            'name': 'Penalty',
            'partner_id': partner.id,
            'debit': self.fees,
        })
        vals.append({
            'account_id': account_id.id,
            'credit': self.fees,
            'debit': 0,
        })
        return vals

    def penalty_move_vals(self, journal_id=False, account_id=False):
        loan_id = self.loan_id or self.loan_line_id.loan_id
        if not journal_id:
            journal_id = loan_id.journal_id
        return {
            'loan_line_id': self.loan_line_id.id,
            'loan_id': loan_id.id,
            'move_type':'entry',
            'date': self.payment_date,
            'payment_reference': (self.communication or '')+'-'+'Debit Note',
            'journal_id': journal_id.id,
            'line_ids': [(0, 0, vals) for vals in self.penalty_move_line_vals(loan_id, account_id)]
        }

    def action_create_payments(self):
        invoice = False
        if self.loan_payment_type == 'multi_installment':
            if self.fees > 0:
                if self.fees_debit_note:
                    invoice = self.create_fees_invoice()
                else:
                    # move = self.env['account.move'].create(self.penalty_move_vals())
                    # move.action_post()
                    invoice = self.create_fees_invoice()
            # self._post()
        elif self.loan_payment_type == 'installment':
                if self.fees > 0:
                    if self.fees_debit_note:
                        invoice = self.create_fees_invoice()
                    else:
                        # move = self.env['account.move'].create(self.penalty_move_vals())
                        # move.action_post()
                        invoice = self.create_fees_invoice()
                        available_lines = self.env['account.move.line']
                        for line in invoice.line_ids:
                            if line.move_id.state != 'posted':
                                raise UserError(_("You can only register payment for posted journal entries."))

                            if line.account_type not in ('asset_receivable', 'liability_payable'):
                                continue
                            if line.currency_id:
                                if line.currency_id.is_zero(line.amount_residual_currency):
                                    continue
                            else:
                                if line.company_currency_id.is_zero(line.amount_residual):
                                    continue
                            available_lines |= line
                        self.line_ids = [(4, line.id) for line in available_lines]
                        self.group_payment = True
        elif self.loan_payment_type == 'transfer':
            for line in self.loan_id.line_ids.filtered(lambda l: l.state=='pending'):
                line.view_process_values()
        return super(AccountPaymentRegister, self).action_create_payments()
    

    @api.onchange('debit_note_amount', 'payment_date')
    def onchange_debit_note_amount(self):
        if self.loan_payment_type != 'debit':
            return
        self.fees = 0
        self.amount = self.debit_note_amount
        if self.payment_date:
            debit_note_ids = self.loan_id.debit_note_ids.filtered(lambda inv: inv.state == 'open')
            amount = self.debit_note_amount
            interest_amount = 0
            rate = self.loan_id.rate / 365
            amount_done = False

            for debit in debit_note_ids:
                amount -= debit.residual
                if amount < 0:
                    residual = amount+debit.residual
                    amount_done = True
                else:
                    residual = debit.residual
                days = (self.payment_date - debit.date_invoice).days /  self.loan_id.method_period
                interest_amount += self.loan_id.currency_id.round((residual * rate / 100)*days)
                if amount_done:
                    break
            self.fees = interest_amount

            self.amount = self.debit_note_amount + self.fees

    

    @api.onchange('fees', 'fees_debit_note', 'payment_amount','loan_payment_type')
    def onchange_fees(self):
        if self.loan_payment_type in ['installment', 'multi_installment']:
            if not self.fees_debit_note :
                # self.amount = self.payment_amount+self.fees
                payment_amount = self.loan_line_id.installment_invoice_id.amount_residual
                self.amount = payment_amount
            else:
                self.amount = self.payment_amount
        elif self.loan_payment_type == 'debit':
            if self.fees_debit_note:
                self.amount = self.debit_note_amount
            else:
                self.amount = self.debit_note_amount+self.fees


    def post(self):
        """ Create the journal items for the payment and update the payment's state to 'posted'.
            A journal entry is created containing an item in the source liquidity account (selected journal's default_debit or default_credit)
            and another in the destination reconcilable account (see _compute_destination_account_id).
            If invoice_ids is not empty, there will be one reconcilable move line per invoice to reconcile with.
            If the payment is a transfer, a second journal entry is created in the destination journal to receive money from the transfer account.
        """
        for rec in self:
            if rec.state not in ('draft', 'approved'):
                raise UserError(_("Only a draft payment can be posted."))

            if any(inv.state != 'open' for inv in rec.invoice_ids):
                raise ValidationError(_("The payment cannot be processed because the invoice is not open!"))

            # keep the name in case of a payment reset to draft
            if not rec.name:
                # Use the right sequence to set the name
                if rec.payment_type == 'transfer':
                    sequence_code = 'account.payment.transfer'
                else:
                    if rec.partner_type == 'customer':
                        if rec.payment_type == 'inbound':
                            sequence_code = 'account.payment.customer.invoice'
                        if rec.payment_type == 'outbound':
                            sequence_code = 'account.payment.customer.refund'
                    if rec.partner_type == 'supplier':
                        if rec.payment_type == 'inbound':
                            sequence_code = 'account.payment.supplier.refund'
                        if rec.payment_type == 'outbound':
                            sequence_code = 'account.payment.supplier.invoice'
                rec.name = self.env['ir.sequence'].with_context(ir_sequence_date=rec.payment_date).next_by_code(sequence_code)
                if not rec.name and rec.payment_type != 'transfer':
                    raise UserError(_("You have to define a sequence for %s in your company.") % (sequence_code,))

            # Create the journal entry
            amount = rec.amount * (rec.payment_type in ('outbound', 'transfer') and 1 or -1)
            move = rec._create_payment_entry(amount)

            rec.write({'state': 'posted', 'move_name': move.name})
            if rec.loan_payment_type == 'transfer':
                if rec.loan_id.credit_invoice_id.state=='paid':
                    rec.loan_id.write({'state': 'posted'})
                for line in rec.loan_id.line_ids.filtered(lambda l: l.state=='pending'):
                    line.installment_invoices()
        return True

    def print_payment(self):
        if self.loan_id and self.loan_id.type_id.type == 'gold' and self.payment_type=='outbound' and self.partner_type=='customer':
            return self.env.ref('account.action_report_gold_deposit_receipt').with_context({'discard_logo_check': True}).report_action(self)
        else:
            return self.env.ref('account.action_report_payment_receipt').with_context({'discard_logo_check': True}).report_action(self)


  