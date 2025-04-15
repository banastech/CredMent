from odoo import api, fields, models
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
import numpy_financial as npf
import math
_logger = logging.getLogger(__name__)
try:
    import numpy
except (ImportError, IOError) as err:
    _logger.debug(err)


class LoanCal(models.TransientModel):
    _name = 'loan.cal'
    _description = 'Loan Calculator'

    name = fields.Char("Name", default="Calculator") 
    loan_amount = fields.Monetary(
        string="Principal Amount",
        currency_field='currency_id',
        required=True,
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
        help='Method of computation of the period annuity',
        default='fixed-annuity'
    )
    rate = fields.Float(
        required=True,
        default=0.0,
        digits=(8, 6),
        help='Currently applied rate',
    )
    periods = fields.Integer(
        required=True,
        help='Number of periods that the loan will last',
    )
    method_period = fields.Integer(
        string='Period Length',
        default=1,
        help="State here the time between 2 depreciations, in months",
        required=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        readonly=True,
        default= lambda self: self.env.ref('base.INR').id,
    )
    rate_period = fields.Float(
        compute='_compute_rate_period', digits=(8, 6),
        help='Real rate that will be applied on each period',
    )
    rate_type = fields.Selection(
        [
            ('napr', 'Nominal APR'),
            ('ear', 'EAR'),
            ('real', 'Real rate'),
        ],
        required=True,
        default='napr',
    )
    fixed_amount = fields.Monetary(
        currency_field='currency_id',
        compute='_compute_fixed_amount',
        string="Intallment Amount"
    )
    total_payment_amount = fields.Monetary(
        currency_field='currency_id',
        string='Total Amount',
        readonly=True,
        compute = '_compute_total_amount'

    )
    total_interests_amount = fields.Monetary(
        currency_field='currency_id',
        string='Total Interest Amount',
        readonly=True,
        compute = '_compute_interest_amount',
        digits=(8, 3),
    )

    @api.onchange('rate', 'periods', 'method_period', 'rate_type')
    def onchange_rate_period(self):
        for record in self:
            record.rate_period = record.loan_rate()

    def loan_rate(self):
        return self.compute_rate(
            self.rate, self.rate_type, self.method_period
        )

    @api.depends('rate', 'method_period', 'rate_type')
    def _compute_rate_period(self):
        for record in self:
            record.rate_period = record.loan_rate()

    @api.model
    def compute_rate(self, rate, rate_type, method_period):
        if rate_type == 'napr':
            return rate / 12 * method_period
        if rate_type == 'ear':
            return math.pow(1 + rate, method_period / 12) - 1
        return rate

    @api.onchange('fixed_amount')

    # def compute(self):
    #     amount = self.loan_amount
    #     date = datetime.today().date()
    #     delta = relativedelta(months=self.method_period)
    #     payment_amount = interests_amount = 0
    #     emi = self.fixed_amount
    #     for i in range(1, self.periods + 1):
    #         interest_payment = (amount * self.loan_rate() / 100)
    #         principal_payment = emi - interest_payment 
    #         payment_amount += emi
    #         interests_amount += interest_payment
    #         date += delta
    #         amount -= principal_payment  # Reduce the remaining loan amount
            
    #     self.total_payment_amount = payment_amount
    #     self.total_interests_amount = interests_amount
    def compute(self):
        amount = self.loan_amount
        date = datetime.today().date()
        delta = relativedelta(months=self.method_period)
        payment_amount = interests_amount = 0
        for i in range(1, self.periods + 1):
            payment_amount += self.fixed_amount
            interests_amount += (amount * self.loan_rate() / 100)
            date += delta
            amount -= self.fixed_amount - (amount * self.loan_rate() / 100)
        self.total_payment_amount = payment_amount
        self.total_interests_amount = interests_amount

# ...




    @api.depends('rate_period', 'loan_amount', 'periods', 'currency_id')
    def _compute_fixed_amount(self):
        for record in self:
            if not record.periods or not record.loan_amount or not record.loan_rate():
                # Handle cases where input values are not valid
                record.fixed_amount = 0.0
                continue

            try:
                if record.loan_type == 'fixed-annuity':
                    record.fixed_amount = -record.currency_id.round(npf.pmt(
                        record.loan_rate() / 100,
                        record.periods,
                        record.loan_amount,

                    ))
 
                elif record.loan_type == 'fixed-principal':
                    record.fixed_amount = record.currency_id.round(
                        (record.loan_amount) / record.periods
                    )
                else:
                    record.fixed_amount = 0.0
            except ValueError as e:
                _logger.error(f"ValueError: {e}")
                record.fixed_amount = 0.0
    


    
    

            
