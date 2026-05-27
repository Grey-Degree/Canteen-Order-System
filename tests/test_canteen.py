"""快餐订餐系统的单元测试。

只测不依赖键盘输入的纯逻辑部分（交互式的 choose_food / interactive_system 不在此测）。
运行方式（在项目根目录）：
    python -m unittest discover -s tests
或直接：
    python tests/test_canteen.py
"""
import sys
import tempfile
import unittest
from pathlib import Path

# 把项目根目录加入导入路径，这样无论从哪运行都能 import 到主模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from food_canteen import Customer, Employee, Food, MenuError, OrderStore, SHOP_MENUS


class TestFood(unittest.TestCase):
    def test_str_contains_name_and_price(self):
        food = Food("豆浆", 3.0)
        self.assertIn("豆浆", str(food))
        self.assertIn("3.00", str(food))


class TestCustomer(unittest.TestCase):
    def setUp(self):
        self.customer = Customer("张三")
        self.customer.received_foods = [
            Food("牛肉面", 18.0),
            Food("牛肉面", 18.0),
            Food("抄手", 12.0),
        ]

    def test_total_price(self):
        self.assertEqual(self.customer.total_price, 48.0)

    def test_len(self):
        self.assertEqual(len(self.customer), 3)

    def test_order_summary_merges_same_dish(self):
        summary = self.customer.order_summary
        self.assertEqual(summary["牛肉面"], 2)
        self.assertEqual(summary["抄手"], 1)


class TestEmployee(unittest.TestCase):
    def setUp(self):
        self.employee = Employee("面馆", SHOP_MENUS["面馆"])

    def test_take_order_returns_food_with_price(self):
        food = self.employee.take_order("牛肉面")
        self.assertIsInstance(food, Food)
        self.assertEqual(food.price, 18.0)

    def test_unknown_dish_raises_menu_error(self):
        with self.assertRaises(MenuError):
            self.employee.take_order("佛跳墙")

    def test_default_menu_when_none(self):
        employee = Employee("某店")
        self.assertEqual(employee.menu, SHOP_MENUS["默认"])


class TestOrderStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "orders.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_read_only_does_not_create_file(self):
        # 纯读取（看历史）不应该把文件写出来——这是修复过的 bug
        with OrderStore(self.path) as store:
            self.assertEqual(store.history(), [])
        self.assertFalse(self.path.exists())

    def test_append_persists_to_disk(self):
        customer = Customer("李四")
        customer.received_foods = [Food("豆浆", 3.0), Food("油条", 2.0)]
        with OrderStore(self.path) as store:
            store.append(customer, "早餐铺")
        self.assertTrue(self.path.exists())

        # 重新打开，数据应当还在
        with OrderStore(self.path) as store:
            records = store.history()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["customer"], "李四")
        self.assertEqual(records[0]["total"], 5.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
