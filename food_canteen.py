"""快餐订餐系统 - 增强版
整合：字典菜单(1)、推导式(2)、Counter 合并(3)、@property 总价(6)、JSON 持久化(8)
顺手补充：类型注解、pathlib、datetime、上下文管理器、魔术方法、自定义异常、字典派发
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


# 统一把标准输入/输出设为 UTF-8，避免中文菜单在重定向/管道场景下乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")


SHOP_MENUS: dict[str, dict[str, float]] = {
    "早餐铺": {"豆浆": 3.0, "油条": 2.0, "包子": 4.0, "皮蛋粥": 6.0},
    "面馆":   {"牛肉面": 18.0, "炸酱面": 15.0, "青菜面": 10.0, "抄手": 12.0},
    "默认":   {"青椒炒肉": 22.0, "番茄炒蛋": 16.0, "丝瓜蛋汤": 12.0,
              "黑椒牛肉": 28.0, "白斩鸡": 26.0},
}
ORDER_LOG = Path(__file__).parent / "orders.json"


class MenuError(ValueError):
    """自定义异常：让菜单错误更语义化。"""


# === 食物类 ===
class Food:
    def __init__(self, name: str, price: float = 0.0) -> None:
        self.name = name
        self.price = price

    # 魔术方法：让 print(food) 自然输出（语法点：__str__）
    def __str__(self) -> str:
        return f"{self.name}（¥{self.price:.2f}）"

    def __repr__(self) -> str:
        return f"Food(name={self.name!r}, price={self.price})"


# === 顾客类 ===
class Customer:
    def __init__(self, name: str) -> None:
        self.name = name
        self.received_foods: list[Food] = []
        self.selected_foods: list[str] = []

    @property  # @property 装饰器：把方法当属性用（要点6）
    def total_price(self) -> float:
        # 生成器表达式 + 内置 sum（要点2）
        return sum(food.price for food in self.received_foods)

    @property
    def order_summary(self) -> Counter[str]:
        # Counter 合并同款菜（要点3）
        return Counter(food.name for food in self.received_foods)

    def __len__(self) -> int:  # 魔术方法：len(customer) 返回总菜数
        return len(self.received_foods)

    def choose_food(self, menu: dict[str, float]) -> None:
        print("\n===== 可选菜品 =====")
        # 字典推导 + enumerate 把"编号→菜名"建索引（要点2）
        index_map: dict[int, str] = {i: name for i, name in enumerate(menu, 1)}
        # join + 生成器表达式：一次性拼接所有菜行
        print("\n".join(
            f"{i}. {name}（¥{menu[name]:.2f}）"
            for i, name in index_map.items()
        ))
        print("提示：输入菜品编号选菜（可重复点同一道菜），输入 0 结束选菜")

        while True:
            raw = input("请输入编号：").strip()
            try:
                num = int(raw)
            except ValueError:
                print("输入格式错误，请输入数字！")
                continue

            if num == 0:
                if not self.selected_foods:
                    print("暂未选择任何菜品，请至少选一道！")
                    continue
                print("选菜完成！")
                break

            # dict.get 带默认值：拿不到就抛自定义异常
            food_name = index_map.get(num)
            if food_name is None:
                print("编号超出范围，请重新输入！")
                continue
            self.selected_foods.append(food_name)
            print(f"已添加菜品：{food_name}（¥{menu[food_name]:.2f}）")

    def place_order(self, employee: "Employee") -> list[Food]:
        print(f"\n顾客 {self.name} 开始向商户下单...")
        # 列表推导式：把"菜名列表"映射成"Food 对象列表"（要点2）
        self.received_foods = [employee.take_order(name) for name in self.selected_foods]
        return self.received_foods

    def print_order(self) -> None:
        if not self.received_foods:
            print(f"\n{self.name} 还未下单！")
            return
        print(f"\n{self.name} 收到订单：")
        # 先建"菜名→单价"表，避免下面每道菜都重新扫一遍 received_foods
        price_of: dict[str, float] = {f.name: f.price for f in self.received_foods}
        # Counter 合并展示（要点3）：同一道菜只打一行 × 数量
        for name, qty in self.order_summary.items():
            price = price_of[name]
            print(f"  {name} × {qty}   小计 ¥{price * qty:.2f}")
        print(f"  ----------------------------")
        print(f"  合计：¥{self.total_price:.2f}")  # 调用 @property（要点6）


# === 商户类 ===
class Employee:
    def __init__(self, shop_name: str, menu: dict[str, float] | None = None) -> None:
        self.shop_name = shop_name
        # dict.get 取默认菜单（要点1）
        self.menu: dict[str, float] = menu if menu is not None else SHOP_MENUS["默认"]

    def get_menu(self) -> dict[str, float]:
        return self.menu

    def take_order(self, food_name: str) -> Food:
        if food_name not in self.menu:
            raise MenuError(f"{self.shop_name} 没有这道菜：{food_name}")
        print(f"商户 {self.shop_name} 已接单，开始准备 {food_name}...")
        food = Food(food_name, self.menu[food_name])
        print(f"商户 {self.shop_name} 制作完成：{food}")
        return food


# === 订单持久化（要点8）：上下文管理器 + JSON ===
class OrderStore:
    """用 with 语句管理订单文件读写。语法点：__enter__ / __exit__。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: list[dict] = []
        self._dirty = False  # 是否有新数据写入，纯读取时为 False

    def __enter__(self) -> "OrderStore":
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                self._data = json.load(f)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # 只有真正追加过订单才写回，看历史等纯读取操作不会重写文件
        if self._dirty:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)

    def append(self, customer: Customer, shop_name: str) -> None:
        self._data.append({
            "time": datetime.now().isoformat(timespec="seconds"),
            "shop": shop_name,
            "customer": customer.name,
            # 字典推导式 + Counter（要点2、3）
            "items": {name: qty for name, qty in customer.order_summary.items()},
            "total": round(customer.total_price, 2),
        })
        self._dirty = True

    def history(self) -> list[dict]:
        return self._data


# === 订餐管理类 ===
class Lunch:
    def __init__(self, customer: Customer, employee: Employee) -> None:
        self.customer = customer
        self.employee = employee

    def order(self) -> None:
        print("=" * 40)
        print("          开始订餐流程")
        print("=" * 40)
        self.customer.choose_food(self.employee.get_menu())
        self.customer.place_order(self.employee)
        # 下单完落盘（要点8）
        with OrderStore(ORDER_LOG) as store:
            store.append(self.customer, self.employee.shop_name)
        print(f"（订单已写入 {ORDER_LOG.name}）")

    def result(self) -> None:
        self.customer.print_order()

    @staticmethod
    def show_history() -> None:
        if not ORDER_LOG.exists():
            print("\n暂无历史订单。")
            return
        with OrderStore(ORDER_LOG) as store:
            records = store.history()
        if not records:
            print("\n暂无历史订单。")
            return
        print(f"\n========== 历史订单（共 {len(records)} 单）==========")
        for i, rec in enumerate(records, 1):
            # f-string 的 ! 转换 + 字典遍历
            items_str = "、".join(f"{k}×{v}" for k, v in rec["items"].items())
            print(f"{i}. [{rec['time']}] {rec['shop']} - {rec['customer']}：{items_str}  合计 ¥{rec['total']}")


# === 交互式界面 ===
def interactive_system() -> None:
    print("========== 快餐订餐系统 ==========")
    shop_name = input("请输入商户名称（早餐铺 / 面馆 / 其他）：").strip()
    # dict.get 字典派发替代 if/elif（要点1）
    shop_menu = SHOP_MENUS.get(shop_name, SHOP_MENUS["默认"])
    employee = Employee(shop_name or "默认店", shop_menu)

    customer = Customer(input("请输入顾客姓名：").strip() or "匿名顾客")
    lunch = Lunch(customer, employee)

    # 用字典把"选项→处理函数"建表，替代 if/elif 分发（语法点：函数即一等公民）
    actions = {
        "1": lunch.order,
        "2": lunch.result,
        "3": Lunch.show_history,
    }
    while True:
        print("\n----------- 功能菜单 -----------")
        print("1. 执行下单    2. 查看本次订单    3. 查看历史订单    4. 退出")
        choice = input("请输入操作编号：").strip()
        if choice == "4":
            print("\n感谢使用订餐系统，再见！")
            break
        action = actions.get(choice)
        if action is None:
            print("输入错误，请重新输入！")
            continue
        try:
            action()
        except MenuError as e:
            print(f"[菜单错误] {e}")


if __name__ == "__main__":
    interactive_system()
