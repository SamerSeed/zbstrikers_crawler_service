import json
import re
import zlib
from datetime import datetime
from time import sleep
from urllib.parse import urlparse
from logger import logger
from typing import Dict
from pathlib import Path
import ssl

from dateutil import parser
import numpy as np
from bs4 import BeautifulSoup
from tqdm import tqdm
from newspaper import Article
from newspaper.configuration import Configuration
import requests
import joblib

from mainparser import PROXIES


TIMEOUT = 7
TIME_SLEEP = 0.5
TO_SLEEP = (
    'vk.com',
)
THRESHOLD = 0.126590649344836


class TLSAdapter(requests.adapters.HTTPAdapter):

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = ctx
        return super(TLSAdapter, self).init_poolmanager(*args, **kwargs)


class History:

    def __init__(self, items: Dict[float, str], date: datetime, path: Path):
        self.url_map = items  # map from url to probability
        self.date = date
        self.path = path

    @classmethod
    def from_file(cls, path: Path):
        items = []
        url_map = {}
        now = datetime.now()
        if path.exists():
            with open(path, 'rt', encoding='UTF-8') as in_f:
                items = in_f.readlines()
        # if no file/file is empty
        if not items:
            return cls(url_map, now, path)
        date = items[0].strip()
        date = datetime.strptime(date, '%d/%m/%Y')
        # if history in file is old, flush it
        if (date.year, date.month, date.day) != (now.year, now.month, now.day):
            return cls(url_map, now, path)
        # remove date from items
        if len(items) > 1:
            items = items[1:]
        else:
            items = []
        # create map from url to probability
        for item in items:
            split = item.strip().split()
            url_map[split[1]] = float(split[0])
        return cls(url_map, now, path)

    def to_file(self):
        items = self.url_map.items()
        items = sorted(items, key=lambda x: x[1], reverse=True)
        with open(self.path, 'wt', encoding='UTF-8') as out_f:
            out_f.write(self.date.strftime('%d/%m/%Y') + '\n')
            for item in items:
                url, prob = item
                out_f.write(f'{prob} {url}\n')


def parse_date(date_s, now):
    months_table = {
        'январ': 'january',
        'феврал': 'february',
        'март': 'march',
        'апрел': 'april',
        'маЙ': 'may',
        'мая': 'may',
        'июн': 'june',
        'июл': 'july',
        'август': 'august',
        'сентябр': 'september',
        'октябр': 'october',
        'ноябр': 'november',
        'декабр': 'december',
    }
    date_s = date_s.lower()
    for key, val in months_table.items():
        date_s = date_s.replace(key, val)
    date_s = re.sub(
        r'[^\x00-\x7F\x80-\xFF\u0100-\u017F\u0180-\u024F\u1E00-\u1EFF]',
        u'',
        date_s
    )
    date = now
    try:
        date = parser.parse(date_s)
    except:
        pass
    return date


def parse_dates(dates_s, now):
    dates = []
    for date_s in dates_s:
        dates.append(parse_date(date_s, now))
    return dates


def parse_tg(data: str, url: str):
    soup = BeautifulSoup(data, features='lxml')
    div = soup.find(
        'div',
        {
            'class': 'tgme_widget_message js-widget_message',
            'data-post': '/'.join(url.split('/')[-2:]),
        }
    )
    if not div:
        div = soup.find(
            'div',
            {
                'class': 'tgme_widget_message text_not_supported_wrap js-widget_message',
                'data-post': '/'.join(url.split('/')[-2:]),
            },
        )
    if not div:
        return None
    div = div.find(
        'div', {'class': 'tgme_widget_message_text js-message_text'})
    if not div:
        div = div.find(
            'div', {'class': 'tgme_widget_message_text js-message_text before_footer'})
    if not div:
        return None
    return div.getText()


def get_text(
        url,
        div_map,
        endswith,
        lower_ssl_security,
        timeout):
    if not url:
        return None, ''
    url = url.replace('Источник:', '').strip()

    url_to_parse = url
    if url.startswith('https://web.archive.org/web/'):
        url_to_parse = url.replace('https://web.archive.org/web/', '')
    url_parsed = urlparse(url_to_parse)
    netloc = url_parsed.netloc

    for template in endswith:
        if netloc.endswith(template):
            netloc = template
            break

    if netloc not in div_map:
        return None, netloc

    def do_request(url, netloc, lower_ssl_security, timeout, proxies=None):
        has_failed = False
        data = None
        error = ''
        headers = {'User-Agent': 'Mozilla/5.0'}
        session = requests
        if netloc in lower_ssl_security:
            session = requests.Session()
            session.mount('https://', TLSAdapter())
        try:
            response = session.get(
                url,
                timeout=timeout,
                headers=headers,
                proxies=proxies,
            )
            response.raise_for_status()
            data = response.content
        except Exception as e:
            error = f'{e}'
            has_failed = True
        return data, has_failed, error

    data, has_failed, error = do_request(
        url,
        netloc,
        lower_ssl_security,
        timeout,
    )

    for proxy in PROXIES:
        if not has_failed:
            break
        proxies = {
            'http': f'http://{proxy}',
            'https': f'https://{proxy}',
        }
        data, has_failed, error = do_request(
            url,
            netloc,
            lower_ssl_security,
            timeout,
            proxies=proxies,
        )

    if error:
        logger.warning(error)
    if has_failed or data is None:
        return None, netloc

    try:
        try:
            data = data.decode('utf-8')
        except UnicodeDecodeError:
            data = zlib.decompress(data, 16 + zlib.MAX_WBITS)
    except:
        pass
    return data, netloc


def parse_text(
        data,
        url,
        div_map,
        netloc,
        collect_all,
        sub_p,
        ignore_header,
        extract_map):
    if netloc == 't.me':
        text = parse_tg(
            data,
            url,
        )
        return text, False

    # parse
    try:
        soup = BeautifulSoup(data, features='lxml')
    except:
        return None, False

    # remove divs from extract_map
    if netloc in extract_map:
        for div in extract_map[netloc]:
            for s in soup.find_all(*div):
                s.extract()

    # remove vk reposts
    if netloc == 'vk.com':
        refs = soup.find_all('a', {'class': 'pi_author'})
        for ref in refs:
            if ref.getText() == 'ЗабастКом':
                return None, True

    divs = div_map[netloc]
    to_collect_all = netloc in collect_all

    # fix for vz.ru
    if netloc == 'vz.ru':
        url_parsed = urlparse(url)
        divs[0][1]['data-url'] = url_parsed.path

    # collect article text
    keys = [f'h{i}' for i in range(1, 6)] + ['p', 'li']
    text = ''
    if netloc not in ignore_header:
        divs = [('h1',)] + divs
    for div in divs:
        text_wraps = []
        if to_collect_all:
            text_wraps = soup.find_all(*div)
        else:
            text_wraps = [soup.find(*div)]
        for text_wrap in text_wraps:
            if text_wrap is None:
                continue
            if netloc in sub_p and div[0] not in keys:
                for key in keys:
                    for p in text_wrap.find_all(key, recursive=True):
                        text += p.getText() + '\n'
            else:
                text += text_wrap.getText() + '\n'

    return text, False


def get_texts(
        texts,
        links,
        div_map,
        collect_all,
        sub_p,
        ignore_header,
        extract_map,
        endswith,
        lower_ssl_security,
        timeout,
        time_sleep,
        to_sleep):
    res = []
    for text_from_feed, url in tqdm(list(zip(texts, links))):
        download_failed = False
        data, netloc = None, ''
        try:
            data, netloc = get_text(
                url,
                div_map,
                endswith,
                lower_ssl_security,
                timeout,
            )
        except Exception as e:
            logger.error(f'Error downloading {url}: {e}')
            download_failed = True
        if netloc in to_sleep:
            sleep(time_sleep)

        def download_with_newspaper(url, netloc, to_sleep, time_sleep, proxies=None):
            has_failed = False
            text = None

            config = Configuration()
            config.language = 'ru'
            config.proxies = proxies
            config.request_timeout = TIMEOUT
            config.browser_user_agent = 'Mozilla/5.0'

            warning = ''
            error = ''
            try:
                article = Article(url, config=config)
                article.download()
                if netloc in to_sleep:
                    sleep(time_sleep)
                article.parse()
                if not article.text:
                    warning = 'newspaper3k failed to get text for ' + url
                text = article.title + '\n' + article.text
            except Exception as e:
                error = f'Error downloading {url} with newspaper3k: {e}'
                has_failed = True
            return text, has_failed, warning, error

        text = ''
        has_failed = False
        to_skip = False
        if download_failed or data is None:
            text, has_failed, warning, error = download_with_newspaper(
                url,
                netloc,
                to_sleep,
                time_sleep,
            )
            for proxy in PROXIES:
                if not has_failed:
                    break
                proxies = {
                    'http': f'http://{proxy}',
                    'https': f'https://{proxy}',
                }
                text, has_failed, warning, error = download_with_newspaper(
                    url,
                    netloc,
                    to_sleep,
                    time_sleep,
                    proxies=proxies,
                )
            if warning:
                logger.warning(warning)
            if error:
                logger.warning(error)
        else:
            try:
                text, to_skip = parse_text(
                    data,
                    url,
                    div_map,
                    netloc,
                    collect_all,
                    sub_p,
                    ignore_header,
                    extract_map,
                )
            except Exception as e:
                logger.warning(f'Error parsing text from {url}: {e}')
                has_failed = True

        if to_skip:
            continue

        if has_failed or not text:
            text = text_from_feed

        if text:
            # костыль для РосТруда
            text = text.replace(
                'Если ваши трудовые права нарушены, вы можете обратиться в государственную инспекцию труда, ' +
                'в том числе дистанционно через сервис "Сообщить о проблеме" на портале "Онлайнинспекция.рф"',
                '',
            )
            text = text.replace(
                'Подписывайтесь на нас в',
                '',
            )
        else:
            logger.error(f'Failed to get text for {url}')
            continue

        res.append((url, text))
    return res


def fix_tg_links(links):
    for i, url in enumerate(links):
        url_parsed = urlparse(url)
        if 't.me' == url_parsed.netloc:
            url = url.replace('://t.me/', '://t.me/s/')
            links[i] = url
    return links


def undo_fix_tg_link(url):
    url_parsed = urlparse(url)
    if 't.me' == url_parsed.netloc:
        url = url.replace('://t.me/s/', '://t.me/')
    return url


def load_checkpoint(checkpoint_dir):
    keys = (
        'collect_all',
        'div_map',
        'endswith',
        'extract_map',
        'ignore_header',
        'lower_ssl_security',
        'sub_p',
    )
    checkpoint = {}
    for key in keys:
        with open(checkpoint_dir / f'{key}.json', 'rt', encoding='UTF-8') as in_f:
            checkpoint[key] = json.load(in_f)
    checkpoint['clf'] = joblib.load(checkpoint_dir / 'log_reg.pkl')
    checkpoint['tfidf_vect'] = joblib.load(checkpoint_dir / 'vectorizer.pkl')
    checkpoint['history'] = History.from_file(Path('today_history.txt'))
    checkpoint['history_v2'] = History.from_file(Path('today_history_v2.txt'))
    return checkpoint


def search_news(
        texts,
        links,
        dates_s,
        checkpoint):
    if len(links) == 0:
        return []

    # parse dates
    now = datetime.now()
    dates = parse_dates(
        dates_s,
        now,
    )

    links = fix_tg_links(links)

    texts = np.asarray(texts, dtype=object)
    links = np.asarray(links)
    dates = np.asarray(dates)

    # filter by date
    mask = []
    for date in dates:
        mask.append((date.year, date.month, date.day)
                    == (now.year, now.month, now.day))
    mask = np.asarray(mask)
    if mask.sum() == 0:
        return []
    texts = texts[mask]
    links = links[mask]

    # get texts
    res = get_texts(
        texts,
        links,
        checkpoint['div_map'],
        checkpoint['collect_all'],
        checkpoint['sub_p'],
        checkpoint['ignore_header'],
        checkpoint['extract_map'],
        checkpoint['endswith'],
        checkpoint['lower_ssl_security'],
        timeout=TIMEOUT,
        time_sleep=TIME_SLEEP,
        to_sleep=TO_SLEEP,
    )

    # remove empty texts
    w_text = [(url, text)
              for url, text in res if text is not None and text.strip()]
    texts = np.asarray([text for _, text in w_text])
    links = np.asarray([url for url, _ in w_text])

    # get unique texts
    texts, idx = np.unique(texts, return_index=True)
    if len(idx) == 0:
        return []
    links = links[idx]

    X_today = checkpoint['tfidf_vect'].transform(texts)

    # remove empty vectors
    X_sum = X_today.sum(axis=1)
    mask = X_sum > 0.0
    if mask.sum() == 0:
        return []
    mask = np.asarray(mask)[:, 0]
    X_today = X_today[mask]
    links = links[mask]

    # predict
    pred_prob = checkpoint['clf'].predict_proba(X_today)[:, 1]
    pred = (pred_prob >= THRESHOLD).astype(np.bool8)
    if 0 == np.count_nonzero(pred):
        return []

    pred_prob = pred_prob[pred]
    links = links[pred]
    res = []
    for prob, url in zip(pred_prob, links):
        if url in checkpoint['history'].url_map:
            continue
        checkpoint['history'].url_map[url] = prob
        url_to_show = undo_fix_tg_link(url)
        res.append((prob, url_to_show))
    return res
