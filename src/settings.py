import csv
from pathlib import Path
from typing import Final

PATH_SOURCE = Path(__file__).parent.parent
PATH_TRANS = PATH_SOURCE / "invent_trans"
PATH_STOCK = PATH_SOURCE / "stock"

DELIMITER: Final = ";"
ENCODING: Final = "utf-8"
QUOTING: Final = csv.QUOTE_NONNUMERIC
