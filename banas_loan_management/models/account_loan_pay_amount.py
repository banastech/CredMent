from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountLoan(models.TransientModel):
    _name = 'account.loan.pay.amount'
    _description = 'Account Loan Pay Amount'

    loan_id = fields.Many2one(
        'banas.loan',
        required=True,
        readonly=True,

    )
    currency_id = fields.Many2one(
        'res.currency',
        related='loan_id.currency_id',
        readonly=True
    )
    cancel_loan = fields.Boolean(
        default=False,
        readonly = True
,    )
    date = fields.Date(required=True, default=fields.Date.today())
    # amount = fields.Monetary(
    #     currency_field='currency_id',
    #     string='Amount to reduce from Principal',
    # )
    fees = fields.Monetary(
        currency_field='currency_id',
        string='Bank fees'
    )
    interests_amount = fields.Monetary(
        currency_field='currency_id',
        string='Interest Charges',
    )

    advance_payment_method = fields.Selection(related='loan_id.company_id.advance_payment_method', readonly=True)
    amount = fields.Monetary(
        currency_field='currency_id',
        string='Payment Amount',
        required=True,
    )
    amount_total = fields.Monetary(compute='_total_amount',
        currency_field='currency_id',
        string='Amount to reduce from Principal'
    )
    amount_total_cancel = fields.Monetary(
        compute='_total_amount',
        currency_field='currency_id',
        string='Amount Total'
    )
    amount_total_debit = fields.Monetary(
        compute='_total_amount',
        currency_field='currency_id',
        string='Debit Note Amount Total'
    )
    payment_journal_id = fields.Many2one("account.journal", domain="[('type', 'in', ('cash', 'bank'))]", required=True)
    debit_note_remain_amount = fields.Monetary(related="loan_id.debit_note_remain_amount")
    debit_note_interest_amount = fields.Monetary(
        currency_field='currency_id',
        string='Debit Note Interest'
    )
    debit_note_amount = fields.Monetary(
        string='Debit note payment amount',
    )

    @api.onchange('debit_note_amount', 'date', 'amount')
    def onchange_dabit_note(self):
        if not self.date:
            self.interest_amount = 0
            return
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
            days = (self.date - debit.date_invoice).days /  self.loan_id.method_period
            if days > 0:
                interest_amount += self.loan_id.currency_id.round((residual * rate / 100)*days)
            if amount_done:
                break
        self.debit_note_interest_amount = interest_amount
        self._total_amount()


    @api.onchange('cancel_loan')
    def _onchange_cancel_loan(self):
        if self.cancel_loan:

            # self.amount = max(self.loan_id.line_ids.filtered(
            #     lambda r: not (r.move_ids or r.installment_invoice_id.payment_state=='paid') and not r.invoice_ids).mapped(
            #         'pending_principal_amount'
            #     )
            # )
            self.amount = max(self.loan_id.line_ids.filtered(
                lambda r: not (r.installment_invoice_id.payment_state=='paid')).mapped(
                    'pending_principal_amount'
                )
            )
            self.debit_note_amount = self.debit_note_remain_amount
        else:
            self._total_amount()

    @api.depends('date', 'amount', 'fees', 'interests_amount', 'debit_note_interest_amount')
    def _total_amount(self):
        for wiz in self:
            if wiz.cancel_loan:
                wiz.amount_total = wiz.amount
                wiz.amount_total_debit = wiz.debit_note_amount + wiz.debit_note_interest_amount
                wiz.amount_total_cancel = wiz.amount + wiz.interests_amount + wiz.fees + wiz.amount_total_debit
            elif wiz.amount:
                # wiz.amount_total_debit = wiz.debit_note_amount
                wiz.amount_total_debit = wiz.debit_note_amount + wiz.debit_note_interest_amount
                wiz.amount_total = wiz.amount - wiz.interests_amount - wiz.fees - wiz.amount_total_debit
                wiz.amount_total_cancel=0.0
            else:
                wiz.amount_total=0.0
                wiz.amount_total_cancel=0.0
                wiz.amount_total_debit=0.0


    @api.onchange('loan_id')
    def onchange_loan_id(self):
        prev_line = self.loan_id.line_ids.filtered(lambda r: r.state == 'done')
        if prev_line:
            sequence = prev_line.mapped('sequence')
            sequence = max(sequence)
            prev_line = self.loan_id.line_ids.filtered(lambda r: r.sequence == sequence)
            self.date = prev_line.date

    @api.onchange('date', 'amount')
    def _onchnage_amount(self):
        adv_repay_interest = self.loan_id.company_id.adv_pay_interest
        day_interest_rate = self.loan_id.company_id.day_interest_rate
        self.fees = 0
        self.interests_amount = 0
        if adv_repay_interest > 0:
            self.fees = (self.amount * adv_repay_interest) / 100

        line = self.loan_id.line_ids.filtered(lambda r: r.date == self.date)
        if not self.date and line:
            return
        if self.advance_payment_method == 'full':
            next_line = self.loan_id.line_ids.filtered(lambda r: r.date > self.date and not r.move_ids)
            if next_line:
                sequence = next_line.mapped('sequence')
                sequence = min(sequence)
                next_line = self.loan_id.line_ids.filtered(lambda r: r.sequence == sequence)
                self.interests_amount = next_line.interests_amount
        elif self.advance_payment_method == 'partial':
            prev_line = self.loan_id.line_ids.filtered(lambda r: r.date <= self.date)
            if prev_line:
                sequence = prev_line.mapped('sequence')
                sequence = max(sequence)
                prev_line = self.loan_id.line_ids.filtered(lambda r: r.sequence == sequence)
                days = (self.date-prev_line.date).days
                self.interests_amount = ((prev_line.final_pending_principal_amount*day_interest_rate)/100)*days

    def new_line_vals(self, sequence):
        if self.cancel_loan:
            amount = self.amount_total_cancel
        else:
            amount = self.amount
        return {
            'loan_id': self.loan_id.id,
            'sequence': sequence,
            'payment_amount': amount,
            'debit_note_payment_amount': self.debit_note_remain_amount,
            'rate': 0,
            'interests_amount': self.fees+self.interests_amount+self.amount_total_debit,
            'date': self.date,
            'type': 'advance',
            'advance_no': self.loan_id.total_advance+1
        }

    def create_debit_note_payment(self, new_line):
        payment_obj = self.env['account.payment']
        available_payment_method_ids = self.payment_journal_id.available_payment_method_ids
        invoices = self.loan_id.debit_note_ids.filtered(lambda i: i.payment_state=='not_paid')
        vals = {
            'partner_id': self.loan_id.partner_id.id,
            'journal_id': self.payment_journal_id.id,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'fees': self.debit_note_interest_amount,
            'amount': self.amount_total_debit,
            'ref': self.loan_id.name+'-DebitNote- '+str(new_line.sequence),
            'payment_method_id': available_payment_method_ids and available_payment_method_ids[0].id or False,
            'debit_note_loan_id': self.loan_id.id,
            'loan_line_id': new_line.id,
            'reconciled_invoice_ids': [(4, inv.id) for inv in invoices]
        }
        payment = payment_obj.with_context(force_save=True).create(vals)
        if self.debit_note_interest_amount > 0:
            move = self.env['account.move'].create(payment.penalty_move_vals())
            move.action_post()
            payment.write({'fees_move_id': move.id})
        payment.action_post()
        payment_account_id=payment.destination_account_id
        lines= self.env['account.move.line']
        lines |= invoices.line_ids.filtered(lambda line: line.account_id == payment_account_id  and not line.reconciled)
        lines |= payment.move_id.line_ids.filtered(lambda line: line.account_id == lines.account_id and not line.reconciled)
        return lines.reconcile()

    def create_payment(self, new_line):
        payment_obj = self.env['account.payment']
        available_payment_method_ids = self.payment_journal_id.available_payment_method_ids
        invoices_id = self.loan_id.line_ids.filtered(lambda i: i.type=='advance')
        invoices=invoices_id.installment_invoice_id
        vals = {
            'partner_id': self.loan_id.partner_id.id,
            'journal_id': self.payment_journal_id.id,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'amount': self.amount,
            'ref': self.loan_id.name+'-'+str(new_line.sequence),
            'payment_method_id': available_payment_method_ids and available_payment_method_ids[0].id or False,
            'loan_line_id': new_line.id,
        }
        payment = payment_obj.with_context(force_save=True).create(vals)
        payment.action_post()
        # new_line.check_move_amount()
        payment_account_id=payment.destination_account_id
        lines= self.env['account.move.line']
        lines |= invoices.line_ids.filtered(lambda line: line.account_id == payment_account_id  and not line.reconciled)
        lines |= payment.move_id.line_ids.filtered(lambda line: line.account_id == lines.account_id and not line.reconciled)
        return lines.reconcile()
        new_line.check_move_amount()
        

    def create_payment_cancel(self, new_line):
        payment_obj = self.env['account.payment']
        available_payment_method_ids = self.payment_journal_id.available_payment_method_ids
        invoices_id = self.loan_id.line_ids.filtered(lambda i: i.type=='advance')
        invoices=invoices_id.installment_invoice_id
        vals = {
            'partner_id': self.loan_id.partner_id.id,
            'journal_id': self.payment_journal_id.id,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'amount': self.amount_total_cancel,
            'ref': self.loan_id.name+'-'+str(new_line.sequence),
            'payment_method_id': available_payment_method_ids and available_payment_method_ids[0].id or False,
            'loan_line_id': new_line.id,
            'reconciled_invoice_ids': [(4, inv.id) for inv in invoices],
        }
        payment = payment_obj.with_context(force_save=True).create(vals)
        payment.action_post()
        # new_line.check_move_amount()
        

        payment_account_id=payment.destination_account_id
        lines= self.env['account.move.line']
        lines |= invoices.line_ids.filtered(lambda line: line.account_id == payment_account_id  and not line.reconciled)
        lines |= payment.move_id.line_ids.filtered(lambda line: line.account_id == lines.account_id and not line.reconciled)
        return lines.reconcile()
        # new_line.check_move_amount()

         
    def run(self):
        self.ensure_one()
        if self.loan_id.is_leasing:
            if self.loan_id.line_ids.move_filtered(
                    lambda r: r.date < self.date and not r.invoice_ids
            ):
                raise UserError(_('Some invoices are not created'))
            if self.loan_id.line_ids.filtered(
                    lambda r: r.date > self.date and r.invoice_ids
            ):
                raise UserError(_('Some future invoices already exists'))
        if self.loan_id.line_ids.filtered(
                lambda r: r.date <= self.date and not (r.installment_invoice_id.payment_state=='paid' or r.move_ids)
        ):
            raise UserError(_('Some moves are not created'))
        # if self.loan_id.line_ids.filtered(
        #         lambda r: r.date > self.date and r.move_ids
        # ):
        #     raise UserError(_('Some future moves already exists'))
        lines = self.loan_id.line_ids.filtered(
            lambda r: r.date > self.date).sorted('sequence', reverse=True)
        sequence = min(lines.mapped('sequence'))
        for line in lines:
            line.sequence += 1
            # line.write({'sequence': line.sequence + 1})
        self._cr.commit()
        old_line = lines.filtered(lambda r: r.sequence == sequence + 1)
        pending = old_line.pending_principal_amount
        if self.loan_id.currency_id.compare_amounts(self.amount, pending) == 1:
            raise UserError(_('Amount cannot be bigger than debt'))
        if self.loan_id.currency_id.compare_amounts(self.amount, 0) <= 0:
            raise UserError(_('Amount cannot be less than zero'))
        self.loan_id.periods += 1
        new_line = self.env['account.loan.line'].create(
            self.new_line_vals(sequence))
        new_line.long_term_pending_principal_amount = (
            old_line.long_term_pending_principal_amount)
        amount = self.loan_id.loan_amount
        for line in self.loan_id.line_ids.sorted('sequence'):
            if line.move_ids:
                amount = line.final_pending_principal_amount
            else:
                line.pending_principal_amount = amount
                if line.sequence != sequence:
                    line.rate = self.loan_id.rate_period
                    line.check_amount()
                amount -= line.payment_amount - line.interests_amount
        if self.loan_id.long_term_loan_account_id:
            self.loan_id.check_long_term_principal_amount()
        if self.loan_id.currency_id.compare_amounts(pending, self.amount) == 0:
            self.loan_id.write({'state': 'cancelled'})
        # payment_sms = "Hi %s, This message is to confirm that %s received advance payment #%s an amount Rs %s of loan #%s on %s. Thank you - %s"
        # date = format_date(self.env, self.date)
        # name = new_line.loan_id.partner_id.name.split(" ")[0]
        # payment_sms = payment_sms%(name,
        #         new_line.loan_id.company_id.name,
        #         format(new_line.advance_no, '05d'),
        #         new_line.payment_amount,
        #         new_line.loan_id.name, date,
        #         new_line.loan_id.company_id.name)
        # sms_obj = self.env['sms.api']
        # if self.loan_id.partner_id.mobile:
        #     sms_obj._send_sms(self.loan_id.partner_id.mobile, payment_sms)
        res = new_line.view_process_values()
        if self.cancel_loan:
            self.create_payment_cancel(new_line)
            self.loan_id.write({'state': 'cancelled'})
        else:
            self.create_payment(new_line)
            self.loan_id.write({'state': 'posted'})

        if self.amount_total_debit>0:
            self.create_debit_note_payment(new_line)
        if self.loan_id.pending_payment_amount == 0.0:
            self.loan_id.close()

        # for line in self.loan_id.line_ids.filtered(lambda l: l.state=='pending' and l.type=='instl'):
        #     line.installment_invoices()

        amount=self.loan_id.pending_principal_amount
        for line in self.loan_id.line_ids.filtered(lambda l: l.state=='pending' and l.type=='instl'):
            if line.move_ids:
                line.pending_principal_amount=amount
                line.check_amount()
                amount -= line.payment_amount - line.interests_amount
               
            line.installment_invoices()




