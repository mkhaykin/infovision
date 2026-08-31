import csv
import heapq
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Generator, Optional

from logger import logger
from models import SkuLocation, Value
from settings import DELIMITER, ENCODING, PATH_STOCK, QUOTING
from utils import load_stock


@dataclass(slots=True)
class TrackValue:
    # на самом деле не используется, но удобно для отладки, поэтому оставил
    days_in: int = 0
    # когда появился
    last_date_in: Optional[date] = None
    # дата, когда уже не было. Важно, last_date_out может быть < last_date_in,
    # если периодов появления было несколько
    last_date_out: Optional[date] = None

    def inc(self) -> None:
        self.days_in = self.days_in + 1


def _stock_loader_wrapper(
    stock_date: date,
) -> dict[SkuLocation, Value]:
    # выглядит как костыль (так и есть),
    # но нельзя менять контракт из первого задания
    return load_stock(stock_date, skip_zero=True)


def track_sku_presence(
    start_date: date,
    fin_date: date,
    started: Optional[dict[SkuLocation, TrackValue]] = None,
    stock_loader: Callable[[date], dict[SkuLocation, Value]] = _stock_loader_wrapper,
) -> dict[SkuLocation, TrackValue]:
    """
    Собираем движение позиций.
    По stock данным определяем сколько дней товар был и
    когда последний раз поступил и закончился.

    `stock_loader` инжектируем для удобства тестов.
    """
    dates = (
        (start_date + timedelta(days)) for days in range((fin_date - start_date).days + 1)
    )
    initial_stock = started.copy() if started else {}

    stock: dict[SkuLocation, Value]
    for _date in dates:
        stock = stock_loader(_date)
        for sku in stock:
            if sku not in initial_stock:
                initial_stock[sku] = TrackValue(days_in=1, last_date_in=_date)
            else:
                initial_stock[sku].inc()
                if (initial_stock[sku].last_date_in is None) or (
                    initial_stock[sku].last_date_out is not None
                    and initial_stock[sku].last_date_in < initial_stock[sku].last_date_out  # type: ignore
                ):
                    initial_stock[sku].last_date_in = _date

        for sku in initial_stock:
            if sku not in stock:
                # Если у товара уже стоит аут, и он свежее,
                # чем дата последнего входа (last_date_in),
                # значит, товар пропал еще в предыдущие дни,
                # и мы эту «дыру» уже зафиксировали.
                if (initial_stock[sku].last_date_out is None) or (
                    # last_date_in обязан быть если есть last_date_out
                    initial_stock[sku].last_date_out < initial_stock[sku].last_date_in  # type: ignore
                ):
                    initial_stock[sku].last_date_out = _date

    logger.debug("Номенклатура %d", len(initial_stock))
    return initial_stock


def save_stock(stock_file: Path, stock: dict[SkuLocation, Value], s_date: str) -> None:
    logger.debug("Сохраняем %s", stock_file)
    with open(stock_file, "w", encoding=ENCODING) as fw:
        writer = csv.writer(fw, delimiter=DELIMITER, quoting=QUOTING)
        header = ("item_id", "location_id", "trans_date", "qty", "cost_amount")
        writer.writerow(header)
        for sl, value in stock.items():
            item = [sl.item_id, sl.location_id, s_date, value.qty, value.cost_amount]
            writer.writerow(item)


def filter_always_present_skus(
    history: dict[SkuLocation, TrackValue],
    start_date: date,
    fin_date: date,
    location_id: Optional[str] = None,
) -> Generator[SkuLocation, None, None]:
    """
    Бизнес-логика задачи А.
    Проверяет, что товар встал на остаток не позже start_date
    и ни разу не исчезал до конца периода fin_date.
    ВАЖНО: это может глючить, если даты сформированы мимо дат истории
    """
    for sku_loc, value in history.items():
        if (
            value.last_date_in is not None
            and value.last_date_in <= start_date
            and (
                value.last_date_out is None
                or value.last_date_out > fin_date
                or value.last_date_out < value.last_date_in
            )
        ):
            if location_id is not None and location_id != sku_loc.location_id:
                continue

            yield sku_loc


def filter_novelties_skus(
    history: dict[SkuLocation, TrackValue],
    window_start: date,
    window_end: date,
    fin_date: date,
    location_id: Optional[str] = None,
) -> Generator[SkuLocation, None, None]:
    """
    Бизнес-логика задачи Б.
    Отбирает SKU, у которых текущий непрерывный период начался внутри окна
    window_start..window_end и не прерывался с window_end до fin_date.
    """
    for sku_loc, value in history.items():
        if (
            value.last_date_in is not None
            and window_start <= value.last_date_in <= window_end
            and (
                value.last_date_out is None
                or value.last_date_out > fin_date
                or value.last_date_out < value.last_date_in
            )
        ):
            if location_id is not None and location_id != sku_loc.location_id:
                continue

            yield sku_loc


def task_a(
    start_date: date,
    fin_date: date,
    fin_stock: dict[SkuLocation, Value],
    history: dict[SkuLocation, TrackValue],
) -> dict[SkuLocation, Value]:
    locations = set()
    for sku in history:
        locations.add(sku.location_id)
    skus = {}
    for location in locations:
        filtered_skus = filter_always_present_skus(
            history,
            start_date,
            fin_date,
            location_id=location,
        )
        valid_skus_for_loc = [sku for sku in filtered_skus if sku in fin_stock]

        top_10 = heapq.nlargest(
            10,
            valid_skus_for_loc,
            key=lambda item: fin_stock[item].cost_amount,
        )
        skus.update({sku: fin_stock[sku] for sku in top_10})

    return skus


def task_b(
    l_date: date,
    r_date: date,
    fin_date: date,
    fin_stock: dict[SkuLocation, Value],
    history: dict[SkuLocation, TrackValue],
) -> dict[SkuLocation, Value]:
    # TODO @<kmi>: логика почти идентичная task_a, надо избавиться от копипасты
    locations = set()
    for sku in history:
        locations.add(sku.location_id)
    skus = {}
    for location in locations:
        filtered_skus = filter_novelties_skus(
            history,
            l_date,
            r_date,
            fin_date,
            location_id=location,
        )
        valid_skus_for_loc = [sku for sku in filtered_skus if sku in fin_stock]
        top_10 = heapq.nlargest(
            10,
            valid_skus_for_loc,
            key=lambda item: fin_stock[item].cost_amount,
        )
        skus.update({sku: fin_stock[sku] for sku in top_10})

    return skus


def main() -> None:
    start_date = datetime(2025, 4, 30).date()
    fin_date = datetime(2025, 7, 31).date()

    l_date = datetime(day=1, month=7, year=2025).date()
    r_date = datetime(day=10, month=7, year=2025).date()

    history = track_sku_presence(start_date, fin_date)
    fin_stock = load_stock(fin_date)

    # task A
    task_a_res = task_a(start_date, fin_date, fin_stock, history)
    stock_file_a = PATH_STOCK / f"stock_{fin_date.strftime('%Y_%m_%d')}_top10a.csv"
    save_stock(stock_file_a, task_a_res, fin_date.strftime("%Y-%m-%d"))

    # task B
    stock_file_b = PATH_STOCK / f"stock_{fin_date.strftime('%Y_%m_%d')}_top10b.csv"
    task_b_res = task_b(l_date, r_date, fin_date, fin_stock, history)
    save_stock(stock_file_b, task_b_res, fin_date.strftime("%Y-%m-%d"))


if __name__ == "__main__":
    main()
