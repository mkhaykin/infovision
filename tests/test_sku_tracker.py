from datetime import date, timedelta
from decimal import Decimal

import pytest

from models import SkuLocation, Value
from task_02 import track_sku_presence


class FakeStockLoader:
    def __init__(self, data: dict[date, dict[SkuLocation, Value]]) -> None:
        self.data = data

    def __call__(self, stock_date: date) -> dict[SkuLocation, Value]:
        return self.data.get(stock_date, {})


@pytest.fixture
def sku_a() -> SkuLocation:
    return SkuLocation("ITEM_A", "LOC_1")


@pytest.fixture
def dummy_val() -> Value:
    return Value(qty=Decimal("10"), cost_amount=Decimal("100"))


def test_perfect_stock_always_present(sku_a: SkuLocation, dummy_val: Value) -> None:
    """Товар присутствует вообще каждый день."""
    start = date(2025, 7, 1)
    fin = date(2025, 7, 5)

    # Товар есть все 5 дней подряд
    history = {
        date(2025, 7, 1): {sku_a: dummy_val},
        date(2025, 7, 2): {sku_a: dummy_val},
        date(2025, 7, 3): {sku_a: dummy_val},
        date(2025, 7, 4): {sku_a: dummy_val},
        date(2025, 7, 5): {sku_a: dummy_val},
    }

    result = track_sku_presence(start, fin, stock_loader=FakeStockLoader(history))
    metrics = result[sku_a]

    assert metrics.days_in == 5
    assert metrics.last_date_in == date(2025, 7, 1)  # Встал на остаток в первый день
    assert metrics.last_date_out is None  # Ни разу не исчезал


def test_no_last_day(sku_a: SkuLocation, dummy_val: Value) -> None:
    """Появился 2-го и лежит до 4-го."""
    start = date(2025, 7, 1)
    fin = date(2025, 7, 5)

    # Товар есть 3 дня подряд
    history = {
        date(2025, 7, 2): {sku_a: dummy_val},
        date(2025, 7, 3): {sku_a: dummy_val},
        date(2025, 7, 4): {sku_a: dummy_val},
    }

    result = track_sku_presence(start, fin, stock_loader=FakeStockLoader(history))
    metrics = result[sku_a]

    assert metrics.days_in == 3
    assert metrics.last_date_in == date(2025, 7, 2)
    assert metrics.last_date_out == date(2025, 7, 5)


def test_perfect_july_novelty(sku_a: SkuLocation, dummy_val: Value) -> None:
    """Появился 3-го и лежит до конца."""
    start = date(2025, 7, 1)
    fin = date(2025, 7, 5)

    # 1 и 2 июля товара нет, появился только 3 июля
    history = {
        date(2025, 7, 3): {sku_a: dummy_val},
        date(2025, 7, 4): {sku_a: dummy_val},
        date(2025, 7, 5): {sku_a: dummy_val},
    }

    result = track_sku_presence(start, fin, stock_loader=FakeStockLoader(history))
    metrics = result[sku_a]

    assert metrics.days_in == 3
    assert metrics.last_date_in == date(2025, 7, 3)  # Зафиксирован старт в июле
    assert metrics.last_date_out is None  # С тех пор не пропадал


def test_july_comeback_after_june_absence(sku_a: SkuLocation, dummy_val: Value) -> None:
    """Был в мае, исчез в июне, повторно появился в июле и удержался."""
    start = date(2025, 5, 1)
    fin = date(2025, 7, 31)

    july_tail_dates = [
        date(2025, 7, 5) + timedelta(days=x)
        for x in range((date(2025, 7, 31) - date(2025, 7, 5)).days + 1)
    ]

    history = {
        date(2025, 5, 1): {sku_a: dummy_val},  # Был в мае
        # Июнь — пусто (last_date_out должен стать 2025-05-02)
    }
    for d in july_tail_dates:
        # тут заполняем полный период за июль
        history[d] = {sku_a: dummy_val}

    result = track_sku_presence(start, fin, stock_loader=FakeStockLoader(history))
    metrics = result[sku_a]

    assert metrics.days_in == len(july_tail_dates) + 1
    assert metrics.last_date_out == date(2025, 5, 2)
    assert metrics.last_date_in == date(2025, 7, 5)
    assert metrics.last_date_out < metrics.last_date_in


def test_july_gap_should_fail_b(sku_a: SkuLocation, dummy_val: Value) -> None:
    """Появился в июле, но внутри июля был разрыв."""
    start = date(2025, 7, 1)
    fin = date(2025, 7, 15)

    history = {
        date(2025, 7, 2): {sku_a: dummy_val},  # Появился
        date(2025, 7, 10): {sku_a: dummy_val},  # Опять на складе
        date(2025, 7, 15): {sku_a: dummy_val},  # Опять Вернулся на склад
    }

    result = track_sku_presence(start, fin, stock_loader=FakeStockLoader(history))
    metrics = result[sku_a]

    assert metrics.days_in == 3
    assert metrics.last_date_out == date(2025, 7, 11)
    assert metrics.last_date_in == date(2025, 7, 15)


def test_disappeared_before_july_should_not_break_logic(
    sku_a: SkuLocation,
    dummy_val: Value,
) -> None:
    """Товар был активен только в мае, а в июне и июле отсутствовал."""
    start = date(2025, 5, 1)
    fin = date(2025, 7, 31)

    # Товар был только 1 и 2 мая
    history = {
        date(2025, 5, 1): {sku_a: dummy_val},
        date(2025, 5, 2): {sku_a: dummy_val},
    }

    result = track_sku_presence(start, fin, stock_loader=FakeStockLoader(history))
    metrics = result[sku_a]

    # Проверяем, что за июнь-июль метрики не перезаписались и не сломались
    assert metrics.days_in == 2
    assert metrics.last_date_in == date(2025, 5, 1)
    assert metrics.last_date_out == date(2025, 5, 3)  # Исчез 3 мая
