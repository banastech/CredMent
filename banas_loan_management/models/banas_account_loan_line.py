from odoo import api, fields, models, _
from datetime import datetime, timedelta, date

from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)
try:
    import numpy
except (ImportError, IOError) as err: 
    _logger.error(err)


class AccountLoanLine(models.Model):
    _name = 'account.loan.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Annuity'
    # _rec_name = 'name'
    _order = 'sequence asc'


    name = fields.Char(compute='_compute_name')
    seq_name = fields.Char(compute='_compute_name', string="Sequence")
    loan_id = fields.Many2one(
        'banas.loan',
        required=True,
        readonly=True,
        # ondelete='cascade',
    )
    is_leasing = fields.Boolean(related='loan_id.is_leasing', readonly=True, )
    loan_type = fields.Selection(related='loan_id.loan_type', readonly=True)
    loan_state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled'),
        ('closed', 'Closed'),
    ], related='loan_id.state', readonly=True, store=True, string = "Loan State")
    sequence = fields.Integer(required=True, readonly=True)
    date = fields.Date(
        required=True,
        readonly=True,
        help='Date when the payment will be accounted',
    )
    long_term_loan_account_id = fields.Many2one(
        'account.account',
        readonly=True,
        related='loan_id.long_term_loan_account_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='loan_id.currency_id',
    )
    rate = fields.Float(
        required=True,
        readonly=True,
        digits=(8, 6),
    )
    pending_principal_amount = fields.Monetary(
        currency_field='currency_id',
        readonly=True,
        help='Pending amount of the loan before the payment',
    )

    long_term_pending_principal_amount = fields.Monetary(
        currency_field='currency_id',
        readonly=True,
        help='Pending amount of the loan before the payment that will not be '
             'payed in, at least, 12 months',
    )
    payment_amount = fields.Monetary(
        currency_field='currency_id',
        readonly=True,
        help='Total amount that will be payed (Annuity)',
    )
    # delay_payment_amount = fields.Monetary(
    #     currency_field='currency_id',
    #     readonly=True,
    #     help='Total amount that will be payed (Annuity)',
    # )

    interests_amount = fields.Monetary(
        currency_field='currency_id',
        readonly=True,
        help='Amount of the payment that will be assigned to interests',
    )
    # delay_interests_amount = fields.Monetary(
    #     currency_field='currency_id',
    #     readonly=True,
    #     help='Amount of the payment that will be assigned to interests',
    # )
    # total_delay_interest = fields.Monetary(
    #     currency_field='currency_id',
    #     readonly=True,
    #     help='Total delay Interest',
    #     # related='loan_id.total_delay_interest',
    # )
    principal_amount = fields.Monetary(
        currency_field='currency_id',
        compute='_compute_amounts',
        help='Amount of the payment that will reduce the pending loan amount',
    )
    long_term_principal_amount = fields.Monetary(
        currency_field='currency_id',
        readonly=True,
        help='Amount that will reduce the pending loan amount on long term',
    )
    final_pending_principal_amount = fields.Monetary(
        currency_field='currency_id',
        compute='_compute_amounts',
        help='Pending amount of the loan after the payment',
    )
    move_ids = fields.One2many(
        'account.move',
        inverse_name='loan_line_id',
        domain="[('move_type', '=', 'entry')]",
    )
    has_moves = fields.Boolean(
        compute='_compute_has_moves'
    )
    invoice_ids = fields.One2many(
        'account.move',
        inverse_name='loan_line_id',
        domain="[('move_type', '=', 'out_invoice')]",
    )
    has_invoices = fields.Boolean(
        compute='_compute_has_invoices'
    )
    type = fields.Selection(
        [
            ('instl', 'Installment'),
            ('advance', 'Advance')
        ], string="Type", default='instl',required=True)
    instl_no = fields.Integer(string="Installment Number", required=True, readonly=True, default=0)
    advance_no = fields.Integer(string="Advance Number", required=True, readonly=True, default=0)

    _sql_constraints = [
        ('sequence_loan',
         'unique(loan_id, sequence)',
         'Sequence must be unique in a loan')
    ]
    partner_id = fields.Many2one(related="loan_id.partner_id", store=True)
    penalty_charges = fields.Monetary(
        currency_field='currency_id',
        string='Penalty Amount',
    )
    amount_total = fields.Monetary(
        currency_field='currency_id',
        compute='_compute_amounts',
        string='Received Amount',
    )
    state = fields.Selection([
        ('upcoming', 'Upcoming'),
        ('pending', 'Pending'),
        ('cancelled', 'Cancelled'),
        ('done', 'Received')], compute="_compute_state", string='Payment Status', default='upcoming', store=True)
    sms_upcomming = fields.Boolean(default=False)
    sms_payment = fields.Boolean(default=False)
    sms_due_payment1 = fields.Boolean(default=False)
    sms_due_payment2 = fields.Boolean(default=False)
    payment_ids = fields.One2many('account.payment', 'loan_line_id', string="Payments")
    has_payments = fields.Boolean(
        compute='_compute_has_payments'
    )
    code = fields.Char(compute='_get_code')
    debit_note_id = fields.Many2one('account.move', string="Debit Note")
    debit_note_payment_amount = fields.Monetary(
        currency_field='currency_id',
        string='Debit Note Payment',
        default=0,
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company.id,
    )
    debit_note_ids = fields.One2many('account.move', 'debit_loan_line_id', string="Debit Notes")
    installment_invoice_id = fields.Many2one('account.move', string="Invoice",domain="[('move_type', '=', 'out_invoice')]",)
    installment_invoice_date = fields.Date(related = 'installment_invoice_id.invoice_date')
    installment_payment_state = fields.Selection(related = 'installment_invoice_id.payment_state')
    # followup_line = fields.Many2one('followup.line', string ="Overdue")

    @api.depends('move_ids')
    def _compute_has_moves(self):
        for record in self:
            record.has_moves = bool(record.move_ids)

    @api.depends('invoice_ids')
    def _compute_has_invoices(self):
        for record in self:
            record.has_invoices = bool(record.invoice_ids)
    @api.depends('loan_id.name', 'sequence')
    def _compute_name(self):
        for record in self:
            if record.type == 'advance':
                record.name = '%s-Adv-%s' % (record.loan_id.name, format(record.advance_no, '03d'))
                record.seq_name = 'Adv-%s' % (format(record.advance_no, '03d'))
            else:
                record.seq_name = 'Instl-%s' % (format(record.instl_no, '03d'))
                record.name = '%s-Instl-%s' % (record.loan_id.name, format(record.instl_no, '03d'))
    @api.depends('payment_amount', 'interests_amount',
                 'pending_principal_amount', 'penalty_charges', 'installment_invoice_id.amount_total')
    def _compute_amounts(self):
        for rec in self: 
            rec.final_pending_principal_amount = (
                rec.pending_principal_amount - rec.payment_amount +
                rec.interests_amount
            )
            rec.principal_amount = rec.payment_amount - rec.interests_amount
            payment_amount = sum(rec.payment_ids.filtered(lambda p: p.state=='posted').mapped('amount'))
            if rec.type == 'instl':
                rec.amount_total = rec.installment_invoice_id.amount_total-rec.installment_invoice_id.amount_residual
                # rec.amount_total = sum(rec.payment_ids.mapped('amount'))
            elif rec.type == 'advance':
                rec.amount_total = sum(rec.payment_ids.mapped('amount'))


    def compute_amount(self):
        """
        Computes the payment amount
        :return: Amount to be payed on the annuity
        """
        # if self.sequence == 1 and self.loan_id.select_loan_date:
        #     # Calculate the payment as the principal amount per period + adjusted interest
        #     return (self.loan_id.fixed_amount+ self.interests_amount)
        if self.sequence == self.loan_id.periods:
            return (self.pending_principal_amount + self.interests_amount -
                    self.loan_id.residual_amount)
        if self.loan_type == 'fixed-principal' and self.loan_id.round_on_end:
            return self.loan_id.fixed_amount + self.interests_amount
        if self.loan_type == 'fixed-principal':
            return (
                self.pending_principal_amount -
                self.loan_id.residual_amount
            ) / (
                self.loan_id.periods - self.sequence + 1
            ) + self.interests_amount
        if self.loan_type == 'interest':
            return self.interests_amount
        if self.loan_type == 'advanceinterest':
            return self.interests_amount
        if self.loan_type == 'fixed-annuity' and self.loan_id.round_on_end:
            if self.loan_id.fixed_amount <  self.pending_principal_amount:
                return self.loan_id.fixed_amount
            else:
                return self.pending_principal_amount + self.interests_amount
        if self.loan_type == 'fixed-annuity':
            return self.currency_id.round(- numpy.pmt(
                self.loan_id.loan_rate() / 100,
                self.loan_id.periods - self.sequence + 1,
                self.pending_principal_amount,
                -self.loan_id.residual_amount
            ))

    def check_amount(self):
        """Recompute amounts if the annuity has not been processed"""
        # if self.move_ids or self.invoice_ids:
        #     raise UserError(_(
        #         'Amount cannot be recomputed if moves or invoices exists '
        #         'already'
        #     ))
        if self.loan_type == 'advanceinterest':
            if self.sequence == 1 and self.loan_id.select_loan_date:
                diff_days = self.date - self.loan_id.start_date
                day_rate = (self.loan_id.rate/365)*diff_days.days
                self.interests_amount = self.currency_id.round(self.pending_principal_amount * day_rate / 100)
                self.payment_amount = self.currency_id.round(self.compute_amount())
            elif self.sequence != self.loan_id.periods:
                self.interests_amount = (self.pending_principal_amount * self.loan_id.rate_period / 100)
                self.payment_amount = self.compute_amount()
            else:
                if self.sequence != self.loan_id.periods:
                    self.interests_amount = (self.pending_principal_amount * self.loan_id.rate_period / 100)
                self.payment_amount = self.compute_amount()
        elif (
            self.sequence == self.loan_id.periods and
            self.loan_id.round_on_end and
            self.loan_type == 'fixed-annuity'

        ):  
            if self.pending_principal_amount > 0:
                if self.sequence == 1 and self.loan_id.select_loan_date:
                    diff_days = self.date - self.loan_id.start_date
                    day_rate = (self.loan_id.rate/365)*diff_days.days
                    self.interests_amount = self.currency_id.round(self.pending_principal_amount * day_rate / 100)
                    self.payment_amount = self.currency_id.round(self.compute_amount())
                else:
                    self.interests_amount = self.currency_id.round(self.pending_principal_amount * self.loan_id.loan_rate() / 100)
                    self.payment_amount = self.currency_id.round(self.compute_amount())
            else:
                self.interests_amount = 0
                self.payment_amount = 0
        elif not self.loan_id.round_on_end:
            if self.sequence == 1 and self.loan_id.select_loan_date:
                diff_days = self.date - self.loan_id.start_date
                day_rate = (self.loan_id.rate/365)*diff_days.days
                self.interests_amount = self.currency_id.round(self.pending_principal_amount * day_rate / 100)
                self.payment_amount = self.currency_id.round(self.compute_amount())
            else:
                self.interests_amount = self.currency_id.round(
                    self.pending_principal_amount * self.loan_id.loan_rate() / 100)
                self.payment_amount = self.currency_id.round(self.compute_amount())
        else:
            if self.sequence == 1 and self.loan_id.select_loan_date:
                diff_days = self.date - self.loan_id.start_date
                day_rate = (self.loan_id.rate/365)*diff_days.days
                self.interests_amount = (self.pending_principal_amount * day_rate / 100)
                self.payment_amount = self.compute_amount()
            else:
                self.interests_amount = (self.pending_principal_amount * self.loan_id.loan_rate() / 100)
                self.payment_amount = self.compute_amount()

        


    def check_move_amount(self):
        """
        Changes the amounts of the annuity once the move is posted
        :return:
        """
        # self.ensure_one()
        # partner = self.loan_id.partner_id.with_context(
        #     force_company=self.loan_id.company_id.id)
        # interests_moves = self.move_ids.mapped('line_ids').filtered(
        #     lambda r: r.account_id == self.loan_id.interest_expenses_account_id
        # )
        # short_term_moves = self.move_ids.mapped('line_ids').filtered(
        #     lambda r: r.account_id == self.loan_id.short_term_loan_account_id
        # )
        # long_term_moves = self.move_ids.mapped('line_ids').filtered(
        #     lambda r: r.account_id == self.loan_id.long_term_loan_account_id
        # )
        # interest_debit_moves = self.move_ids.mapped('line_ids').filtered(
        #     lambda r: r.account_id == partner.property_account_receivable_id
        # )
        # self.long_term_principal_amount = (
        #     sum(long_term_moves.mapped('debit')) -
        #     sum(long_term_moves.mapped('credit'))
        # )
        # for line in self.payment_ids.filtered(lambda l: (l.state=='posted')):
        payment_amount = sum(self.payment_ids.mapped('amount'))   
        fixed_amount_interest = (self.has_payments and payment_amount) or self.loan_id.fixed_amount or self.interests_amount
        self.penalty_charges = sum(self.payment_ids.mapped('fees'))
        self.amount_total = payment_amount+self.penalty_charges
    def move_vals(self):
        return {
            'loan_line_id': self.id,
            'loan_id': self.loan_id.id,
            'date': self.date,
            'ref': self.name,
            'journal_id': self.loan_id.journal_id.id,
            'currency_id': self.currency_id.id,
            'line_ids': [(0, 0, vals) for vals in self.move_line_vals()]
        }

    def move_line_vals(self):
        vals = []
        partner = self.loan_id.partner_id.with_context(
            force_company=self.loan_id.company_id.id)
        vals.append({
            'account_id': partner.property_account_payable_id.id,
            'partner_id': partner.id,
            'credit': self.payment_amount,
            'debit': 0,
        })
        vals.append({
            'account_id': self.loan_id.interest_expenses_account_id.id,
            'credit': 0,
            'debit': self.interests_amount,
        })
        vals.append({
            'account_id': self.loan_id.short_term_loan_account_id.id,
            'credit': 0,
            'debit': self.payment_amount - self.interests_amount,
        })
        if self.long_term_loan_account_id and self.long_term_principal_amount:
            vals.append({
                'account_id': self.loan_id.short_term_loan_account_id.id,
                'credit': self.long_term_principal_amount,
                'debit': 0,
            })
            vals.append({
                'account_id': self.long_term_loan_account_id.id,
                'credit': 0,
                'debit': self.long_term_principal_amount,
            })
        return vals

    def invoice_vals(self):
        partner = self.loan_id.partner_id.with_context(
            force_company=self.loan_id.company_id.id)
        return {
            'loan_line_id': self.id,
            'loan_id': self.loan_id.id,
            'move_type': 'out_invoice',
            'partner_id': self.loan_id.partner_id.id,
            'invoice_date': self.date,
            'invoice_date_due': self.date,
            'ref': self.name,
            # 'account_id': partner.property_account_payable_id.id,
            'journal_id': self.loan_id.journal_id.id,
            'currency_id': self.currency_id.id,
            'company_id': self.loan_id.company_id.id,
            'invoice_line_ids': [(5, 0, 0)]+[(0, 0, vals) for vals in
                                 self.invoice_line_vals()]
        }

    def calclate_day_interest(self, payment_date=False):
        if not payment_date:
            payment_date = datetime.now()
        # if payment.loan_line_id and payment.payment_date:
        loan_date = fields.Date.from_string(self.date)
        payment_date = fields.Date.from_string(payment_date)
        fees = 0.0
        if payment_date > loan_date:
            date_difference = (payment_date - loan_date).days
            fees = date_difference * self.company_id.day_interest_rate
        return fees

    def invoice_line_vals(self):
        vals = list()
        product_tmpl_id = self.loan_id.type_id.product_tmpl_id
        vals.append({
            'product_id': product_tmpl_id.product_variant_id.id,
            # 'name': self.loan_id.product_id.name,
            'name': str(self.seq_name) + ': ' + str(product_tmpl_id.name),
            'quantity': 1,
            'price_unit': self.principal_amount,
            'account_id': self.loan_id.short_term_loan_account_id.id,
            'tax_ids': product_tmpl_id.taxes_id,
        })
        vals.append({
            'product_id': product_tmpl_id.product_variant_id.id,
            'name': str(self.seq_name) + ': ' + str(product_tmpl_id.name),
            'quantity': 1,
            'price_unit': self.interests_amount,
            # 'price_unit': self.delay_interests_amount,
            'account_id': self.loan_id.interest_expenses_account_id.id,
            'tax_ids': product_tmpl_id.taxes_id,
        })
        # fees = self.calclate_day_interest()
        # if fees:
        #     vals.append({
        #         'product_id': product_tmpl_id.product_variant_id.id,
        #         'name': str(self.seq_name) + ': ' + "Penalty",
        #         'quantity': 1,
        #         # 'price_unit': self.interests_amount,
        #         'price_unit': fees,
        #         'account_id': self.loan_id.penalty_account_id.id,
        #         'tax_ids': product_tmpl_id.taxes_id,
        #     })
        return vals

    def generate_move(self):
        """
        # return
        Computes and post the moves of loans
        :return: list of account.move generated
        """
        res = []
        for record in self:
            if not record.move_ids:
                if record.loan_id.line_ids.filtered(
                        lambda r: r.date < record.date and not r.move_ids
                ):
                    raise UserError(_('Some moves must be created first'))
                move = self.env['account.move'].create(record.move_vals())
                move.post()
                res.append(move.id)
        return res

    def generate_invoice(self):
        """
        Computes invoices of leases
        :return: list of account.move generated
        """
        res = []
        for record in self:
            # if not record.invoice_ids:
            if record.loan_id.line_ids.filtered(
                    lambda r: r.date < record.date and not r.invoice_ids
            ):
                raise UserError(_('Some invoices must be created first'))
            if not self.installment_invoice_id:
                invoice = self.env['account.move'].create(
                    record.invoice_vals())
                res.append(invoice.id)
            # else:
            #     self.installment_invoice_id.button_cancel()
            #     self.installment_invoice_id.button_draft()
            #     self.installment_invoice_id.write(
            #         record.invoice_vals())
            #     invoice = self.installment_invoice_id
                if record.loan_id.post_invoice:
                    invoice.action_post()
                    self.installment_invoice_id = invoice.id
        return res

    def view_account_values(self):
        """Shows the invoice if it is a leasing or the move if it is a loan"""
        self.ensure_one()
        if self.is_leasing:
            return self.view_account_invoices()
        return self.view_account_moves()

    def view_process_values(self):
        """Computes the annuity and returns the result"""
        previous_loan_line = self.env['account.loan.line'].search([
            ('loan_id', '=', self.loan_id.id),
            ('id', '<', self.id),
        ], order='id desc', limit=1)
        self.ensure_one()
        if not self.has_moves:
            self.generate_invoice()
            self.state='pending'
        elif self.has_moves:
            self.generate_invoice()
            self.state='pending'
            if previous_loan_line and previous_loan_line.state != 'done':
                raise ValidationError("Cannot proceed with payment. Previous loan installment is still pending.")
        return self.action_account_payments()



    def view_account_moves(self):
        self.ensure_one()
        action = self.env.ref('account.action_move_journal_line')
        result = action.sudo().read()[0]
        result['context'] = {
            'default_loan_line_id': self.id,
            'default_loan_id': self.loan_id.id
        }
        result['domain'] = [
            ('loan_line_id', '=', self.id),
            # ('loan_id', '=', self.loan_id.id),
            
        ]
        if len(self.move_ids) == 1:
            res = self.env.ref('account.move.form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = self.move_ids.id
        return result

    def view_account_invoices(self):
        self.ensure_one()
        action = self.env.ref('account.action_move_in_invoice_type')
        result = action.sudo().read()[0]
        result['context'] = {
            'default_loan_line_id': self.id,
            'default_loan_id': self.loan_id.id
        }
        result['domain'] = [
            ('loan_line_id', '=', self.id),
            ('move_type', '=', 'in_invoice')
        ]
        if len(self.invoice_ids) == 1:
            res = self.env.ref('account.move.form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = self.invoice_ids.id
        return result

    def _get_code(self):
        for line in self:
            line.code = format(line.sequence, '05d')

    @api.depends('payment_ids')
    def _compute_has_payments(self):
        for record in self:
            record.has_payments = bool(record.payment_ids)

    def action_account_payments(self):
        invoice_ids = self.installment_invoice_id.filtered(lambda inv: inv.state=='not_paid')
        # payment_amount = sum(invoice_ids.mapped('amount_total'))
        payment_amount = self.installment_invoice_id.amount_residual
        action = {
            'name': 'Account Payment Register',
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment.register',
            'view_mode': 'form',
            'view_id': self.env.ref('account.view_account_payment_register_form').id,
            'target': 'new',  # Open the form in a new window
            'context': {'active_model': 'account.move', 
                        'active_ids': self.installment_invoice_id.ids,
                        'default_loan_payment_type': 'installment',
                        'default_loan_line_id': self.id,
                        'default_partner_id': self.partner_id.id,
                        'default_partner_type': 'customer',
                        'search_default_inbound_filter': 1,
                        'default_payment_type': 'inbound',
                        'default_payment_date': datetime.now(),
                        'default_payment_amount': payment_amount,
                        # 'default_amount': payment_amount,
                        'default_fess': 0,
                        # 'default_invoice_ids': [(4, inv.id, None) for inv in invoice_ids],
                        }
        }
        return action

    def action_view_account_payments(self):
        payment_ids = self.payment_ids
        action = self.env.ref('account.action_account_payments').sudo().read()[0]
        action['context'] = {''}
        if len(payment_ids) > 1:
            action['domain'] = [('id', 'in', payment_ids.ids)]
        elif len(payment_ids) == 1:
            action['views'] = [(self.env.ref('account.view_account_payment_form').id, 'form')]
            action['res_id'] = payment_ids.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def installment_invoices_line(self, line):
        qty = 1
        product_tmpl_id = self.loan_id.type_id.product_tmpl_id
        invoice_line = self.env['account.move.line']
        interest_expenses_account_id = self.loan_id.interest_expenses_account_id
        data = [(5, 0, 0)]

        data.append((0, 0, {
            # 'name': self.seq_name+': '+product_tmpl_id.name,
            'name': str(self.seq_name) + ': ' + str(product_tmpl_id.name),
            # 'origin': self.seq_name,
            'product_uom_id': product_tmpl_id.uom_po_id.id,
            'product_id': product_tmpl_id.product_variant_id.id,
            'account_id': self.loan_id.short_term_loan_account_id.id,
            'price_unit': self.principal_amount,
            'quantity': qty,
            'discount': 0.0,
            'tax_ids': product_tmpl_id.taxes_id,
            'loan_id': self.loan_id.id,
            'loan_line_id': self.id
        }))
        data.append((0, 0, {
            # 'name': self.seq_name+': Interest'+product_tmpl_id.name,
            'name': str(self.seq_name) + ': Interest ' + str(product_tmpl_id.name),
            # 'origin': self.seq_name,
            'product_uom_id': product_tmpl_id.uom_po_id.id,
            'product_id': product_tmpl_id.product_variant_id.id,
            'account_id': interest_expenses_account_id.id,
            'price_unit': self.interests_amount,
            # 'price_unit': self.delay_interests_amount,
            'quantity': qty,
            'discount': 0.0,
            'tax_ids': product_tmpl_id.taxes_id,
            'loan_id': self.loan_id.id,
            'loan_line_id': self.id
        }))

        return data

    def installment_invoices(self):
        inv_obj = self.env['account.move']
        # if self.installment_invoice_id:
        #     self.installment_invoice_id.button_cancel()#action_invoice_cancel()
        #     self.installment_invoice_id.button_draft()#action_invoice_draft
            
            
        vals = {
            'partner_id': self.partner_id.id,
            'invoice_date': self.date,
            'ref': self.name,
            'move_type': 'out_invoice',
            # 'currency_id': self.loan_id.company_id.currency_id.id,
            'currency_id': self.currency_id.id,
            'company_id': self.loan_id.company_id.id,
            'loan_id': self.loan_id.id,
            'loan_line_id': self.id,
            'journal_id': self.loan_id.journal_id.id,
            'invoice_line_ids': self.installment_invoices_line(self)
        }
        if not self.installment_invoice_id:
            inv_id = inv_obj.create(vals)
            inv_id.action_post()
            self.installment_invoice_id = inv_id.id

        else: 
            self.installment_invoice_id.button_draft()
            self.installment_invoice_id.write(vals)
            self.installment_invoice_id.action_post()
            
 
       



    # @api.depends('instl_no', 'payment_amount', 'principal_amount')

    # def _compute_final_pending_principal_amount(self):
    #     for rec in self:
    #         next_installment = self.env['account.loan.line'].search([
    #             ('loan_id', '=', rec.loan_id.id),
    #             ('instl_no', '=', rec.instl_no + 1),
    #         ], limit=1)
    #         if next_installment:
    #             rec.final_pending_principal_amount = next_installment.pending_principal_amount
    #         else:
    #             rec.final_pending_principal_amount = 0.0

    
    @api.depends('payment_ids', 'installment_invoice_id.payment_state')
    def _compute_state(self):
        for rec in self:
            if rec.pending_principal_amount>0 and rec.installment_invoice_id.payment_state=='paid':
                rec.state = 'done'
            elif rec.type=='advance':
                rec.state = 'done'
            elif rec.pending_principal_amount == 0:
                rec.state = 'cancelled'
            # elif rec.installment_invoice_id.state =='cancel' :
            #     rec.state = 'cancelled'
            elif rec.installment_invoice_id.state =='posted' :
                rec.state = 'pending'
            else:
                rec.state = 'upcoming'


    # def update_follow_up_ids(self):
    #     print("---followup overdue cron")
    #     today = date.today()
    #     followup_lines = self.env['followup.line'].search([])
    #     loan_lines = self.search([])

    #     for loan_line in loan_lines:
    #         if loan_line.installment_invoice_id:
    #             invoice_date = loan_line.installment_invoice_id.invoice_date
    #             payment_state = loan_line.installment_invoice_id.payment_state

    #             if payment_state == 'paid':
    #                 loan_line.update({'followup_line': None})
    #                 continue

    #             if invoice_date and payment_state == 'not_paid':
    #                 days_passed = (today - invoice_date).days
    #                 matching_followup = followup_lines.filtered(lambda fl: fl.delay <= days_passed)
    #                 if matching_followup:
    #                     closest_followup = matching_followup.sorted(key=lambda fl: fl.delay, reverse=True)[0]
    #                     loan_line.update({'followup_line': closest_followup.id})


# class FollowupLine(models.Model):
#     _name = 'followup.line'
#     _inherit = 'followup.line'

#     loan_line_ids = fields.Many2many('account.loan.line', string="Loan Lines")

   