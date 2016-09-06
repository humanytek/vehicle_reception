from openerp import api, fields, models


class VehicleReception(models.AbstractModel):
    _name = 'vehicle.reception'

    contract_id = fields.Many2one('purchase.order')
    auxiliary_contract = fields.Many2one('purchase.order')
    contract_type = fields.Selection(readonly=True, related="contract_id.contract_type")
    partner_id = fields.Many2one('res.partner', readonly=True, related="contract_id.partner_id")
    street = fields.Char(readonly=True, related='partner_id.street')
    contract_state = fields.Selection(readonly=True, related="contract_id.state")

    hired = fields.Float(compute="_compute_hired", readonly=True, store=False)
    delivered = fields.Float(compute="_compute_delivered", readonly=True, store=False)
    pending = fields.Float(compute="_compute_pending", readonly=True, store=False)

    product_id = fields.Many2one('product.product', compute="_compute_product_id", readonly=True, store=False)
    location_id = fields.Many2one('stock.location', readonly=True, related="contract_id.location_id")

    damaged_location = fields.Many2one('stock.location')

    @api.one
    @api.depends('contract_id')
    def _compute_hired(self):
        self.hired = sum(line.product_qty for line in self.contract_id.order_line)

    @api.one
    @api.depends('contract_id')
    def _compute_delivered(self):
        self.delivered = 0

    @api.one
    @api.depends('contract_id')
    def _compute_pending(self):
        self.pending = self.hired - self.delivered

    @api.one
    @api.depends('contract_id')
    def _compute_product_id(self):
        if self.contract_id:
            self.product_id = self.contract_id.order_line[0].product_id or False
        else:
            self.product_id = False
