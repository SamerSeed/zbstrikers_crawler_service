#!/usr/bin/env python
#  -*- coding: utf-8 -*-


from mainparser.parser import Parser
from logger import logger
if __name__ == "__main__":
    logger.info("-------Start parsing-------")
    parser = Parser("config.yaml")
    logger.info("--------End parsing--------")
    print("Done parsing!")
    print('Starting ml stuff...')
    try:
        parser.filter_urls()
    except Exception as e:
        logger.error(f'Error in classifier: {e}')
