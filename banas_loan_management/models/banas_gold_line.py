from odoo import api, fields, models

class AccountGoldLine(models.Model):
    _name = 'banas.gold.line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Annuity'
    # _order = 'sequence asc'


  
    currency_id = fields.Many2one( 
        'res.currency',
        readonly=True,
        default= lambda self: self.env.ref('base.INR').id,
    )

    loan_id = fields.Many2one(
        'banas.loan',string = "gold line")

    
    
    product_id = fields.Many2one('product.product', string="Gold Type", required=True ,store=True )
    product_qty = fields.Float(string = "Quantity" , digits=(8, 2), required=True, default=1)
    uom_id = fields.Many2one('uom.uom', string="Unit of Measure")
    gross_weight =fields. Float(string = "Gross Weight" , digits=(8, 2), required=True, default=0)
    stone_weight = fields.Float(string = "Stone Weight" , digits=(8, 2), required=True, default=0)
    net_weight = fields.Float(string = "Net weight" , digits=(8, 2), required=True, default=0)
    name  =fields. Text(string = "Remark" , required=False)

    




