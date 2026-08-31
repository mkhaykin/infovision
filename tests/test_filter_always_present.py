from datetime import date

import pytest

from models import SkuLocation
from task_02 import TrackValue, filter_always_present_skus


@pytest.fixture
def sku_a() -> SkuLocation:
    return SkuLocation("ITEM_A", "LOC_1")


def test_always_present_perfect(sku_a: SkuLocation) -> None:
    """Товар присутствовал весь период без единого разрыва."""
    start = date(2025, 5, 1)
    fin = date(2025, 7, 31)

    history = {
        sku_a: TrackValue(days_in=92, last_date_in=date(2025, 5, 1), last_date_out=None),
    }

    result = list(filter_always_present_skus(history, start, fin))
    assert sku_a in result


def test_always_present_with_future_disappearance(sku_a: SkuLocation) -> None:
    """Товар лежал весь май, а исчез только в июне. При проверке мая он должен пройти."""
    start = date(2025, 5, 1)
    fin = date(2025, 5, 31)

    history = {
        sku_a: TrackValue(
            days_in=31,
            last_date_in=date(2025, 5, 1),
            last_date_out=date(2025, 6, 15),
        ),
    }

    result = list(filter_always_present_skus(history, start, fin))
    assert sku_a in result


def test_always_present_failed_late_start(sku_a: SkuLocation) -> None:
    """Товар не прерывался, но появился позже start_date. Должен отсеяться."""
    start = date(2025, 5, 1)
    fin = date(2025, 7, 31)

    history = {
        sku_a: TrackValue(days_in=60, last_date_in=date(2025, 6, 1), last_date_out=None),
    }

    result = list(filter_always_present_skus(history, start, fin))
    assert sku_a not in result


def test_always_present_failed_gap_inside(sku_a: SkuLocation) -> None:
    """Товар начался вовремя, но имел разрыв внутри проверяемого периода."""
    start = date(2025, 5, 1)
    fin = date(2025, 7, 31)

    # Товар пропал 15 июня, вернулся 20 июня.
    # Текущий streak_start (20.06) больше start_date
    history = {
        sku_a: TrackValue(
            days_in=87,
            last_date_in=date(2025, 6, 20),
            last_date_out=date(2025, 6, 15),
        ),
    }

    result = list(filter_always_present_skus(history, start, fin))
    assert sku_a not in result
