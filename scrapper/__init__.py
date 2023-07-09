from logger import logger
import datetime
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

RESULT_FILE_PATH = '/var/www/html/parse/sniff2/{}_result.html'.format(
    datetime.datetime.now().strftime("%Y%m%d"))
TIMEOUT = 20
FILTER_BY_KEYWORDS = True
BATCH_SIZE = 50
TG_TOKEN = ''