from datetime import date
from decimal import Decimal

from task_03 import SkuLocation, StockHistory, find_stock_incidents


def test_find_stock_incidents_strict_boundary() -> None:
    """
    Проверяет математику: инцидент должен срабатывать ТОЛЬКО если
    остаток СТРОГО МЕНЬШЕ 25% от среднего. Равенство пограничного значения не срабатывает.
    """
    sku = SkuLocation("ITEM_B", "LOC_1")

    # Настройки для теста:
    # 4 дня по 10 шт = 40 шт сумма / 4 дня = 10.000 среднее. Порог 25% = 2.500
    test_data = {
        sku: StockHistory(
            sum_qty=Decimal("40.0"),
            count_days=4,
            states=[
                (date(2025, 7, 1), Decimal("10.0")),
                # Ровно 25% -> НЕ инцидент (нужно строго меньше)
                (date(2025, 7, 2), Decimal("2.5")),
                # Строго меньше 2.5 -> ИНЦИДЕНТ!
                (date(2025, 7, 3), Decimal("2.499")),
                # Тоже меньше, но мы должны остановиться на первом (break)
                (date(2025, 7, 4), Decimal("1.0")),
            ],
        ),
    }

    incidents = list(find_stock_incidents(test_data))

    assert len(incidents) == 1
    assert incidents[0].trans_date == date(2025, 7, 3)
    assert incidents[0].qty == Decimal("2.499")
    assert incidents[0].avg_qty == Decimal("10.000")


def test_find_stock_incidents_no_incidents_recorded() -> None:
    """
    Проверяет, что если за весь месяц остаток ни разу не падал ниже 25% порога,
    функция ничего не возвращает.
    """
    sku = SkuLocation("ITEM_C", "LOC_1")

    # Сумма 300 / 3 дня = 100.000 среднее. Порог 25% = 25.000
    test_data = {
        sku: StockHistory(
            sum_qty=Decimal("300.0"),
            count_days=3,
            states=[
                (date(2025, 7, 1), Decimal("100.0")),
                (date(2025, 7, 10), Decimal("25.001")),  # Чуть выше порога -> чисто
            ],
        ),
    }

    incidents = list(find_stock_incidents(test_data))
    assert len(incidents) == 0


def test_find_stock_incidents_first_day_is_incident() -> None:
    """
    Проверяет, что если просадка была в самый первый день месяца,
    функция корректно зафиксирует дату именно первого дня.
    """
    sku = SkuLocation("ITEM_D", "LOC_2")

    # Сумма 100 / 4 дня = 25.000 среднее. Порог 25% = 6.250.
    test_data = {
        sku: StockHistory(
            sum_qty=Decimal("100.0"),
            count_days=4,
            states=[
                # Ниже 6.250 -> Сразу инцидент первого дня!
                (date(2025, 7, 1), Decimal("5.0")),
                # Далее норм
                (date(2025, 7, 2), Decimal("30.0")),
                (date(2025, 7, 3), Decimal("35.0")),
                (date(2025, 7, 4), Decimal("30.0")),
            ],
        ),
    }

    incidents = list(find_stock_incidents(test_data))

    assert len(incidents) == 1
    assert incidents[0].trans_date == date(2025, 7, 1)
    assert incidents[0].qty == Decimal("5.0")
