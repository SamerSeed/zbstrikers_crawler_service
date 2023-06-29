import logging.config

from logger.settings import logger_config

logging.config.dictConfig(logger_config)
logger = logging.getLogger('app_logger')
