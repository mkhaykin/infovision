"""
При текущих вводных (размер файлов не превышает 40 Мб) данные за один месяц
гарантированно и безопасно помещаются в оперативную память. Чтобы избавиться от
повторных дисковых операций, в решении реализован
ленивый кэширующий слой уровня модуля для файла транзакций текущего периода.

В ОЗУ сохраняется полный массив транзакций месяца (а не сжатые/агрегированные
изменения). Это сделано ради сохранения простоты, лаконичности кода и избавления от
избыточных предварительных группировок. При переходе на следующий месяц кэш полностью
очищается, что страхует систему от утечек памяти при сколь угодно длинном периоде расчёта.

При расчете оставлен побочный эффект: всегда считаем в одном словаре. Но если
принять, что скрипт работает как линейная утилита «запустился, посчитал,
сохранился», экономия на аллокациях памяти и снижение нагрузки уборщик даст
приличный выигрыш.

Так же не чистим нулевые остатки (в ТЗ нет указаний по этому поводу).
"""

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Generator

from logger import logger
from models import SkuLocation, Value
from settings import DELIMITER, ENCODING, PATH_STOCK, PATH_TRANS, QUOTING
from utils import load_stock, rows


@dataclass(slots=True)
class CachedPeriod:
    start: date = date.max
    fin: date = date.min

    def __bool__(self) -> bool:
        return self.start <= self.fin

    def __str__(self) -> str:
        if not self:
            return super().__str__()
        return f"с {self.start.strftime('%Y-%m-%d')} по {self.fin.strftime('%Y-%m-%d')}"


# данные о периоде кеширования
_CACHED_PERIOD: CachedPeriod = CachedPeriod()

# хранение кеша за месяц
_CACHED_RAW_DATA: dict[date, list[tuple[SkuLocation, Value]]] = {}


def get_last_day_of_month(some_date: date) -> date:
    if some_date.month == 12:
        next_month = some_date.replace(year=some_date.year + 1, month=1, day=1)
    else:
        next_month = some_date.replace(month=some_date.month + 1, day=1)

    return next_month - timedelta(days=1)


def _day_process(
    trans_date: date,
    stock: dict[SkuLocation, Value],
) -> dict[SkuLocation, Value]:
    for sl, value in _invent(trans_date):
        stock[sl] = stock.get(sl, Value()) + value

    _save_stock(trans_date, stock)
    return stock


def _invent(
    trans_date: date,
) -> Generator[tuple[SkuLocation, Value], None, None]:
    if not _CACHED_PERIOD.start <= trans_date <= _CACHED_PERIOD.fin:
        _CACHED_RAW_DATA.clear()
        _CACHED_PERIOD.start = date(trans_date.year, trans_date.month, 1)
        _CACHED_PERIOD.fin = get_last_day_of_month(trans_date)

        s_date_short = trans_date.strftime("%Y_%m")
        invent_trans_file = PATH_TRANS / f"invent_trans_{s_date_short}.csv"

        logger.debug("Читаем %s", invent_trans_file)
        count = 0
        skipped = 0
        for i, row in enumerate(rows(invent_trans_file), 1):
            try:
                td = datetime.strptime(row.trans_date, "%Y-%m-%d").date()
                sl = SkuLocation(row.item_id, row.location_id)
                value = Value(Decimal(row.qty), Decimal(row.cost_amount))

                _CACHED_RAW_DATA.setdefault(td, []).append((sl, value))
                count += 1
            except ValueError:
                logger.warning("Ошибка конвертации в строке %d", i)
                skipped += 1
                continue

        logger.debug(
            "Закэширован период: %s, количество дней: %d, строк: %d, пропущено: %d",
            _CACHED_PERIOD,
            len(_CACHED_RAW_DATA),
            count,
            skipped,
        )

    yield from _CACHED_RAW_DATA.get(trans_date, [])


def _save_stock(trans_date: date, stock: dict[SkuLocation, Value]) -> None:
    s_date = trans_date.strftime("%Y-%m-%d")
    stock_file = PATH_STOCK / f"stock_{trans_date.strftime('%Y_%m_%d')}.csv"

    logger.debug("Сохраняем %s", stock_file)
    with open(stock_file, "w", encoding=ENCODING) as fw:
        writer = csv.writer(fw, delimiter=DELIMITER, quoting=QUOTING)
        header = ("item_id", "location_id", "trans_date", "qty", "cost_amount")
        writer.writerow(header)
        for sl, value in stock.items():
            item = [sl.item_id, sl.location_id, s_date, value.qty, value.cost_amount]
            writer.writerow(item)


def main() -> None:
    start_date = datetime(2025, 4, 30).date()
    fin_date = datetime(2025, 7, 31).date()

    stock = load_stock(start_date)
    trans_date = start_date
    while trans_date < fin_date:
        trans_date = trans_date + timedelta(days=1)
        stock = _day_process(trans_date, stock)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Oops... Something wrong!")
