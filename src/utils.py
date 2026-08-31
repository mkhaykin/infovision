import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Generator, Optional

from logger import logger
from models import Row, SkuLocation, Value
from settings import DELIMITER, ENCODING, PATH_STOCK


def load_stock(stock_date: date, *, skip_zero: bool = False) -> dict[SkuLocation, Value]:
    stock: dict[SkuLocation, Value] = {}
    trans_date_set = set()

    s_date = stock_date.strftime("%Y_%m_%d")
    stock_file = PATH_STOCK / f"stock_{s_date}.csv"

    logger.debug("Читаем %s", stock_file)
    count = 0
    for stock_item in rows(stock_file):
        # считаем, что повторов в остатках быть не должно
        if skip_zero and stock_item.qty == 0 or stock_item.cost_amount == 0:
            continue

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


def rows(
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
