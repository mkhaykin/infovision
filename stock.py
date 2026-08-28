"""
При текущих вводных мы вполне можем прочитать все данные за месяц за один раз
и далее хранить их в условном словаре или, что удобнее, в pandas (представленные
файлы не превышают 40Мб). Но сделаем предположение, что мы не можем забрать все
продажи за месяц в ОЗУ одномоментно (для больших данных это скорее правило).
Таким образом мы платим множеством чтений файла за отсутствия риска упасть
из-за нехватки памяти.

Так же сделано предположение, что агрегированные остатки _точно_ уберутся в ОЗУ,
сейчас их размер не превышает 6 Мб.

При расчете оставил побочный эффект: всегда считаем в одном словаре. Но если
принять, что скрипт работает как линейная утилита «запустился, посчитал,
сохранился», экономия на аллокациях памяти и снижение нагрузки уборщик даст
приличный выигрыш.
Так же не чистим нулевые остатки (в ТЗ нет указаний по этому поводу).
"""

import csv
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Final, Generator, NamedTuple, Optional

PATH_SOURCE = Path(__file__).parent
PATH_TRANS = PATH_SOURCE / "invent_trans"
PATH_STOCK = PATH_SOURCE / "stock"

DELIMITER: Final = ";"
ENCODING: Final = "utf-8"
QUOTING: Final = csv.QUOTE_NONNUMERIC

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d "
    "| %(levelname)-8s "
    "| [%(process)d:%(threadName)s] "
    "| %(name)s "
    "| %(filename)s:%(lineno)d -> %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


class SkuLocation(NamedTuple):
    item_id: str
    location_id: str


class Value(NamedTuple):
    qty: Decimal = Decimal(0)
    cost_amount: Decimal = Decimal(0)

    def __add__(self, other: tuple) -> Value:
        if not isinstance(other, Value):
            return NotImplemented

        return Value(self.qty + other.qty, self.cost_amount + other.cost_amount)


class Row(NamedTuple):
    item_id: str
    location_id: str
    trans_date: str
    qty: str
    cost_amount: str


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


def _rows(
    filename: Path,
    filtered_date: Optional[str] = None,
    has_header: bool = True,
) -> Generator[Row, None, None]:
    if not filename.is_file():
        logger.error("Файл %s не найден", filename)

    with open(filename, encoding=ENCODING) as fr:
        reader = csv.reader(fr, delimiter=DELIMITER)

        if has_header:
            header = tuple(next(reader))
            if Row._fields != tuple(header):
                raise ValueError(
                    f"Проблема с файлом `{filename}`: не совпадают заголовки.",
                )

        for line in reader:
            row = Row(*line)
            if filtered_date is None or row.trans_date == filtered_date:
                yield row


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
        for i, row in enumerate(_rows(invent_trans_file), 1):
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


def _load_stock(stock_date: date) -> dict[SkuLocation, Value]:
    stock: dict[SkuLocation, Value] = {}
    trans_date_set = set()

    s_date = stock_date.strftime("%Y_%m_%d")
    stock_file = PATH_STOCK / f"stock_{s_date}.csv"

    logger.debug("Читаем %s", stock_file)
    count = 0
    for stock_item in _rows(stock_file):
        # считаем, что повторов в остатках быть не должно
        stock[
            SkuLocation(
                stock_item.item_id,
                stock_item.location_id,
            )
        ] = Value(
            Decimal(stock_item.qty),
            Decimal(stock_item.cost_amount),
        )
        trans_date_set.add(stock_item.trans_date)
        count += 1

    logger.debug(
        "Прочитаны остатки за %s, количество дней: %d, строк: %d, позиций: %d",
        ", ".join(sorted(trans_date_set)),
        len(trans_date_set),
        count,
        len(stock),
    )

    if len(trans_date_set) > 1:
        raise ValueError(
            "Ерунда в начальных остатках с датами > 1",
        )

    return stock


def main() -> None:
    start_date = datetime(2025, 4, 30).date()
    fin_date = datetime(2025, 7, 31).date()

    stock = _load_stock(start_date)
    trans_date = start_date
    while trans_date < fin_date:
        trans_date = trans_date + timedelta(days=1)
        stock = _day_process(trans_date, stock)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Oops... Something wrong!")
