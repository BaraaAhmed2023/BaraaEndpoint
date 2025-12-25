from app import app as application
import logging
from logging.handlers import RotatingFileHandler
import os

LOG_FILE = os.path.expanduser('~/logs/flask.log')

handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,
    backupCount=3
)

handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)

application.logger.addHandler(handler)
application.logger.setLevel(logging.INFO)

application.logger.info("Flask logging started")
