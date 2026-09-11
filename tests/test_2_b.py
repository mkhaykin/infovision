from pathlib import Path

import pandas as pd


def get_sum(
    filename: Path,
    sku: str,
) -> tuple[float, float]:
    df = pd.read_csv(
        filename,
        sep=";",
        usecols=("item_id", "location_id", "trans_date", "qty", "cost_amount"),
    )
    qty_sum = df[df["location_id"] == sku]["qty"].sum()
    cost_sum = df[df["location_id"] == sku]["cost_amount"].sum()
    return qty_sum, cost_sum


def test_test_2b() -> None:
    """
    ожидаемый результат:
    44673735EAF46E11B7B78A650500BC08              910.5     373902.99
    B0BDDED34CC83E11052F6792C000B249             913.0     123294.22
    FC081C55582CED11A62CD892C0003F2A              470.0     172414.64
    """
    assert get_sum(
        Path(__file__).parent.parent / "stock/stock_2025_07_31_top10b.csv",
        "44673735EAF46E11B7B78A650500BC08",
    ) == (910.5, 373902.99)
