from odoo import api, fields, models
from odoo.exceptions import UserError
# from odoo.addons.iap.models import iap

import urllib.request
import urllib.parse

import json

import logging
_logger = logging.getLogger(__name__)

#

class SMSSMS(models.Model):
    _inherit = 'sms.sms'
    _description = 'sms'

   