from decimal import Decimal
from typing import Any, NamedTuple


class SkuLocation(NamedTuple):
    item_id: str
    location_id: str


class Value(NamedTuple):
    qty: Decimal = Decimal(0)
    cost_amount: Decimal = Decimal(0)

    def __add__(self, other: tuple[Any, ...]) -> Value:
        if not isinstance(other, Value):
            return NotImplemented

        return Value(self.qty + other.qty, self.cost_amount + other.cost_amount)


class Row(NamedTuple):
    item_id: str
    location_id: str
    trans_date: str
    qty: str
    cost_amount: str
