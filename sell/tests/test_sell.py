# -*- coding: utf-8 -*-
from openerp.tests.common import TransactionCase
from openerp.exceptions import except_orm
from datetime import datetime
ISODATEFORMAT = '%Y-%m-%d'
ISODATETIMEFORMAT = "%Y-%m-%d %H:%M:%S"


class Test_sell(TransactionCase):

    def setUp(self):
        super(Test_sell, self).setUp()
        self.order = self.env.ref('sell.sell_order_1')
        self.warehouse_dest_id = self.env.ref('warehouse.warehouse_customer')
        self.order_2 = self.env.ref('sell.sell_order_2')
        self.order_3 = self.env.ref('sell.sell_order_3')
        self.sell_order_line = self.env.ref('sell.sell_order_line_2_3')
        self.bank = self.env.ref('core.alipay')
        self.warehouse_id = self.env.ref('warehouse.hd_stock')
        self.others_warehouse_id = self.env.ref('warehouse.warehouse_others')
        self.goods = self.env.ref('goods.cable')
        self.goods.default_wh = self.warehouse_id.id
        self.partner = self.env.ref('core.lenovo')
        warehouse_obj = self.env.ref('warehouse.wh_in_whin0')
        warehouse_obj.approve_order()
        self.order_2.sell_order_done()
        self.sell_delivery = self.env['sell.delivery'].search([('order_id', '=', self.order_2.id)])
        self.sell_delivery.write({"date_due": (datetime.now()).strftime(ISODATEFORMAT)})

    def test_sell(self):
        ''' 测试销售订单  '''
        # 正常销售订单

        # receipt = self.env['sell.delivery'].search([('order_id', '=', order.id)])

        # 没有订单行的销售订单
        partner_objs = self.env.ref('core.jd')
        vals = {'partner_id': partner_objs.id}
        order_no_line = self.env['sell.order'].create(vals)
        self.order.sell_order_done()
        # 计算字段的测试
        self.assertEqual(self.order.amount, 151600.00)
        # 正常的反审核
        self.order.sell_order_draft()
        # 正常的  审核销售订单
        # 正常审核后会生成 销售发货单

        self.sell_delivery.sell_delivery_done()
        self.sell_delivery.receipt = 0
        self.sell_delivery._get_sell_money_state()
        self.sell_delivery.amount
        self.assertEqual(self.sell_delivery.money_state, u'未收款')
        self.sell_delivery.receipt = self.sell_delivery.amount
        self.sell_delivery._get_sell_money_state()
        self.assertEqual(self.sell_delivery.money_state, u'全部收款')

        self.order_2.unlink()

        with self.assertRaises(except_orm):
            self.order_2.sell_order_draft()

        # 没有订单行的销售订单
        with self.assertRaises(except_orm):
            order_no_line.sell_order_done()

        for goods_state in [(u'未出库', 0), (u'部分出库', 1), (u'全部出库', 10000)]:
            self.order.line_ids.write({'quantity_out': goods_state[1]})
            self.assertEqual(self.order.goods_state, goods_state[0])
            if goods_state[1] != 0:
                with self.assertRaises(except_orm):
                    self.order.sell_order_done()
                    self.order.sell_order_draft()
            else:
                self.order.sell_order_done()
                self.order.sell_order_draft()

        # 销售退货单的测试
        #
        self.order_3.write({'type': "return"})
        self.order_3.sell_order_done()

        # sell.order onchange test
        self.order.discount_rate = 10
        self.order.onchange_discount_rate()
        self.assertEqual(self.order.discount_amount, 15163.2)
        self.order.unlink()

    def test_sale_order_line_compute(self):

        vals = {
            'order_id': self.order_2.id,
            'goods_id': self.goods.id
        }
        sell_order_line = self.env['sell.order.line']
        sell_order_line._default_warehouse_dest()

        sell_order_line_default = sell_order_line.with_context({'warehouse_dest_type': u'customer'}).create(vals)

        # 测试 产品自动带出 默认值 的仓库
        self.assertEqual(sell_order_line_default.warehouse_dest_id.id,  self.warehouse_dest_id.id)
        # self.assertEqual(sell_order_line_default.warehouse_id.id,  self.warehouse_id.id)

        # sell_order_line 的计算字段的测试
        self.assertEqual(self.sell_order_line.amount, 90)  # tax_amount subtotal
        self.assertEqual(self.sell_order_line.tax_rate, 17.0)
        self.assertEqual(self.sell_order_line.tax_amount, 15.3)
        self.assertEqual(self.sell_order_line.subtotal, 105.3)

        # onchange test
        self.sell_order_line.goods_id = self.env.ref('goods.mouse')
        # 折扣率 on_change 变化
        self.sell_order_line.discount_rate = 20
        # 通过onchange来改变 goods_id
        self.sell_order_line.onchange_goods_id()
        self.sell_order_line.onchange_discount_rate()

        self.assertEqual(self.sell_order_line.amount, 80)

    def test_sell_delivery(self):
        sell_delivery = self.env['sell.delivery'].search([('order_id', '=', self.order_2.id)])
        sell_delivery.discount_rate = 10
        sell_delivery.write({"date_due": (datetime.now()).strftime(ISODATEFORMAT), 'bank_account_id': self.bank.id})
        sell_delivery.onchange_discount_rate()

        self.assertEqual(sell_delivery.money_state, u'未收款')
        self.assertEqual(sell_delivery.discount_amount, 10.53)
        self.assertEqual(sell_delivery.amount, 94.77)

        sell_delivery.amount = 94.8
        # 销售发货单 的确认
        sell_delivery.receipt = -222
        sell_delivery.sell_delivery_done()

        self.assertEqual(sell_delivery.amount, 913.77)
        self.assertEqual(sell_delivery.money_state, u'部分收款')
        # with self.assertRaises(except_orm):
        #     sell_delivery.receipt = -222
        #     sell_delivery.sell_delivery_done()
        # 确认后改变 状态金额

        # self.assertEqual(sell_delivery.money_state, u'未收款')

    def test_sell_delievery_in(self):
        vals = {'partner_id': self.partner.id, 'is_return': True, 'date_due': (datetime.now()).strftime(ISODATEFORMAT),
                'line_in_ids': [(0, 0, {'goods_id': self.goods.id, 'warehouse_dest_id': self.others_warehouse_id.id,
                                        'price': 100, 'warehouse_id': self.warehouse_id.id, 'goods_qty': 5})]}

        sell_delivery_obj = self.env['sell.delivery'].create(vals)
        for sell_delivery_line_obj in sell_delivery_obj.line_in_ids:
            sell_delivery_line_obj.discount_rate = 10
            sell_delivery_line_obj.onchange_discount_rate()
            self.assertEqual(sell_delivery_line_obj.discount_amount, 50)
        # 退货单折扣率测试
        sell_delivery_obj.discount_rate = 10
        sell_delivery_obj.onchange_discount_rate()
        self.assertEqual(sell_delivery_obj.discount_amount, 52.65)
        #  结算账户 需要输入付款额 测试
        sell_delivery_obj.bank_account_id = self.bank.id
        self.receipt = False
        with self.assertRaises(except_orm):
            sell_delivery_obj.sell_delivery_done()
        # 付款状态测试 未退款
        sell_delivery_obj._get_sell_return_state()
        self.assertEqual(sell_delivery_obj.return_state, u'未退款')
        sell_delivery_obj.state = 'done'
        self.receipt = 0
        sell_delivery_obj._get_sell_return_state()
        self.assertEqual(sell_delivery_obj.return_state, u'未退款')
        # 部分退款
        sell_delivery_obj.receipt = 20

        sell_delivery_obj._get_sell_return_state()
        self.assertEqual(sell_delivery_obj.return_state, u'部分退款')
        #  全部退款
        sell_delivery_obj.receipt = sell_delivery_obj.amount
        sell_delivery_obj._get_sell_return_state()
        self.assertEqual(sell_delivery_obj.return_state, u'全部退款')

    def test_no_account_id(self):
        self.sell_delivery.bank_account_id = False
        self.sell_delivery.receipt = 20
        with self.assertRaises(except_orm):
            self.sell_delivery.sell_delivery_done()

    def test_done_twice(self):
        self.sell_delivery.sell_delivery_done()
        with self.assertRaises(except_orm):
            self.sell_delivery.sell_delivery_done()

    def test_sale_usage_return(self):
        vals = {'partner_id': self.partner.id, 'is_return': True, 'date_due': (datetime.now()).strftime(ISODATEFORMAT),
                'line_in_ids': [(0, 0, {'goods_id': self.goods.id, 'warehouse_dest_id': self.others_warehouse_id.id,
                                        'price': 100, 'warehouse_id': self.warehouse_id.id, 'goods_qty': 5})],
                'cost_line_ids': [(0, 0, {'partner_id': self.partner.id,
                                          'category_id': self.env.ref('core.cat_freight').id,
                                          'amount': 50})]}

        sell_delivery_obj = self.env['sell.delivery'].create(vals)
        sell_delivery_obj.sell_delivery_done()

    def test_account_id_receipt(self):
        self.sell_delivery.receipt = 100000
        self.sell_delivery.amount = 10
        self.sell_delivery.bank_account_id = self.bank.id
        with self.assertRaises(except_orm):
            self.sell_delivery.sell_delivery_done()

    def test_sell_done(self):
        ''' 测试审核销货订单  '''
        order = self.env.ref('sell.sell_order_1')

        # 审核销货订单
        order.sell_order_done()
        with self.assertRaises(except_orm):
            order.sell_order_done()

    def test_sell_draft(self):
        ''' 测试反审核销货订单  '''
        order = self.env.ref('sell.sell_order_1')

        # 反审核销货订单
        order.sell_order_done()
        order.sell_order_draft()
        with self.assertRaises(except_orm):
            order.sell_order_draft()
