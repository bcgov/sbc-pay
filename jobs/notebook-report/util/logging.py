import logging.config
import sys
from os import path

from config import Config


def setup_logging(conf="logging.conf"):
    log_file_path = path.join(Config.PROJECT_ROOT, conf)

    if path.isfile(log_file_path):
        logging.config.fileConfig(log_file_path)
        print("Configure logging, from conf:{}".format(log_file_path), file=sys.stderr)
    else:
        print("Unable to configure logging, attempted conf:{}".format(log_file_path), file=sys.stderr)
