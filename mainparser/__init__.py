#  -*- coding: utf-8 -*-
from logger import logger

WORDS = []
try:
    words = open('wordlist.txt', 'r', encoding='utf-8')
except FileNotFoundError as e:
    logger.warning(e)
except Exception as e:
    logger.error(e)
else:
    for word in words:
        word = word.strip()
        if word:
            WORDS.append(word)
    words.close()

PROXIES = []
try:
    proxies = open('proxies.txt', 'r', encoding='utf-8')
except FileNotFoundError as e:
    logger.warning(e)
except Exception as e:
    logger.error(e)
else:
    for proxy in proxies:
        proxy = proxy.strip()
        if proxy:
            PROXIES.append(proxy)
    proxies.close()

if not WORDS:
    raise Exception("Не заполнен файл с стоп словами")
if not PROXIES:
    logger.warning("Не заполнен файл с прокси")
