"""
Общее описание решения:
1. считаем средний остаток (игнорируя нулевые остатки), фактически день и сумма.
2. ведем список изменения остатка: (2025-07-02, 15), (2025-07-05, 12) -
означает что с 02 остаток был 15, а с 05 стал 12.
Важно, полностью игнорируем нулевки (так по ТЗ), т.е. вот такого (2025-07-07, 0) не будет

После того как собрали такую структуру, проходим по ней еще раз и выбираем первый
подходящий остаток из п. 2
"""

import csv
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Callable, Final, Generator, NamedTuple

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
        logging.FileHandler("../app.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)

PATH_SOURCE = Path(__file__).parent.parent
PATH_TRANS = PATH_SOURCE / "invent_trans"
PATH_STOCK = PATH_SOURCE / "stock"

DELIMITER: Final = ";"
ENCODING: Final = "utf-8"
QUOTING: Final = csv.QUOTE_NONNUMERIC


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


class StockRowIn(NamedTuple):
    sku_loc: SkuLocation
    trans_date: date
    value: Value

    @classmethod
    def from_raw(cls, line: list[str]) -> StockRowIn:
        if len(line) != 5:
            raise ValueError("Не корректное количество колонок")
        item_id, location_id, trans_date_str, qty_str, cost_str = line
        return cls(
            sku_loc=SkuLocation(item_id, location_id),
            trans_date=datetime.strptime(trans_date_str, "%Y-%m-%d").date(),
            value=Value(
                qty=Decimal(qty_str),
                cost_amount=Decimal(cost_str),
            ),
        )


class IncidentRowOut(NamedTuple):
    sku_loc: SkuLocation
    trans_date: date
    qty: Decimal
    avg_qty: Decimal


@dataclass(slots=True)
class StockHistory:
    sum_qty: Decimal = Decimal("0.0")
    count_days: int = 0
    states: list[tuple[date, Decimal]] = field(default_factory=list)


def read_daily_stock(stock_date: date) -> Generator[StockRowIn, None, None]:
    stock_file = PATH_STOCK / f"stock_{stock_date.strftime('%Y_%m_%d')}.csv"
    logger.debug("Читаем %s", stock_file)
    with open(stock_file, encoding=ENCODING) as fr:
        reader = csv.reader(fr, delimiter=DELIMITER)
        next(reader)  # skip header
        for line in reader:
            if not line:
                continue
            try:
                yield StockRowIn.from_raw(line)
            except (ValueError, TypeError, IndexError) as e:
                logger.error("Ошибка обработки строки `%s`: %s", line, e)
                continue
    logger.debug("Прочитан файл %s", stock_file)


def aggregate_stock_data(
    start_date: date,
    fin_date: date,
    stock_reader: Callable[[date], Generator[StockRowIn, None, None]] = read_daily_stock,
) -> dict[SkuLocation, StockHistory]:
    result: dict[SkuLocation, StockHistory] = defaultdict(StockHistory)
    current_date = start_date
    while current_date <= fin_date:
        for item in stock_reader(current_date):
            if item.value.qty == 0:
                # нулевки вообще не нужны
                continue

            v = result[item.sku_loc]
            v.sum_qty += item.value.qty
            v.count_days += 1
            if not v.states or v.states[-1][1] != item.value.qty:
                v.states.append((item.trans_date, item.value.qty))
            result[item.sku_loc] = v

        current_date += timedelta(days=1)

    return result


def find_stock_incidents(
    data: dict[SkuLocation, StockHistory],
) -> Generator[IncidentRowOut, None, None]:
    for sku_loc, item in data.items():
        avg_qty = round(item.sum_qty / item.count_days, 3)
        for state_date, state_qty in item.states:
            if avg_qty * Decimal("0.25") > state_qty:
                yield IncidentRowOut(
                    sku_loc=sku_loc,
                    trans_date=state_date,
                    qty=state_qty,
                    avg_qty=avg_qty,
                )
                break


def write_incident_report(
    file: Path,
    data: Generator[IncidentRowOut, None, None],
) -> None:
    logger.debug("Пишем %s", file)
    with open(file, "w", encoding=ENCODING) as fw:
        writer = csv.writer(fw, delimiter=DELIMITER, quoting=QUOTING)
        writer.writerow(["item_id", "location_id", "trans_date", "qty", "qty_avg"])
        for item in data:
            writer.writerow(
                [
                    item.sku_loc.item_id,
                    item.sku_loc.location_id,
                    item.trans_date,
                    item.qty,
                    item.avg_qty,
                ],
            )


def main() -> None:
    start_date = datetime(2025, 7, 1).date()
    fin_date = datetime(2025, 7, 31).date()

    prep_data = aggregate_stock_data(start_date, fin_date)
    proc_data = find_stock_incidents(prep_data)

    filename = PATH_STOCK / f"stock_{fin_date.strftime('%Y_%m')}_avg25.csv"
    write_incident_report(filename, proc_data)


if __name__ == "__main__":
    main()
