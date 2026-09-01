from datetime import date
from decimal import Decimal
from typing import Generator

from task_03 import SkuLocation, StockRowIn, Value, aggregate_stock_data


def test_aggregate_stock_data_removes_zeros_and_deduplicates() -> None:
    """
    Проверяет, что оригинальная функция aggregate_stock_data корректно
    обрабатывает поток данных от ридера, отсекая нули и дубликаты остатков.
    """
    sku = SkuLocation("ITEM_A", "LOC_1")
    start_date = date(2025, 7, 1)
    fin_date = date(2025, 7, 5)

    # Готовим фиксированный тестовый набор данных, распределенный по дням
    mock_db = {
        date(2025, 7, 1): [
            StockRowIn(sku, date(2025, 7, 1), Value(Decimal("10.0"))),
        ],
        date(2025, 7, 2): [
            StockRowIn(sku, date(2025, 7, 2), Value(Decimal("10.0"))),
        ],  # Повтор (игнор в states)
        date(2025, 7, 3): [
            StockRowIn(sku, date(2025, 7, 3), Value(Decimal("0.0"))),
        ],  # Ноль (полный игнор)
        date(2025, 7, 4): [
            StockRowIn(sku, date(2025, 7, 4), Value(Decimal("5.0"))),
        ],  # Новое состояние (запись)
        date(2025, 7, 5): [
            StockRowIn(sku, date(2025, 7, 5), Value(Decimal("10.0"))),
        ],  # Перепад обратно (запись)
    }

    # Создаем управляемый mock-ридер, который заменяет чтение с диска
    def mock_stock_reader(stock_date: date) -> Generator[StockRowIn, None, None]:
        if stock_date in mock_db:
            for item in mock_db[stock_date]:
                yield item

    result = aggregate_stock_data(start_date, fin_date, stock_reader=mock_stock_reader)

    assert sku in result, "Позиция должна быть добавлена в итоговый словарь"

    assert result[sku].count_days == 4, (
        "Должно быть ровно 4 дня (минус 1 день с нулевым остатком)"
    )
    assert result[sku].sum_qty == Decimal("35.0"), (
        "Сумма ненулевых остатков должна быть 10 + 10 + 5 + 10 = 35"
    )

    expected_states = [
        # Первое появление
        (date(2025, 7, 1), Decimal("10.0")),
        # Падение до 5 (после пропущенного нуля)
        (date(2025, 7, 4), Decimal("5.0")),
        # Возврат к 10
        (date(2025, 7, 5), Decimal("10.0")),
    ]
    assert result[sku].states == expected_states, (
        "Список зафиксированных изменений остатка не совпадает"
    )
