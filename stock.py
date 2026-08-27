"""
При текущих вводных мы вполне можем прочитать все данные за месяц за один раз
и далее хранить их в условном словаре или, что удобнее, в pandas (представленные
файлы не превышают 40Мб). Но сделаем предположение, что мы не можем забрать все
продажи за месяц в ОЗУ одномоментно (для больших данных это скорее правило).
Таким образом мы платим множеством чтений файла за отсутствия риска упасть
из-за нехватки памяти.

Так же сделано предположение, что агрегированные остатки _точно_ уберутся в ОЗУ,
сейчас их размер не превышает 6 Мб.

При расчете не стал убирать побочный эффект (всегда считаем в одном словаре).
Так же не чистим нулевые остатки (в ТЗ нет указаний по этому поводу).
"""

import calendar
import csv
import logging
from datetime import date, datetime
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
    qtu: Decimal = Decimal(0)
    cost_amount: Decimal = Decimal(0)

    def __add__(self, other: tuple) -> Value:
        if not isinstance(other, Value):
            return NotImplemented

        return Value(self.qtu + other.qtu, self.cost_amount + other.cost_amount)


class Row(NamedTuple):
    item_id: str
    location_id: str
    trans_date: str
    qty: str
    cost_amount: str


def add_months(sourcedate: date, months: int) -> date:
    # stackoverflow
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year, month)[1])
    return datetime(year, month, day)


def _rows(
    filename: Path,
    filtered_date: Optional[str] = None,
    has_header: bool = True,
) -> Generator[Row, None, None]:
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
    s_date = trans_date.strftime("%Y_%m_%d")
    s_date_ = trans_date.strftime("%Y-%m-%d")
    s_date_short = trans_date.strftime("%Y_%m")

    invent_trans_file = PATH_TRANS / f"invent_trans_{s_date_short}.csv"
    stock_file = PATH_STOCK / f"stock_{s_date}.csv"

    logger.debug("Читаем %s", invent_trans_file)
    for i, row in enumerate(_rows(invent_trans_file, s_date, False), 1):
        try:
            sl = SkuLocation(row.item_id, row.location_id)
            value = Value(Decimal(row.qty), Decimal(row.cost_amount))
        except ValueError:
            logger.warning("Ошибка конвертации в строке %d", i)
            continue
        stock[sl] = stock.get(sl, Value()) + value

    logger.debug("Сохраняем %s", stock_file)
    with open(stock_file, "w", encoding=ENCODING) as fw:
        writer = csv.writer(fw, delimiter=DELIMITER, quoting=QUOTING)
        header = ("item_id", "location_id", "trans_date", "qty", "cost_amount")
        writer.writerow(header)
        for sl, value in stock.items():
            item = [sl.item_id, sl.location_id, s_date_, value.qtu, value.cost_amount]
            writer.writerow(item)

    return stock


def _month_process(
    trans_date: date,
    stock: dict[SkuLocation, Value],
) -> dict[SkuLocation, Value]:
    _, last_day = calendar.monthrange(trans_date.year, trans_date.month)
    for current_day in range(1, last_day + 1):
        current_date = datetime(trans_date.year, trans_date.month, current_day)
        stock = _day_process(current_date, stock)
    return stock


def _load_stock(stock_date: date) -> dict[SkuLocation, Value]:
    stock: dict[SkuLocation, Value] = {}
    trans_date_set = set()
    s_date = stock_date.strftime("%Y_%m_%d")
    for stock_item in _rows(PATH_STOCK / f"stock_{s_date}.csv"):
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

    if len(trans_date_set) != 1:
        raise ValueError(
            f"Ерунда в начальных остатках с датами: {sorted(trans_date_set)}",
        )

    return stock


def main() -> None:
    start_date = datetime(2025, 4, 30)
    stock = _load_stock(start_date)

    for i in range(1, 4):
        trans_date = add_months(start_date, i)
        stock = _month_process(trans_date, stock)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Oops... Something wrong!")
