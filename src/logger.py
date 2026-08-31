import logging

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
