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
        product_id = False
        for line in self.contract_id.order_line:
            product_id = line.product_id
            break
        self.product_id = product_id

    @api.multi
    def fun_transfer(self):
        self.stock_picking_id = self.env['stock.picking'].search([('origin', '=', self.contract_id.name), ('state', '=', 'assigned')], order='date', limit=1)
        if self.stock_picking_id:
            picking = [self.stock_picking_id.id]
            if self.delivered < self.hired:
                self._do_enter_transfer_details(picking, self.stock_picking_id, self.clean_kilos, self.location_id)
            else:
                self._do_enter_transfer_details(picking, self.stock_picking_id, self.clean_kilos + self.pending * 1000 , self.location_id)
                self.auxiliary_contract = self.env['purchase.order'].create({'partner_id': self.contract_id.partner_id.id,
                                                                             'location_id': self.contract_id.location_id.id,
                                                                             'pricelist_id': self.contract_id.pricelist_id.id})
                self.auxiliary_contract.contract_type = 'surplus'
                self.auxiliary_contract.order_line = self.env['purchase.order.line'].create({
                    'order_id': self.auxiliary_contract.id,
                    'product_id': self.contract_id.order_line[0].product_id.id,
                    'name': self.contract_id.order_line[0].name,
                    'date_planned': self.contract_id.order_line[0].date_planned,
                    'company_id': self.contract_id.order_line[0].company_id.id,
                    'product_qty': (-self.pending),
                    'price_unit': self.contract_id.order_line[0].price_unit,
                    'product_uom': self.contract_id.order_line[0].product_uom.id,
                })
                self.fun_ship()

    @api.multi
    def fun_ship(self):
        stock_picking_id_cancel = self.env['stock.picking'].search([('origin', '=', self.contract_id.name), ('state', '=', 'assigned')], order='date', limit=1)
        if stock_picking_id_cancel:
            stock_picking_id_cancel.action_cancel()

    @api.multi
    def _do_enter_transfer_details(self, picking_id, picking, clean_kilos, location_id, context=None):
        if not context:
            context = {}
        else:
            context = context.copy()
        context.update({
            'active_model': self._name,
            'active_ids': picking_id,
            'active_id': len(picking_id) and picking_id[0] or False
        })

        created_id = self.env['stock.transfer_details'].create({'picking_id': len(picking_id) and picking_id[0] or False})

        items = []
        if not picking.pack_operation_ids:
            picking.do_prepare_partial()
        for op in picking.pack_operation_ids:
            item = {
                'packop_id': op.id,
                'product_id': op.product_id.id,
                'product_uom_id': op.product_uom_id.id,
                'quantity': clean_kilos/1000,
                'package_id': op.package_id.id,
                'lot_id': op.lot_id.id,
                'sourceloc_id': op.location_id.id,
                'destinationloc_id': op.location_dest_id.id,
                'result_package_id': op.result_package_id.id,
                'date': op.date,
                'owner_id': op.owner_id.id,
            }
            if op.product_id:
                items.append(item)
        created_id.item_ids = items
        created_id.do_detailed_transfer()
