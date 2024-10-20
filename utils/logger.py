import logging
import os.path

from utils.environment import Environment

LOG_FILE = os.path.join(Environment().log_directory(), Environment().log_file())

logger = logging.getLogger('mythic_tui')
logger.setLevel(Environment().log_level())
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(Environment().log_level())
formatter = logging.Formatter('%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
