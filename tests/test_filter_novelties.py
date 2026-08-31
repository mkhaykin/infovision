from datetime import date

import pytest

from models import SkuLocation
from task_02 import TrackValue, filter_novelties_skus


@pytest.fixture
def sku_b() -> SkuLocation:
    return SkuLocation("ITEM_B", "LOC_1")


def test_novelty_perfect(sku_b: SkuLocation) -> None:
    """Идеальный случай: товар впервые появился в первой декаде июля и не исчезал."""
    win_start = date(2025, 7, 1)
    win_end = date(2025, 7, 10)
    fin = date(2025, 7, 31)

    history = {
        sku_b: TrackValue(
            days_in=27,
            last_date_in=date(2025, 7, 5),
            last_date_out=None,
        ),
    }

    result = list(filter_novelties_skus(history, win_start, win_end, fin))
    assert sku_b in result


def test_novelty_comeback_from_past(sku_b: SkuLocation) -> None:
    """Сложный случай: товар был в мае, исчез в июне,
    совершил камбэк 5 июля и удержался."""
    win_start = date(2025, 7, 1)
    win_end = date(2025, 7, 10)
    fin = date(2025, 7, 31)

    history = {
        sku_b: TrackValue(
            days_in=28,
            last_date_in=date(2025, 7, 5),
            last_date_out=date(2025, 6, 1),
        ),
    }

    result = list(filter_novelties_skus(history, win_start, win_end, fin))
    assert sku_b in result


def test_novelty_failed_too_late(sku_b: SkuLocation) -> None:
    """Товар появился без разрывов, но позже первой декады (15 июля). Отсекаем."""
    win_start = date(2025, 7, 1)
    win_end = date(2025, 7, 10)
    fin = date(2025, 7, 31)

    history = {
        sku_b: TrackValue(days_in=17, last_date_in=date(2025, 7, 15), last_date_out=None),
    }

    result = list(filter_novelties_skus(history, win_start, win_end, fin))
    assert sku_b not in result


def test_novelty_failed_gap_in_july(sku_b: SkuLocation) -> None:
    """Товар зашел 2 июля, но имел разрыв внутри июля (последний камбэк был 15.07)."""
    win_start = date(2025, 7, 1)
    win_end = date(2025, 7, 10)
    fin = date(2025, 7, 31)

    history = {
        sku_b: TrackValue(
            days_in=20,
            last_date_in=date(2025, 7, 15),
            last_date_out=date(2025, 7, 6),
        ),
    }

    result = list(filter_novelties_skus(history, win_start, win_end, fin))
    assert sku_b not in result
