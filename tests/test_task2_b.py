from datetime import date, timedelta
from decimal import Decimal

from models import SkuLocation, Value
from task_02 import task_b, track_sku_presence


class FakeStockLoader:
    def __init__(self, data: dict[date, dict[SkuLocation, Value]]) -> None:
        self.data = data

    def __call__(self, stock_date: date) -> dict[SkuLocation, Value]:
        return self.data.get(stock_date, {})


def test_task_b_calculates_from_raw_stocks() -> None:
    """
    Тестирует task_b на основе исходных файлов остатков (через track_sku_presence):
    - Генерирует 11 валидных новинок, 1 старый товар и 1 опоздавший.
    - Проверяет, что на выходе получается ровно ТОП-10 из валидных позиций.
    """
    start_period = date(2025, 5, 1)
    l_date = date(2025, 7, 1)
    r_date = date(2025, 7, 10)
    fin_date = date(2025, 7, 31)

    raw_history = {}

    # 1. СТАРЫЙ ТОВАР: лежит на складе с мая по июль
    # (должен отсеяться из новинок)
    sku_old = SkuLocation("OLD_ITEM", "LOC_1")
    all_dates = [
        start_period + timedelta(days=x)
        for x in range((fin_date - start_period).days + 1)
    ]
    for d in all_dates:
        raw_history.setdefault(d, {})[sku_old] = Value(
            qty=Decimal("10"),
            cost_amount=Decimal("5000"),
        )

    # 2. ОПОЗДАВШАЯ НОВИНКА: появилась после 10 июля (15.07) и
    # лежит до конца (должна отсеяться)
    sku_late = SkuLocation("LATE_ITEM", "LOC_1")
    late_dates = [
        date(2025, 7, 15) + timedelta(days=x)
        for x in range((fin_date - date(2025, 7, 15)).days + 1)
    ]
    for d in late_dates:
        raw_history.setdefault(d, {})[sku_late] = Value(
            qty=Decimal("10"),
            cost_amount=Decimal("6000"),
        )

    # 3. 11 ВАЛИДНЫХ НОВИНОК: появились 5 июля и лежат без перерывов до 31 июля
    # Стоимость каждой: от 50 до 550
    valid_july_dates = [
        date(2025, 7, 5) + timedelta(days=x)
        for x in range((fin_date - date(2025, 7, 5)).days + 1)
    ]
    for i in range(1, 12):
        sku_new = SkuLocation(f"NEW_{i}", "LOC_1")
        for d in valid_july_dates:
            raw_history.setdefault(d, {})[sku_new] = Value(
                qty=Decimal("1"),
                cost_amount=Decimal(str(i * 50)),
            )

    # 4. ВЫЧИСЛЯЕМ историю через боевой трекер (как это происходит в основном коде)
    loader = FakeStockLoader(raw_history)
    computed_history = track_sku_presence(start_period, fin_date, stock_loader=loader)

    # Забираем финальный срез за 31.07
    fin_stock = raw_history[fin_date]

    # 5. ЗАПУСКАЕМ ТЕСТИРУЕМУЮ ФУНКЦИЮ task_b
    result = task_b(l_date, r_date, fin_date, fin_stock, computed_history)

    # --- СТРОГИЕ ПРОВЕРКИ РЕЗУЛЬТАТА ---
    # Должно остаться ровно 10 позиций (лишняя 11-я отсечена, старая и поздняя пропущены)
    assert len(result) == 10

    # Самая дешевая новинка NEW_1 (cost_amount = 50) должна выпасть из ТОП-10
    assert SkuLocation("NEW_1", "LOC_1") not in result.keys()
    assert SkuLocation("NEW_11", "LOC_1") in result.keys()

    # Проверяем, что невалидные позиции точно не пробились в отчет
    assert sku_old not in result
    assert sku_late not in result
