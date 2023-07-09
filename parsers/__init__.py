from logger import logger
from typing import List
WORDS:list[str] = []
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
