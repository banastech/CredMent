from odoo import api, fields, models,_
from datetime import datetime, timedelta

from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)
try:
    import numpy
except (ImportError, IOError) as err: 
    _logger.error(err)

class BanasEngineTrack(models.Model):
    _name = 'banas.engine.track'   
    _description = 'Loan'

    # approval_id = fields.Many2one(
    #     'res.partner',string = "approval line")

    # name = fields.Char(string="Role")
    # template_stage_id = fields.Char(string="Approval Stage")
    # is_approved = fields.Boolean(string="Is Approved")
    # is_rejected = fields.Boolean(string="Is Rejected")
    # status = fields.Selection([
    #     ('none', "Not Yet"),
    #     ('comment', "Commented"),
    #     ('approved', "Approved"),
    #     ('rejected', "Rejected")],
    #     string="Status",
    #     default='none')
