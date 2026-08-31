from datetime import date
from decimal import Decimal

from models import SkuLocation, Value
from task_02 import TrackValue, task_a


def test_task_a_returns_top_10_by_location() -> None:
    """
    Тестирует task_a:
    - Отбирает только товары, бывшие на остатках всегда.
    - Корректно группирует и обрезает выборку до ТОП-10 внутри каждого подразделения.
    - Игнорирует товары, отсутствующие в fin_stock.
    """
    start_date = date(2025, 5, 1)
    fin_date = date(2025, 7, 31)

    history = {}
    fin_stock = {}

    # Локация 1: Создаем 11 абсолютно валидных товаров (стоимость от 100 до 1100)
    for i in range(1, 12):
        sku = SkuLocation(f"ITEM_{i}", "LOC_1")
        history[sku] = TrackValue(days_in=92, last_date_in=start_date, last_date_out=None)
        fin_stock[sku] = Value(qty=Decimal("1"), cost_amount=Decimal(str(i * 100)))

    # Локация 2: Один валидный товар (стоимость 500)
    sku_loc2 = SkuLocation("ITEM_LOC2", "LOC_2")
    history[sku_loc2] = TrackValue(
        days_in=92,
        last_date_in=start_date,
        last_date_out=None,
    )
    fin_stock[sku_loc2] = Value(qty=Decimal("5"), cost_amount=Decimal("500"))

    # Невалидный товар: Высокая стоимость, но по истории должен отсеяться
    sku_broken = SkuLocation("ITEM_BROKEN", "LOC_1")
    history[sku_broken] = TrackValue(
        days_in=5,
        last_date_in=date(2025, 7, 25),
        last_date_out=None,
    )
    fin_stock[sku_broken] = Value(qty=Decimal("10"), cost_amount=Decimal("9999"))

    # Запускаем расчет (теперь функция возвращает чистый dict[SkuLocation, Value])
    result = task_a(start_date, fin_date, fin_stock, history)

    # --- ПРОВЕРКИ ---
    # 1. Проверяем общее количество: 10 из первой локации + 1 из второй = 11 позиций всего
    assert len(result) == 11

    # 2. Выделяем ключи для проверки по подразделениям
    loc1_keys = [sku for sku in result.keys() if sku.location_id == "LOC_1"]
    loc2_keys = [sku for sku in result.keys() if sku.location_id == "LOC_2"]

    assert len(loc1_keys) == 10
    assert len(loc2_keys) == 1

    # 3. Проверяем, что самый дешёвый товар (ITEM_1 со стоимостью 100) отсеялся из ТОП-10
    assert SkuLocation("ITEM_1", "LOC_1") not in loc1_keys
    assert SkuLocation("ITEM_11", "LOC_1") in loc1_keys  # Самый дорогой на месте

    # 4. Проверяем, что невалидный товар не попал в результат, несмотря на стоимость
    assert sku_broken not in result
