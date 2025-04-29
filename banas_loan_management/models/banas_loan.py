from odoo import api, fields, models,_
from odoo.exceptions import UserError, ValidationError, AccessError
from datetime import datetime, timedelta
from odoo.tools.misc import formatLang, format_date
from dateutil.relativedelta import relativedelta
import numpy_financial 
from odoo.tools import float_utils
from lxml import etree
import numpy as np
from odoo.addons import decimal_precision as dp
import logging
from datetime import date


INTERVALS = [
    ('daily', 'Days(s)'),
    ('weekly', 'Week(s)'),
    ('monthly', 'Month(s)'),
    ('yearly', 'Year(s)'),
]
LOAN_TYPE = [
    ('vehicle', 'Vehicle'),
    ('gold', 'Gold'),
    ('personal', 'Personal'),
    ('other','Other')


]


_logger = logging.getLogger(__name__) 



class Vehicle(models.AbstractModel):
    _name = 'banas.loan.vehicle'
    _description = 'Vehicle'

    gold_image = fields.Binary('Jewellary Photo')

    rto_id = fields.Many2one('res.partner', string="RTO Office", domain=[('rto', '=', True)])
    reg_number = fields.Char('Reg. Number')
    chassis_number = fields.Char("Chassis Number")
    engine_number = fields.Char("Engine Number")    
    registered_owner_sign = fields.Binary('Registered Owner Sign')
    date_sign_of_owner = fields.Date('Registered Owner Sign Date')
    financier_sign = fields.Binary('Financier Sign')
    date_sign_of_financier = fields.Date('Financier Sign Date')
    date_endorsement = fields.Date('Hypothecation Endorsement Date')
    date_noc = fields.Date('NOC Date')
    noc_ref_number = fields.Char("NOC Ref. Number")
    noc_agreement_number = fields.Char("Agreement number")
    model_id = fields.Many2one('fleet.vehicle.model', string="Model")
    partner_bank_id = fields.Many2one('res.partner.bank', string="Bank")
    ownership_id = fields.Many2one('banas.loan.vehicle.ownership', string="New or 2nd Hand")
    wheel_base = fields.Char(related="model_id.wheel_base", string="Wheel Base", readonly=True)



class AccountLoan(models.Model):
    _name = 'banas.loan'
    _description = 'Loan'
    _inherit = ['mail.thread', 'mail.activity.mixin','banas.loan.vehicle']
    _rec_name = 'name'

    def _default_company(self):
        force_company = self._context.get('force_company')
        if not force_company:
            return self.env.company.id
        return force_company

    check_amount_in_words = fields.Char(
        string="Amount in Words",
        store=True,
        compute='_compute_check_amount_in_words',
    )


    name = fields.Char(
        string="Name",
        copy=False,
        required=True,
        readonly=True,
        default='/',
        # states={'draft': [('readonly', False)]},
    )
    contact_id = fields.Many2one("res.partner",string = "Contact")
    address=fields.Char(string="Address", store=True,)
    payment_partner_id = fields.Char( 
                        string = "Third party to pay")
    partner_id = fields.Many2one('res.partner',
        string = "Lender",
        required = True,
        readonly = True,
        help='Company or individual that lends the money at an interest rate.',
        states={'draft': [('readonly', False)]},
        
    )
    company_id = fields.Many2one('res.company',
            string = "Company",
            required = True,
            readonly = True,
            default=_default_company,
            states={'draft': [('readonly', False)]},
    )

    line_ids = fields.One2many(
        'account.loan.line',
        'loan_id',string = "line id",
        readonly=True,
        copy=False,
    )
    periods = fields.Integer(
        string ="Installment(s)",
        required = True,
        help = "number of period that loan will be last"
    )
    method_period = fields.Integer(
        string = "Installment Frequency ",
        default = 1,
        required = False,
        readonly=False,
        help ="state here the time between 2 depreciations , in months"
    )
    interval = fields.Selection(
        INTERVALS,
        string="Installment Interval",
        required=True,
        readonly=False,
        default='monthly'
    )
    start_date = fields.Date(
        string = "Loan Date",
        help = "Start of the moves",
        default = fields.Date.context_today,
        readonly=True,
    )
    rate = fields.Float(
        string = "Yearly Interest Rate",
        required=True,
        default=0.0,
        digits=(8, 6),
        track_visibility='always',
        help = "currently appied rate"
    )
    rate_period = fields.Float(
        string = "Rate Period ",
        compute='_compute_rate_period',
        digits=(8, 6),
        help = "real rate that will be applied on each period",
    )
    rate_type = fields.Selection(
        [
            ('napr', 'Nominal APR'),
            ('ear', 'EAR'),
            ('real', 'Real rate'),
        ],
        required=True,
        default='napr',
        readonly=True,
        help='Method of computation of the applied rate',
    )
    loan_type = fields.Selection(
        [
            ('fixed-annuity', 'Fixed Annuity'),
            ('fixed-principal', 'Fixed Principal'),
            ('interest', 'Only interest'),
            ('advanceinterest', 'Only interest + Advance'),
            ('flat-interest','Flat Interest')
        ],
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Method of computation of the period annuity',
        store=True,
        default='fixed-annuity',
    )
    fixed_amount = fields.Monetary(
        currency_field='currency_id',
        compute='_compute_fixed_amount',
    )

    fixed_loan_amount = fields.Monetary(
        currency_field='currency_id',
        readonly=True,
        copy=False,
        default=0,
    )
    fixed_periods = fields.Integer(
        readonly=True,
        copy=False,
        default=0,
    )
    loan_amount = fields.Monetary(
        currency_field='currency_id',
        required=True,
    )

    residual_amount = fields.Monetary(
        currency_field='currency_id',
        default=0.,
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Residual amount of the lease that must be payed on the end in '
             'order to acquire the asset',
    )
    round_on_end = fields.Boolean(
        default=True,
        help='When checked, the differences will be applied on the last period'
             ', if it is unchecked, the annuity will be recalculated on each '
             'period.',
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    payment_on_first_period = fields.Boolean(
        string = "Payment On First Period",
        help = "when it cheaked the first payment will be on start date"
    )

    currency_id = fields.Many2one(
        'res.currency',
        readonly=False,
        default= lambda self: self.env.company.currency_id,
    )
    journal_type = fields.Char(
        compute='_compute_journal_type'
    )
    journal_id = fields.Many2one('account.journal',
        string="Journal",
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        default=lambda self: self.env.company.journal_loan_id.id
    )
    short_term_loan_account_id = fields.Many2one('account.account',
        string = "Transfer account",
        domain="[('company_id', '=', company_id)]",
        required=True,
        readonly=True,
        help = "Account that will contain the pending amount on short term",
        default=lambda self: self.env.company.transfer_account_id.id
    )
    long_term_loan_account_id = fields.Many2one(
        'account.account',
        string='Long term account',
        help='Account that will contain the pending amount on Long term',
        domain="[('company_id', '=', company_id)]",
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    interest_expenses_account_id = fields.Many2one('account.account',
        string = "Interests account",
        domain="[('company_id', '=', company_id)]",
        required = True,
        help ="Account where the interests will be assigned",
        default=lambda self: self.env.company.interest_revenue_account_id.id
    )
    is_leasing = fields.Boolean(
        default=False,
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    leased_asset_account_id = fields.Many2one(
        'account.account',
        domain="[('company_id', '=', company_id)]",
        readonly=True,
        states={'draft': [('readonly', False)]},
    )
    product_id = fields.Many2one(
        'product.product',
        string='Loan product',
        help='Product where the amount of the loan will be assigned when the '
             'invoice is created',
    )
    interests_product_id = fields.Many2one(
        'product.product',
        string='Interest product',
        help='Product where the amount of interests will be assigned when the '
             'invoice is created',
    )
    interests_product_id = fields.Many2one(
        'product.product',
        string='Interest product',
        help='Product where the amount of interests will be assigned when the '
             'invoice is created',
    )
    move_ids = fields.One2many(
        'account.move',
        copy=False,
        inverse_name='loan_id'
    )
    pending_principal_amount = fields.Monetary(
        currency_field='currency_id',
        compute='_compute_total_amounts',
    )
    payment_amount = fields.Monetary(
        currency_field='currency_id',
        string='Total payed amount',
        compute='_compute_total_amounts',
    )
    interests_amount = fields.Monetary(
        currency_field='currency_id',
        string='Total interest paid',
        compute='_compute_total_amounts',
    )
    post_invoice = fields.Boolean(
        default=True,
        help='Invoices will be posted automatically'
    )
    total_instl = fields.Integer(compute='count_instl_adv', string="Total Installment", store=True)
    total_advance = fields.Integer(compute='count_instl_adv', string="Total Advance", store=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)',
         'Loan name must be unique'),
    ]

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approval', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('payment', 'Payments'),
        ('posted', 'Running'),
        ('cancelled', 'Cancelled'),
        ('closed', 'Closed'),
    ], required=True, copy=False, default='draft', track_visibility='onchange',
    )
    purpose = fields.Char('Purpose', required=True, default="2")
    date_application = fields.Date(
        string="Application Date",
        required=True,
        default=fields.Date.context_today,
        readonly=True,
        states={'draft': [('readonly', False)]}
    )
    start_date = fields.Date(
        string="Loan Date",
        required=True,
        default=fields.Date.context_today,
        readonly=True,
        states={'draft': [('readonly', False)]}
    )
    document_ids = fields.One2many('banas.loan.document', 'loan_id', 'Documents')
    gold_document_ids = fields.One2many('banas.loan.document', 'gold_loan_id', 'Jewellery Photograph')
    gaurenter_id = fields.Many2one('res.partner', 'First Gaurenter')
    gaurenter_id2 = fields.Many2one('res.partner', 'Second Gaurenter')
    contact_id = fields.Many2one(
        'res.partner',
        string='Contact',
        readonly=True,
        states={'draft': [('readonly', False)]}
    )
    payment_partner_id = fields.Many2one(
        'res.partner',
        string='Third party to pay',
        readonly=True,
        states={'draft': [('readonly', False)]}
    )
    repayment_type = fields.Selection([
       ('cash', 'By Cash'),
       ('cheque', 'By Transfer'),
       ('automatic', 'Automatic Payment')], 'Re-Payment Type')
    period_id = fields.Many2one('banas.loan.period',
        string='Loan Period',
        required=False,
        readonly=True,
        states={'draft': [('readonly', False)]}
    )
    type_id = fields.Many2one(
        'banas.loan.type',
        string='Loan Type',
        required=True,
        # readonly=True,
        domain="[('company_id', '=', company_id)]",
        states={'draft': [('readonly', False)]}
    )
    type = fields.Selection(related='type_id.type')
    application_number = fields.Char('Application Number', readonly=True)
    applied_amount = fields.Float('Applied Amount',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]}
    )
    fee_deduct_from_payment = fields.Boolean("Deduct From Payment", default=True)
    process_fee = fields.Float('Processing Fee', readonly=True,compute='compute_other_fees')
    other_fee = fields.Float('Other Fee',compute='compute_other_fees')
    installment = fields.Integer('Installments')
    interest_rate = fields.Float('Interest Rate')
    partner_id = fields.Many2one('res.partner',string="Customer")
    debit_journal_id = fields.Many2one(
        'account.journal',
        required=True,
        readonly=True,
        default=lambda self: self.env.company.journal_debit_id.id,
        states={'draft': [('readonly', False)]}
    )
    penalty_journal_id = fields.Many2one(
        'account.journal',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]}
    )
   
    sales_expense_journal_id = fields.Many2one('account.journal', string="Sale Person Expense Journal", default=lambda self: self.env.company.sales_expense_journal_id.id)
    sales_person_id = fields.Many2one('res.partner', "Sale Person")
    commission_percentage = fields.Float("Percentage" )
    credit_invoice_id = fields.Many2one('account.move', string="Invoice" ,readonly=True)
    fees_invoice_id = fields.Many2one('account.move', string="Fees Invoice")
    expense_invoice_ids = fields.One2many('account.move', 'loan_id', string="Expense Invoices", domain=[('move_type', '=', 'in_invoice')])
    invoice_count = fields.Integer(compute="_compute_invoice", string='# of Bills', copy=False, default=0, store=True)
    fee_invoice_ids = fields.One2many('account.move', 'loan_id', string="Fee Invoices", domain=[('move_type', '=', 'out_invoice')])
    fee_invoice_count = fields.Integer(compute="_compute_invoice", string='# of Invoice', copy=False, default=0, store=True)
    debit_note_count = fields.Integer(compute="_compute_invoice", string='# of Debit', copy=False, default=0, store=True)
    total_attachment = fields.Integer(compute='count_attachemnt', string="Total Attachment")
    # approval_id = fields.Many2one("banas.loan.approval", string="Approval Stage", readonly=True, copy=False)
    # approval_ids = fields.One2many(related="approval_id.approval_ids", readonly=True)
    total_payment_amount = fields.Monetary(
        currency_field='currency_id',
        string='Total Amount',
        compute='_compute_total_amounts',
    )

    pending_interests_amount = fields.Monetary(
        currency_field='currency_id',
        string='Pending Interest Amount',
        compute='_compute_total_amounts',
    )
    total_interests_amount = fields.Monetary(
        currency_field='currency_id',
        string='Total Interest Amount',
        compute='_compute_total_amounts',
    )
    pending_payment_amount = fields.Monetary(
        currency_field='currency_id',
        string='Total Pending Amount',
        compute='_compute_total_amounts',
    )

    interests_amount = fields.Monetary(
        currency_field='currency_id',
        string='Total interest paid',
        compute='_compute_total_amounts',
    )
    payment_ids = fields.One2many('account.payment', 'loan_id', string="Payments")
    payment_count = fields.Integer(compute="_compute_invoice", string='# of Payments', copy=False, default=0, store=True)
    payments_amount = fields.Monetary(
        currency_field='currency_id',
        string='Total Transfer Amount',
        compute='_compute_total_amounts',
    )

    penalty_account_id = fields.Many2one(
        'account.account',
        domain="[('company_id', '=', company_id)]",
        string='Penalty account',
        help='Account where the Penalty will be assigned to',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        default=lambda self: self.env.company.penalty_account_id.id,
    )

    journal_other_fee_id = fields.Many2one(
        'account.journal',
        string="Other Fees Journal",
        required=True,
        # readonly=True,
        states={'draft': [('readonly', False)]},
        default=lambda self: self.env.company.journal_other_fee_id.id
    )
    journal_processing_fee_id = fields.Many2one(
        'account.journal',
        string="Processing Fees Journal",
        required=True,
        # readonly=True,
        states={'draft': [('readonly', False)]},
        default=lambda self: self.env.company.journal_processing_fee_id.id
    )
    debit_note_ids = fields.One2many('account.move', 'debit_loan_id', string="Debit Notes" ,domain=[('move_type', '=', 'out_invoice')])
    debit_note_amount = fields.Monetary(
        currency_field='currency_id',
        string='Total Debit Note',
        compute='_compute_amounts',
    )
    debit_note_paid_amount = fields.Monetary(
        currency_field='currency_id',
        string='Debit note paid ',
        compute='_compute_amounts',
    )
    debit_note_remain_amount = fields.Monetary(
        currency_field='currency_id',
        string='Debit Note Remain',
        compute='_compute_total_amounts',
    )
    debit_note_interest_amount = fields.Monetary(
        currency_field='currency_id',
        string='Debit Note Interest ',
        compute='_compute_amounts',
    )
    # branch_id = fields.Many2one(
    #     "banas.res.branch",
    #     string="Branch",
    #     required=False,
    #     readonly=True,
    #     states={'draft': [('readonly', False)]},
    # )

    fund_type = fields.Selection([('company', 'Business'), ('individual', 'Individual')], string="Fund Type", required=1, default='individual')
    gold_ids = fields.One2many(
        "banas.gold.line",
        'loan_id',
        string="Gold Details",
        readonly=True,
        states={'draft': [('readonly', False)]}
    )
    date_maturity = fields.Date(compute='get_maturity_date', string="Maturity Date", store=True)
    asset_valuation = fields.Monetary(string="Assets Valuation")
    fees_ids = fields.One2many('banas.loan.fees', 'loan_id', string='Fees')
    date_application = fields.Datetime(
        string = "Application date",
        default = fields.Datetime.now,
        required = False
    )
    payment_id = fields.Many2one(
        'account.payment',
        string = "Payment",
    )
    debit_note_remain_amount = fields.Monetary(
        currency_field='currency_id',
        string='Debit Note Remain',
        compute='_compute_total_amounts',
    )
    gold_document_ids = fields.One2many(
        'banas.loan.document', 
        'gold_loan_id', 'Jewellery Photograph')

    gaurenter_id = fields.Many2one('res.partner',
                        string = "First Gaurenter")
    gaurenter_id2 = fields.Many2one('res.partner',
                        string = "Second Gaurenter")

    #------------select date for loan-------------
    select_loan_date = fields.Boolean(
        string = "Date (First Installment)",
        help = "when it cheaked the first loan will be start from this date"
    )
    first_installment_date = fields.Date(
        string="First Loan Date",
        required=True,
        default=fields.Date.context_today,
        readonly=True,
        states={'draft': [('readonly', False)]}
    )

    # total_delay_interest = fields.Monetary(
    #     currency_field='currency_id',
    #     readonly=True,
    #     digits=(8, 6),
    #     help='Total delay Interest',
    #     # compute='_compute_total_delay_interest'
    # )

    
    @api.depends('line_ids.instl_no', 'line_ids.advance_no')
    def count_instl_adv(self):
        for loan in self:
            loan.total_instl = len(loan.line_ids.filtered(lambda l: l.type=='instl'))
            loan.total_advance = len(loan.line_ids.filtered(lambda l: l.type=='advance'))

    @api.depends('line_ids', 'currency_id', 'loan_amount', 'payment_ids', 'debit_note_ids', 'line_ids.installment_invoice_id.payment_state')
    def  _compute_amounts(self):
        for record in self:
            record.debit_note_amount = sum(record.debit_note_ids.mapped('amount_total'))
            record.debit_note_paid_amount = record.debit_note_amount-record.debit_note_remain_amount
            record.debit_note_interest_amount = record._compute_debit_interest()



    @api.depends('line_ids', 'currency_id', 'loan_amount', 'payment_ids', 'debit_note_ids', 'line_ids.installment_invoice_id.payment_state')
    def _compute_total_amounts(self):
        for record in self:
            record.debit_note_remain_amount = sum(record.debit_note_ids.mapped('amount_residual'))

            lines = record.line_ids.filtered(lambda r: r.state=='done')

            record.total_payment_amount = sum(
                record.line_ids.mapped('payment_amount')) or 0.
            # record.payment_amount = sum(
            #     lines.mapped('amount_total')) or 0.
            record.payment_amount = sum(
                record.line_ids.mapped('amount_total')) or 0.

            # record.payment_amount = record.total_payment_amount - record.payment_amount
            record.pending_payment_amount = (record.total_payment_amount + record.debit_note_remain_amount) - record.payment_amount

            record.total_interests_amount = sum(
                record.line_ids.mapped('interests_amount')) or 0.

            record.interests_amount = sum(
                lines.mapped('interests_amount')) or 0.

            record.pending_interests_amount = record.total_interests_amount - record.interests_amount
            record.payments_amount = abs(sum(record.payment_ids.filtered(lambda p: p.id in record.payment_ids.ids and p.loan_payment_type == 'transfer').mapped('amount_signed')) or 0.)

            record.pending_principal_amount = (
                record.loan_amount -
                record.payment_amount +
                record.interests_amount
            )

    def get_interval_rate(self):
        if self.interval == 'daily':
            rate = 365
        elif self.interval == 'weekly':
            rate = 52.142857143
        elif self.interval == 'yearly':
            rate = 1
        else:
            rate = 12
        return rate

    def _compute_debit_interest(self):
        date = datetime.now()
        debit_note_ids = self.debit_note_ids.filtered(lambda inv: inv.payment_state == 'not_paid')
        interest_amount = 0
        rate = self.rate / 365
        payment_cal = True
        for debit in debit_note_ids:
            days = (date - fields.Datetime.from_string(debit.invoice_date)).days /  self.method_period
            interest_amount += self.currency_id.round((debit.amount_residual * rate / 100)*days)
        return interest_amount

    @api.model
    def compute_rate(self, rate, rate_type, method_period):
        """
        Returns the real rate
        :param rate: Rate
        :param rate_type: Computation rate
        :param method_period: Number of months between payments
        :return:
        """
        interval_unit = self.get_interval_rate()
        if rate_type == 'napr':
            return rate / interval_unit * method_period
        if rate_type == 'ear':
            return math.pow(1 + rate, method_period / interval_unit) - 1
        return rate


    @api.onchange('rate', 'periods', 'method_period', 'rate_type')
    def onchange_rate_period(self):
        for record in self:
            record.rate_period = record.loan_rate()

    # @api.onchange('select_loan_date','first_installment_date')
    # def _compute_total_delay_interest(self):
    #     for record in self:
    #         if self.select_loan_date == True:
    #             delta = self.installment_delta()
    #             adjusted_start_date = self.start_date + delta
    #             days_difference = (self.first_installment_date - adjusted_start_date).days
    #             one_day_interest = self.rate / 365
    #             record.total_delay_interest = (one_day_interest * days_difference)*100
    #             # record.total_delay_interest = (record.loan_amount * one_day_interest * days_difference) / 100
    #         else:
    #             record.total_delay_interest==0.0

    def loan_rate(self):
        return self.compute_rate(
            self.rate, self.rate_type, self.method_period
        )

    @api.depends('rate', 'method_period', 'rate_type', 'interval')
    def _compute_rate_period(self):
        for record in self:
            record.rate_period = record.loan_rate()

    @api.depends('journal_id', 'company_id')
    def _compute_currency(self):
        for rec in self:
            rec.currency_id = (
                rec.journal_id.currency_id or rec.company_id.currency_id)

    @api.depends('is_leasing')
    def _compute_journal_type(self):
        for record in self:
            if record.is_leasing:
                record.journal_type = 'purchase'
            else:
                record.journal_type = 'sale'
    @api.onchange('is_leasing')
    def _onchange_is_leasing(self):
        # self.journal_id = self.env['account.journal'].search([
        #     ('company_id', '=', self.company_id.id),
        #     ('type', '=', 'purchase' if self.is_leasing else 'general')
        # ], limit=1)
        self.residual_amount = 0.0

    @api.onchange('company_id')
    def _onchange_company(self):
        self._onchange_is_leasing()
        # self.interest_expenses_account_id = False
        # self.short_term_loan_account_id = False
        self.long_term_loan_account_id = False

        #pass

    def get_default_name(self, vals):
        return self.env['ir.sequence'].with_company(self.company_id).next_by_code('account.loan.app') or '/'


    def post(self):
        self.ensure_one()
        if not self.start_date:
            self.start_date = fields.Datetime.now().date()
        self.compute_draft_lines()
        self.write({'state': 'posted'})

    def close(self):
            self.write({'state': 'closed'})

    def compute_lines(self):
        self.ensure_one()
        if self.state == 'draft':
            return self.compute_draft_lines()
        return self.compute_posted_lines()

    def compute_posted_lines(self):
        """
        Recompute the amounts of not finished lines. Useful if rate is changed
        """
        amount = self.loan_amount
        for line in self.line_ids.sorted('sequence'):
            if line.move_ids:
                amount = line.final_pending_principal_amount
                # line.check_amount()
            else:
                line.rate = self.rate_period
                line.pending_principal_amount = amount
                line.check_amount()
                amount -= line.payment_amount - line.interests_amount
        if self.long_term_loan_account_id:
            self.check_long_term_principal_amount()


    def check_long_term_principal_amount(self):
        """
        Recomputes the long term pending principal of unfinished lines.
        """
        lines = self.line_ids.filtered(lambda r: not r.move_ids)
        amount = 0
        if not lines:
            return
        final_sequence = min(lines.mapped('sequence'))
        for line in lines.sorted('sequence', reverse=True):
            date = line.date + relativedelta(months=12)
            if self.state == 'draft' or line.sequence != final_sequence:
                line.long_term_pending_principal_amount = sum(
                    self.line_ids.filtered(
                        lambda r: r.date >= date
                    ).mapped('principal_amount'))
            line.long_term_principal_amount = (
                line.long_term_pending_principal_amount - amount)
            amount = line.long_term_pending_principal_amount

    def new_line_vals(self, sequence, date, amount):
        return {
            'loan_id': self.id,
            'sequence': sequence,
            'instl_no': sequence,
            'date': date,
            'pending_principal_amount': amount,
            'rate': self.rate_period,
        }
    
    # def compute_draft_lines(self):
    #     self.ensure_one()
    #     self.fixed_periods = self.periods
    #     self.fixed_loan_amount = self.loan_amount
    #     self.line_ids.unlink()
    #     amount = self.loan_amount
    #     if self.start_date:
    #         date = self.start_date
    #     else:
    #         date = datetime.today().date()
    #     delta = self.installment_delta()
    #     if not self.payment_on_first_period:
    #         date += delta
    #     for i in range(1, self.periods + 1):
    #         line = self.env['account.loan.line'].sudo().create(
    #             self.new_line_vals(i, date, amount)
    #         )
    #         line.check_amount()
    #         date += delta
    #         amount -= line.payment_amount - line.interests_amount
    #     if self.long_term_loan_account_id:
    #         self.check_long_term_principal_amount()
    def compute_draft_lines(self):
        self.ensure_one()
        self.fixed_periods = self.periods
        self.fixed_loan_amount = self.loan_amount
        self.line_ids.unlink()
        amount = self.loan_amount

        delta = self.installment_delta()

        if self.select_loan_date:
            date = self.first_installment_date

        else:
            date = self.start_date
            if not self.payment_on_first_period:
                date += delta

        for i in range(1, self.periods + 1):
            line = self.env['account.loan.line'].sudo().create(
                self.new_line_vals(i, date, amount)
            )
            line.check_amount()
            date += delta
            amount -= line.payment_amount - line.interests_amount

        if self.long_term_loan_account_id:
            self.check_long_term_principal_amount()

    def view_account_moves(self):
        self.ensure_one()
        action = self.env.ref('account.action_move_journal_line')
        result = action.sudo().read()[0]
        result['domain'] = [('loan_id', '=', self.id),('move_type','=','entry')]
        return result

    def view_account_invoices(self):
        self.ensure_one()
        action = self.env.ref('account.action_invoice_tree2')
        result = action.sudo().read()[0]
        result['domain'] = [
            ('loan_id', '=', self.id),
            ('move_type', '=', 'in_invoice')
        ]
        return result

    @api.model
    def generate_loan_entries(self, date):
        """
        Generate the moves of unfinished loans before date
        :param date:
        :return:
        """
        res = []
        for record in self.search([
            ('state', '=', 'posted'),
            ('is_leasing', '=', False)
        ]):
            lines = record.line_ids.filtered(
                lambda r: r.date <= date and not r.move_ids
            )
            res += lines.generate_move()
        return res

    @api.model
    def generate_leasing_entries(self, date):
        res = []
        for record in self.search([
            ('state', '=', 'posted'),
            ('is_leasing', '=', True)
        ]):
            res += record.line_ids.filtered(
                lambda r: datetime.strptime(
                    r.date, DF).date() <= date and not r.invoice_ids
            ).generate_invoice()
        return res


    @api.depends('rate_period', 'fixed_loan_amount', 'fixed_periods',
                 'currency_id')
    
    def _compute_fixed_amount(self):
        for record in self:
                if record.loan_type == 'fixed-annuity' and record.fixed_loan_amount:
                    record.fixed_amount = - record.currency_id.round(numpy_financial.pmt(
                        record.loan_rate() / 100,
                        record.fixed_periods or 1,
                        record.fixed_loan_amount,
                        -record.residual_amount
                    ))
                elif record.loan_type == 'fixed-principal':
                    record.fixed_amount = record.currency_id.round(
                        (record.fixed_loan_amount - record.residual_amount) /
                        (record.fixed_periods or 1)
                    )
                else:
                    record.fixed_amount = 0.0

    @api.constrains('loan_amount')
    def check_validation_for_loan(self):
        if self.loan_amount<1:
            raise ValidationError(_('Loan amount must be greater than 0.'))
        if self.rate<1:
            raise ValidationError(_('Interest rate must be greater than 0.'))
        if self.method_period<1:
            raise ValidationError(_('Period length must be greater than 0.'))
        if self.periods<1:
            raise ValidationError(_('Installment length must be greater than 0.'))

    @api.model
    def installment_delta(self):
        if self.interval == 'daily':
            delta = timedelta(days=self.method_period)  
        elif self.interval == 'weekly':
            delta = timedelta(weeks=self.method_period)
        elif self.interval == 'yearly':
            delta = relativedelta(years=self.method_period)
        else:
            delta = relativedelta(months=self.method_period)
        return delta

    @api.depends('line_ids.date')
    def get_maturity_date(self):
        for record in self:
            max_id = record.line_ids.ids and max(record.line_ids.ids)
            record.date_maturity = record.line_ids.filtered(lambda l: l.id==max_id).date

    @api.onchange('applied_amount')
    def onchnage_applied_amount(self):
        if self.state == 'draft':
            self.loan_amount = self.applied_amount

    # @api.onchange('loan_amount')
    # def onchnage_loan_amount(self):
    #     if self.state in ('draft', 'approval'):
    #         self.process_fee = (self.loan_amount * self.company_id.processing_fees)/100


    @api.depends('fees_ids.price_total', 'loan_amount')
    def compute_other_fees(self):
        process_fee_id = self.env.ref('banas_loan_management.fees_account_account')
        total_other_fees = sum(fee.price_total for fee in self.fees_ids if fee.account_id != process_fee_id)
        total_process_fees = sum(fee.price_total for fee in self.fees_ids if fee.account_id == process_fee_id)
        try:
            self.other_fee = total_other_fees
            self.process_fee=total_process_fees
            # self.process_fee=(self.loan_amount * self.company_id.processing_fees)/100
        except Exception as e:
            raise ValueError(f"Compute method failed: {e}")


    @api.depends('expense_invoice_ids', 'payment_ids', 'line_ids.payment_ids', 'debit_note_ids')
    def _compute_invoice(self):
        for loan in self:
            loan.invoice_count = len(loan.expense_invoice_ids)
            loan.fee_invoice_count = len(loan.fee_invoice_ids)
            # loan.payment_count = len(loan.payment_ids)
            loan.payment_count = len(loan.payment_ids) + len(loan.line_ids.mapped('payment_ids'))
            loan.debit_note_count = len(loan.debit_note_ids.ids)


    @api.onchange('type_id', 'loan_amount')
    def onchange_type(self):
        self.loan_type = self.type_id.cal_method
        if self.type_id.journal_processing_fee_id:
            self.journal_processing_fee_id = self.type_id.journal_processing_fee_id.id
        else:
            self.journal_processing_fee_id = self.env.company.journal_processing_fee_id.id
        if self.type_id.journal_other_fee_id:
            self.journal_other_fee_id = self.type_id.journal_other_fee_id.id
        else:
            self.journal_other_fee_id = self.env.company.journal_other_fee_id.id

        if self.type_id.journal_id:
            self.journal_id = self.type_id.journal_id
        else:
            self.journal_id = self.env.company.journal_loan_id.id

        if self.type_id.debit_journal_id:
            self.debit_journal_id = self.type_id.debit_journal_id
        else:
            self.debit_journal_id = self.env.company.journal_debit_id.id

        if self.type_id.penalty_journal_id:
            self.penalty_journal_id = self.type_id.penalty_journal_id
        else:
            pass


        val = [(5, 0, 0)]
        for fee in self.type_id.fees_ids:
            val.append((0, 0, {
            'product_id': fee.product_id.id,
            'account_id': fee.account_id.id,
            'charges': fee.charges,
        }))
        self.fees_ids = val

    # @api.onchange('period_id')
    # def onchange_period(self):
    #     self.periods = self.period_id.period

    # def action_send_for_approval(self):
    #     self.state='approval'

    def action_approve(self):
        self.state='approved'
        self.line_ids.write({'state':'pending'})
        self.loan_approved()

    def action_send_for_approval(self):
        self.state = 'approval'

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.get_default_name(vals)
        res = super(AccountLoan, self).create(vals)
        res.compute_lines()
        return res

    def write(self, vals):
        res = super(AccountLoan, self).write(vals)
        if not self._context.get('in_compute_lines', False):
            for record in self:
                if record.state == 'draft' and record._context.get('compute_item', True):
                    record.with_context(in_compute_lines=True).compute_lines()
        return res


    def action_draft(self):
        if self.state in ['approved', 'rejected']:
            # self.credit_invoice_id.button_cancel()
            self.credit_invoice_id.button_draft()
            self.state = 'draft'

    # def action_loan_approve(self):
    #     self.state = 'approved'

    def action_see_attachments(self):
        domain = [
            ('res_model', 'in', ('banas.loan', 'banas.loan.document')),
            ('res_id', 'in', [self.id]+self.gold_document_ids.ids)
        ]
        attachment_view = self.env.ref('banas_loan_management.view_banas_loan_document_kanban')
        return {
            'name': _('Attachments'),
            'domain': domain,
            'res_model': 'banas.loan.document',
            'type': 'ir.actions.act_window',
            'view_id': attachment_view.id,
            'views': [(attachment_view.id, 'kanban'), (False, 'form')],
            'view_mode': 'kanban,tree,form',
            'view_type': 'form',
            'help': _('''<p class="o_view_nocontent_smiling_face">
                        Upload files
                    </p><p>
                        Use this feature to store any files.
                    </p>'''),
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d, 'default_loan_id': %d}" % (self._name, self.id, self.id)
        }

    def count_attachemnt(self):
        for loan in self:
            loan.total_attachment = len(loan.document_ids)+len(loan.gold_document_ids)

  
    def action_reject(self):
        if self.credit_invoice_id:
            self.credit_invoice_id.button_draft()
            # self.credit_invoice_id.button_cancel()
        self.state='rejected'

    # def _approval_reject_by_user(self, app_req=True, comment=True):
    #     return self.approval_id._approval_reject_by_user()

    def action_view_disbursement(self):
        invoices = self.credit_invoice_id
        action = self.env.ref('account.action_move_out_refund_type').sudo().read()[0]
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = invoices.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def view_debit_notes(self):
        self.ensure_one()
        action = self.env.ref('account.action_move_out_invoice_type')
        result = action.sudo().read()[0]
        result['domain'] = [('debit_loan_id', '=', self.id)]
        return result

    def action_view_invoice(self):
        invoices = self.expense_invoice_ids
        action = self.env.ref('account.action_move_in_invoice_type').sudo().read()[0]
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = invoices.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def action_view_fee_invoice(self):
        invoices = self.fee_invoice_ids
        action = self.env.ref('account.action_move_out_invoice_type').sudo().read()[0]
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = invoices.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def action_send_sms(self, type):
        # sms_obj = self.env['sms.api']
        msg = ''
        numbers = []
        if type == 'approved' and self.partner_id.mobile:
            numbers = self.partner_id.mobile
            date = datetime.now().strftime("%d%b%Y")
            name = self.partner_id.name.split(" ")[0]
            msg = "Dear %s, Your loan #%s Rs %s Approved on %s by %s"
            msg = msg%(name, self.name, format(self.loan_amount, '.2f'), date, self.company_id.name)
            message = 'Hi there, thank you for sending your first test message from Textlocal. See how you can send effective SMS campaigns here'
            print(numbers,name,message)
        # if message and numbers:
        #     sms_obj.sendSMS(numbers=numbers,message=message)
 

    def fees_move_line_vals(self, journal, type):
        vals = []
        partner = self.partner_id.with_context(
            force_company=self.company_id.id)
        if self.process_fee>0 and type=='Processing':
            if not journal.default_account_id:
                raise ValidationError("Processing fee credit account not set!")
            vals.append({
                'account_id': partner.property_account_receivable_id.id,
                'credit': 0,
                'name': 'Processing Fee',
                'partner_id': partner.id,
                'debit': self.process_fee,
            })
            vals.append({
                'account_id': journal.default_credit_account_id.id,
                'credit': self.process_fee,
                'debit': 0,
            })
        if self.other_fee>0 and type=='Other':
            if not journal.default_account_id:
                raise ValidationError("Other fee credit account not set!")
            vals.append({
                'account_id': partner.property_account_receivable_id.id,
                'credit': 0,
                'name': 'Other Fee',
                'partner_id': partner.id,
                'debit': self.other_fee,
            })
            vals.append({
                'account_id': journal.default_credit_account_id.id,
                'credit': self.other_fee,
                'debit': 0,
            })
        return vals

    def fees_move_vals(self, journal, type):
        if not journal:
            raise ValidationError("Fee journal not selection!")
        return {
            'loan_id': self.id,
            'date': self.date_application,
            'ref': self.name,
            'journal_id': journal.id,
            'line_ids': [(0, 0, vals) for vals in self.fees_move_line_vals(journal, type)]
        }

    def loan_disbursement_credit_invoice_line(self):
        qty = 1
        product_tmpl_id = self.type_id.product_tmpl_id
        invoice_line = self.env['account.move.line']
        account_id = invoice_line.with_context({'journal_id': self.journal_id.id, 'move_type': 'out_refund'})
        data = [(5, 0, 0)]

        data.append((0, 0, {
            'name': str(self.name) + ': ' + str(product_tmpl_id.name),
            # 'origin': self.name,
            'product_uom_id': product_tmpl_id.uom_po_id.id,
            'product_id': product_tmpl_id.product_variant_id.id,
            'account_id': self.short_term_loan_account_id.id,
            'price_unit': self.loan_amount,
            'quantity': qty,
            'discount': 0.0,
            'tax_ids': product_tmpl_id.taxes_id,
        }))
        return data

    def loan_disbursement_credit_invoice(self):
        

        print("-------------disbursment-----------------")
        # self.state='approved'
        inv_obj = self.env['account.move']
        vals = {
            'partner_id': self.partner_id.id,
            'ref': self.name,
            'move_type': 'out_refund',
            # 'currency_id': self.company_id.currency_id.id,
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
            'loan_id': self.id,
            'journal_id': self.journal_id.id,
            'invoice_line_ids': self.loan_disbursement_credit_invoice_line()
        }
        if not self.credit_invoice_id:
            inv_id = inv_obj.create(vals)
            inv_id.action_post()
            self.credit_invoice_id = inv_id.id
        else:
            self.credit_invoice_id.write(vals)
            self.credit_invoice_id.action_post()
        if self.payment_on_first_period:
            self.line_ids[0].installment_invoices()
            self.line_ids[0].state='pending'
        

    def loan_approved(self):
        application_number = self.name
        vals = {'application_number': application_number, 'state': 'approved'}
        if not self.application_number:
            code = self.company_id.loan_seq_id.next_by_id() or '/'
            # code = self.env['ir.sequence'].next_by_code('create.loan.app')
            vals.update({'name': code})
        self.write(vals)
        self.action_send_sms('approved')
        if self.sales_person_id and self.commission_percentage > 0:
            self.create_sales_expense_invoice()
        if self.fees_ids:
            self.create_fees_invoice()
        self.loan_disbursement_credit_invoice()

    def action_account_payments(self):
        action = self.env.ref('account.view_account_payment_register_form').sudo().read()[0]
        payment_amount=sum(self.credit_invoice_id.mapped('amount_total'))
        active_ids = self.credit_invoice_id.ids
        inv_vals = [(4, self.credit_invoice_id.id)]
        if self.fee_deduct_from_payment and self.fees_invoice_id and self.fees_invoice_id.payment_state == 'not_paid':
            inv_vals.append((4, self.fees_invoice_id.id))
            active_ids.append(self.fees_invoice_id.id)
        if self.payment_on_first_period and self.line_ids and self.line_ids[0].installment_invoice_id == 'open':
            inv_vals.append((4, self.line_ids[0].installment_invoice_id.id))
       
        action = {
            'name': 'Account Payment Register',
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment.register',
            'view_mode': 'form',
            'view_id': self.env.ref('account.view_account_payment_register_form').id,
            'target': 'new', 
            'context': {'active_model': 'account.move', 
            'active_ids': active_ids,
            'default_loan_payment_type': 'transfer',
            'default_partner_type': 'customer',
            'search_default_inbound_filter': 1,
            'default_loan_id': self.id,
            'default_payment_type': 'outbound',
            'default_payment_amount': payment_amount,
            'default_partner_id': self.payment_partner_id and self.payment_partner_id.id or self.partner_id.id,
            'default_communication': self.name,
            'default_invoice_ids': inv_vals,
            }
        }
        return action

    def action_register_payments(self):
        if self.line_ids.installment_invoice_id or self.debit_note_ids:
            payment_states_debit= [debit_note.payment_state == 'paid' for debit_note in self.debit_note_ids]
            payment_states_lines=[line.payment_state == 'paid' for line in self.line_ids.installment_invoice_id]
        
            if all(payment_states_debit) and all(payment_states_lines):
                return self.close()

        
            invoice_ids = self.line_ids.mapped('installment_invoice_id').filtered(lambda inv: inv.payment_state=='not_paid' and inv.state=='posted')
            payment_amount = sum(invoice_ids.mapped('amount_total'))
            action = {
                'name': 'Account Payment Register',
                'type': 'ir.actions.act_window',
                'res_model': 'account.payment.register',
                'view_mode': 'form',
                'view_id': self.env.ref('account.view_account_payment_register_form').id,
                'target': 'new', 
                'context': {'active_model': 'account.move', 
                'active_ids': list(invoice_ids.ids),
                'default_loan_payment_type': 'multi_installment',
                'default_payment_type': 'inbound',
                'default_partner_type': 'customer',
                'search_default_inbound_filter': 1,
                'default_loan_id': self.id,
                # 'default_amount': payment_amount,
                'default_fees': 0,
                'default_payment_amount': payment_amount,
                # 'reconciled_invoice_ids': [(4, inv.id) for inv in invoice_ids]
                }
            }
            return action
    def action_account_debit_note_payments(self):
        debit_note_ids = self.debit_note_ids.filtered(lambda inv: inv.payment_state == 'not_paid')
        payment_amount = sum(debit_note_ids.mapped('amount_total'))
        action = {
            'name': 'Account Payment Register',
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment.register',
            'view_mode': 'form',
            'view_id': self.env.ref('account.view_account_payment_register_form').id,
            'target': 'new', 
            'context': {'active_model': 'account.move', 
            'active_ids': list(debit_note_ids.ids),
            'default_loan_payment_type': 'debit',
            'default_payment_type': 'inbound',
            'default_partner_type': 'customer',
            'search_default_inbound_filter': 1,
            'default_loan_id': self.id,
            'default_debit_note_amount': self.debit_note_remain_amount,
            'default_fess': self.debit_note_interest_amount,
            # 'default_amount': 0,
            'default_fess': 0,
            'default_payment_amount': payment_amount,
            # 'default_debit_note_loan_id':self.id
            # 'default_invoice_ids': [(4, inv.id, None) for inv in debit_note_ids],
            }
        }
        return action


    def action_view_account_payments(self):
        payment_ids = self.payment_ids+self.line_ids.mapped('payment_ids')
        action = self.env.ref('account.action_account_payments').sudo().read()[0]
        action['context'] = {}
        if len(payment_ids) > 1:
            action['domain'] = [('id', 'in', payment_ids.ids)]
        elif len(payment_ids) == 1:
            action['views'] = [(self.env.ref('account.view_account_payment_form').id, 'form')]
            action['res_id'] = payment_ids.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def _prepare_invoice_line_from_loan_sales_expense(self):
        qty = 1
        product = self.env.company.product_sales_person_id
        taxes = product.supplier_taxes_id
        commission_price = (self.loan_amount*self.commission_percentage) / 100,
        invoice_line = self.env['account.move.line']
        if not self.sales_expense_journal_id.default_account_id:
            raise ValidationError(_('Set default accounts in Sale Person Expense Journal.'))

        data = {
            'name': str(self.name)+': '+str(product.name),
            # 'origin': self.name,
            'product_uom_id': product.uom_po_id.id,
            'product_id': product.id,
            'account_id': self.sales_expense_journal_id.id,
            # 'account_id': invoice_line.with_context({'journal_id': self.sales_expense_journal_id.id, 'move_type': 'in_invoice'}),
            'price_unit': commission_price,
            'quantity': qty,
            'discount': 0.0,
            'tax_ids': taxes.ids
        }
        return data


    def create_sales_expense_invoice(self):
        inv_obj = self.env['account.move']
        vals = {
            'partner_id': self.partner_id.id,
            'ref': self.name,
            'invoice_date':self.date,
            'move_type': 'in_invoice',
            # 'currency_id': self.company_id.currency_id.id,
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
            'loan_id': self.id,
            'journal_id': self.sales_expense_journal_id.id,
            'invoice_line_ids': [(0, 0, self._prepare_invoice_line_from_loan_sales_expense())]
        }
        inv_id = inv_obj.create(vals)
        inv_id.action_post()

    def _prepare_invoice_line_for_fees(self):
        qty = 1
        data = []
        for fee in self.fees_ids:
            data.append((0, 0, {
                'name': self.name+': '+fee.product_id.name,
                # 'origin': self.name,
                'product_uom_id': fee.product_id.uom_po_id.id,
                'product_id': fee.product_id.id,
                'account_id': fee.account_id.id,
                'price_unit': fee.price_total,
                'quantity': qty,
                'discount': 0.0,
                'tax_ids': fee.product_id.taxes_id,
            }))
        return data

    def create_fees_invoice(self):
        inv_obj = self.env['account.move']
        vals = {
            'partner_id': self.partner_id.id,
            'journal_id': self.journal_processing_fee_id.id,
            'ref': self.name,
            'move_type': 'out_invoice',
            # 'currency_id': self.company_id.currency_id.id,
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
            'loan_id': self.id,
            'invoice_line_ids': self._prepare_invoice_line_for_fees()
        }
        if not self.fees_invoice_id:
            inv_id = inv_obj.create(vals)
            inv_id.action_post()
            self.fees_invoice_id = inv_id.id
        else:
            self.fees_invoice_id.write(vals)


    def compute_installment_seq(self):
        for loan in self:
            instl_no = 1
            advance_no = 1
            for line in loan.line_ids:
                if line.type=='instl':
                    line.instl_no = instl_no
                    line.advance_no = 0
                    instl_no += 1
                elif line.type=='advance':
                    line.instl_no = 0
                    line.advance_no = advance_no
                    advance_no += 1

    def action_loan_statement(self):
        return {
            'name': _('Loan Statement'),
            'res_model': 'banas.loan.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    @api.depends('loan_amount','currency_id')
    def _compute_check_amount_in_words(self):
        for pay in self:
                pay.check_amount_in_words = pay.currency_id.amount_to_text(pay.loan_amount) if pay.currency_id else ''

    def action_receive_payments(self):
        loan_id=self.id
        return {
            'name': _('pay amount'),
            'res_model': 'account.loan.pay.amount',
            'view_mode': 'form',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'domain':[],
            'context': {
            'default_loan_id': loan_id,},
            
        }
    def action_cancel_payments(self):
        loan_id=self.id
        return {
            'name': _('pay amount'),
            'res_model': 'account.loan.pay.amount',
            'view_mode': 'form',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'domain':[],
            'context': {
            'default_loan_id': loan_id,
            'default_cancel_loan': True,},
            
        }
    @api.onchange('sales_expense_journal_id','sales_person_id')
    def get_commissin_percantage(self):
        if self.sales_person_id:
            self.commission_percentage=self.sales_expense_journal_id.commission_percentage

    # def partner_ledger(self):
    #     context = {}
    #     action = self.env.ref('base_accounting_kit.action_partner_leadger').sudo().read()[0]
    #     context = {
    #         'default_loan_ids': self.ids,
    #         # 'default_partner_ids':self.partner_id.ids,
    #     }

    #     action['context'] = context
    #     action['view_mode'] = 'form'
    #     form_view = [(self.env.ref('base_accounting_kit.account_report_partner_ledger_view').id, 'form')]
    #     action['views'] = form_view

    #     return action

    # @api.model
    # def _run_sms(self):
    #     sms_obj = self.env['sms.api']
    #     upcoming_domain = [
    #         ('sms_upcomming', '=', False),
    #         ('date', '=', datetime.now()+timedelta(days=2)),
    #         ('payment_ids', '=', False),
    #         ('payment_amount', '>', 0),
    #         ('state', '=', 'pending'),
    #         ('loan_state', '=', 'posted')
    #     ]
    #     upcomming_insts = self.line_ids.search(upcoming_domain)
    #     upcomming_sms_format = "Hi %s, Your next loan payment #%s of loan #%s is due on %s. Please make a payment of Rs %s before the due date. Or call us at %s if you have any questions."
    #     for line in upcomming_insts:
    #         date = format_date(self.env, line.date, date_format='ddMMMYYYY')
    #         name = line.loan_id.partner_id.name.split(" ")[0]
    #         upcomming_sms = upcomming_sms_format%(
    #             name,
    #             format(line.sequence, '05d'),
    #             line.loan_id.name, date,
    #             line.payment_amount, line.loan_id.company_id.phone)
    #         sms_obj._send_sms(line.loan_id.partner_id.mobile, upcomming_sms)
    #         line.write({'sms_upcomming': True})

    #     today_domain = [
    #         ('sms_payment', '=', False),
    #         ('date', '=', datetime.now()),
    #         ('payment_ids', '=', False),
    #         ('payment_amount', '>', 0),
    #         ('state', '=', 'pending'),
    #         ('loan_state', '=', 'posted')
    #     ]
    #     today_insts = self.line_ids.search(today_domain)
    #     today_sms_format = "Hi %s, Last day of payment #%s an amount of Rs %s of loan #%s. Please make a payment by today to avoid late fee. Or call us at %s if you have any questions."
    #     for line in today_insts:
    #         name = line.loan_id.partner_id.name.split(" ")[0]
    #         today_sms = today_sms_format%(
    #             name,
    #             format(line.sequence, '05d'),
    #             line.payment_amount,
    #             line.loan_id.name,
    #             line.loan_id.company_id.phone)
    #         sms_obj._send_sms(line.loan_id.partner_id.mobile, today_sms)
    #         line.write({'sms_payment': True})

    #     due_sms_format = "Hi %s, Your loan payment #%s an amount of Rs %s of loan #%s is outstanding. It was due on %s. Please call us at %s to make a payment or to set up a payment arrangement."
    #     due_domain = [
    #         ('sms_due_payment1', '=', False),
    #         ('date', '<', datetime.now()-timedelta(days=2)),
    #         ('payment_ids', '=', False),
    #         ('payment_amount', '>', 0),
    #         ('state', '=', 'pending'),
    #         ('loan_state', '=', 'posted')
    #     ]
    #     due_insts = self.line_ids.search(due_domain)
    #     for line in due_insts:
    #         date = format_date(self.env, line.date, date_format='ddMMMYYYY')
    #         name = line.loan_id.partner_id.name.split(" ")[0]
    #         due_sms = due_sms_format%(
    #             name,
    #             format(line.sequence, '05d'),
    #             line.payment_amount,
    #             line.loan_id.name, date,
    #             line.loan_id.company_id.phone)
    #         sms_obj._send_sms(line.loan_id.partner_id.mobile, due_sms)
    #         line.write({'sms_due_payment1': True})

    #     due_domain = [
    #         ('sms_due_payment2', '=', False),
    #         ('date', '<', datetime.now()-timedelta(days=6)),
    #         ('payment_ids', '=', False),
    #         ('payment_amount', '>', 0),
    #         ('state', '=', 'pending'),
    #         ('loan_state', '=', 'posted')
    #     ]
    #     due_insts = self.line_ids.search(due_domain)
    #     for line in due_insts:
    #         name = line.loan_id.partner_id.name.split(" ")[0]
    #         date = format_date(self.env, line.date, date_format='ddMMMYYYY')
    #         due_sms = due_sms_format%(
    #             name,
    #             format(line.sequence, '05d'),
    #             line.payment_amount,
    #             line.loan_id.name, date,
    #             line.loan_id.company_id.phone)
    #         sms_obj._send_sms(line.loan_id.partner_id.mobile, due_sms)
    #         line.write({'sms_due_payment2': True})

    

class BanasFeesId(models.Model):
    _name = 'banas.loan.fees'
    _description = 'Loan'
    
    loan_id = fields.Many2one(
        'banas.loan',string = "fees line")
    product_id = fields.Many2one('product.product', string="Fees Type", required=True)
    account_id = fields.Many2one('account.account', string='Account',
        domain=[('deprecated', '=', False)], required=True, help="The partner account used for this fees.")
    price_unit = fields.Monetary( string='Amount',related="loan_id.loan_amount", required=True, digits=dp.get_precision('Product Price'))
    charges = fields.Float(string='Charges (%)', required=True, digits=dp.get_precision('Discount'),
        default=0.0)
    price_total = fields.Monetary(string='Amount',
        store=True, readonly=True, compute='_compute_price', help="Total amount")
    loan_id = fields.Many2one("banas.loan", string="Loan")
    currency_id = fields.Many2one(related="loan_id.currency_id")

    @api.depends('price_unit', 'charges')
    def _compute_price(self):
        for line in self:
            line.price_total = line.price_unit * (line.charges or 0.0) / 100.0

class BanasApprovalIds(models.Model):
    _name = 'banas.approval'
    _description = 'Loan'

    loan_id = fields.Many2one(
        'banas.loan',string = "fees line")
    name = fields.Char(
                        string = " Role",)
    template_stage_id = fields.Char(
                        string = "Approval Stage",)
    is_approved = fields.Boolean(
                        string = "Is Approved",)
    is_rejected = fields.Boolean(
                        string = "Is Rejected",)
    status = fields.Selection([
                        ('none',"Not Yet",),
                        ('comment',"Commented"),
                        ('approved',"Approved"),
                        ('rejected',"Rejected")],
                        string = "Status",)


class OwnerNumber(models.Model):
    _name = "banas.loan.vehicle.ownership"
    _description = 'Owner Number'

    name = fields.Char("Name", required=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company.id,
    )


class LoanTypeT(models.Model):
    _name = "banas.loan.type"
    _description = "Banas Loan Type"
   
    name = fields.Char('Name', required=True)
    # document_ids = fields.Many2many('banas.loan.document.type', 'banas_loan_type_doc_type_rel', 'type_id', 'doc_type_id', string='Documents')
    cal_method = fields.Selection(
        [
            ('fixed-annuity', 'Fixed Annuity'),
            ('fixed-principal', 'Fixed Principal'),
            ('interest', 'Only interest'),
            ('advanceinterest', 'Only interest + Advance'),
            ('flat-interest','Flat Interest'),
        ],
        required=True,
        help='Method of computation of the period annuity',
        default='fixed-annuity'
    )
    type = fields.Selection(LOAN_TYPE, string="Type")
    journal_other_fee_id = fields.Many2one(
        'account.journal',
        string="Other Fee Journal",
        # default=lambda self: self.env.user.company_id.journal_other_fee_id.id
    )
    journal_processing_fee_id = fields.Many2one(
        'account.journal',
        string="Processing Fee Journal",
        # default=lambda self: self.env.user.company_id.journal_processing_fee_id.id
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company.id,
    )
    loan_ids = fields.One2many('banas.loan', 'type_id', string="Loans")
    loan_count = fields.Integer(compute='get_loan_count', string="#Loans", store=True)
    document_type_ids = fields.Many2many("banas.loan.document.type", "banas_loan_type_doc_type_rel", "type_id", "doc_type_id", string="Documents")
    product_tmpl_id = fields.Many2one('product.template', string="Product", required=False, ondelete="restrict")
    fees_ids = fields.One2many('banas.loan.type.fees', 'loan_type_id', string="Fees", default=lambda self: self.get_type_fees())
    # partner_id=fields.Many2one("res.partner",string="Customer")
    journal_id = fields.Many2one('account.journal', string="Journal")
    debit_journal_id = fields.Many2one('account.journal', string="Debit Journal")
    penalty_journal_id = fields.Many2one('account.journal',string="Penalty Journal")

    @api.model
    def get_type_fees(self):
    
    
        company_id = self._context.get('force_company', False) or self.env.company.id
        print (".........................", company_id)
        company_id = self.env['res.company'].browse([company_id])
        return [
            (0, 0, {
                'product_id': company_id.product_process_fee_id.product_variant_id.id,
                # 'account_id': company_id.journal_processing_fee_id.default_credit_account_id.id,
                'account_id': company_id.journal_processing_fee_id.default_account_id.id,
                'charges': company_id.processing_fees,
            })
        ]

    
    
    @api.depends('loan_ids')
    def get_loan_count(self):
        for loan_type in self:
            loan_type.loan_count = len(loan_type.loan_ids)

    @api.model
    def create(self, vals):
        product_tmpl_obj = self.env['product.template']
        if not vals.get('product_tmpl_id'):
            product_vals = {
                'name': vals.get('name'),
                'categ_id': self.env.ref('banas_loan_management.cat_service').id,
                'standard_price': 0,
                'list_price': 0,
                'type': 'service',
                'uom_id': self.env.ref('uom.product_uom_unit').id,
                'uom_po_id': self.env.ref('uom.product_uom_unit').id,
                'taxes_id': [(6, 0, [])],
            }
            product_tmpl = product_tmpl_obj.create(product_vals)
            vals.update({'product_tmpl_id': product_tmpl.id})
        res = super(LoanTypeT, self).create(vals)
        return res

    def write(self, vals):
        product_tmpl_obj = self.env['product.template']
        product_vals = {
            'name': vals.get('name') or self.name,
            'categ_id': self.env.ref('banas_loan_management.cat_service').id,
            'standard_price': '0',
            'list_price': 0,
            'type': 'service',
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'taxes_id': [(6, 0, [])],
        }
        if not vals.get('product_tmpl_id') and not self.product_tmpl_id:
            product_tmpl = product_tmpl_obj.create(product_vals)
            vals.update({'product_tmpl_id': product_tmpl.id})
        elif self.product_tmpl_id:
            product_tmpl = self.product_tmpl_id.write(product_vals)
        res = super(LoanTypeT, self).write(vals)
        return res

class LoanTypeFEES(models.Model):
    _name = 'banas.loan.type.fees'
    _description = 'Loan Type Fees'

    product_id = fields.Many2one('product.product', string="Fees")
    account_id = fields.Many2one('account.account',  string='Account',
        domain=[('deprecated', '=', False)], help="The partner account used for this fees.")
    charges = fields.Float(string='Charges (%)', required=True)
    loan_type_id = fields.Many2one('banas.loan.type', string="Loan Type", ondelete='cascade')


class VehicleBrand(models.Model):
    _inherit = 'fleet.vehicle.model.brand'
    _description = 'Vehicle Brand'

    active = fields.Boolean(default=False)


class VehicleModel(models.Model):
    _inherit = "fleet.vehicle.model"
    _description = 'Vehicle Model'

    wheel_base=fields.Char(string="Wheel Base")
class LoanPeriod(models.Model):
    _name = 'banas.loan.period'
    _description = 'Loan Period'

    name = fields.Char('Period Name', required=True)
    period = fields.Integer('Loan Period', required=True)

class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def create(self, vals):
        print ("..........................", self._context)
        if self.env.user.has_group('base.group_system') or self._context.get('no_reset_password', False):
            return super(ResUsers, self).create(vals)
        else:
            raise AccessError("You don't have permission to create users.")


# class AccountChartTemplateTax(models.Model):
#     _inherit = 'account.chart.template'

#     def _load(self, company):
    
#         res = super()._load(company)  
#         company.account_sale_tax_id = False
#         company.account_purchase_tax_id = False
#         return res
