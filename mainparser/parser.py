#  -*- coding: utf-8 -*-
import datetime
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse
import re

import feedparser
import requests
import validators
import yaml
from logger import logger
from lxml import html
import telebot
import numpy as np
from bs4 import BeautifulSoup

from mainparser import WORDS, PROXIES

from .classifier import load_checkpoint, search_news, parse_date
from .classifier import TLSAdapter
from .classifier_v2 import ZabastcomClassificator, search_news_v2


RESULT_FILE_PATH = '/var/www/html/parse/sniff2/{}_result.html'.format(datetime.datetime.now().strftime("%Y%m%d"))
TIMEOUT = 20
FILTER_BY_KEYWORDS = True
BATCH_SIZE = 50
TG_TOKEN = ''


def load_parser_res(path: Path):
    data = ''
    res = defaultdict(dict)
    try:
        with open(path, 'rt', encoding='UTF-8') as in_f:
            data = in_f.read()
    except:
        return res

    soup = BeautifulSoup(data, 'html.parser')
    headers = soup.find_all('h2')[1:]
    tables = soup.find_all('table')

    for header, table in zip(headers, tables):
        site_name = str(header.string)
        ths = table.find_all('th')[3:]
        for date, title, href2 in zip(ths[::3], ths[1::3], ths[2::3]):
            href2 = str(href2.find('a')['href'])
            res[site_name][href2] = {
                'date': str(date.string),
                'title': str(title.string),
                'href2': href2,
            }
    return res


class Parser:

    def __init__(self, config:str):
        self.items_accum = defaultdict(dict)
        self.items = defaultdict(list)
        self.new_items = defaultdict(list)
        self.configs = []
        self.now = datetime.datetime.now()
        self.loadConfig(config)
        self.load_accumulated()
        self._parse()
        self.build_report()

    @staticmethod
    def find_words(text):
        if not text:
            return False
        text = text.lower()
        for word in WORDS:
            text_pos = text.find(word)
            if text_pos >= 0:
                return True
        return False

    def load_accumulated(self):
        self.items_accum = load_parser_res(
            RESULT_FILE_PATH
        )

    def loadConfig(self, config):
        try:
            f = open(config, encoding='utf-8')
        except FileNotFoundError as e:
            logger.warning(e)
            return
        except Exception as e:
            logger.error(e)
            return
        self.configs = yaml.load(f, Loader=yaml.FullLoader)

    def parse_rss(self, context, site_config):
        thefeed = feedparser.parse(context, sanitize_html=False)
        site_name = site_config.get('site_name', '')

        is_bezformata = False
        if 'links' in thefeed.channel and thefeed.channel['links'] and \
                'href' in thefeed.channel['links'][0] and \
                'bezformata' in thefeed.channel['links'][0]['href']:
            is_bezformata = True

        for thefeedentry in thefeed.entries:
            title = thefeedentry.get("title", "")
            href2 = thefeedentry.get("link", "")
            text = thefeedentry.get("summary", "").strip()
            date = thefeedentry.get('published', '')

            if is_bezformata:
                desc = thefeedentry.get('description', '')
                pos = desc.find('href')
                if -1 != pos:
                    desc = desc[pos:]
                    split = desc.split('"')
                    if len(split) >= 2:
                        link = split[1]
                        if link:
                            href2 = link

            date = parse_date(date, self.now)
            if (date.year, date.month, date.day) != (self.now.year, self.now.month, self.now.day):
                continue

            found_keywords = False
            if title or text:
                if self.find_words(title) or self.find_words(text):
                    found_keywords = True

            if not FILTER_BY_KEYWORDS or found_keywords:
                self.items[site_name].append({
                    'href2': href2,
                    'title': title,
                    'date': str(date),
                    'text': text,
                    'base_url': site_config.get('base_url', ''),
                })

    def parse(self, context, site_config):
        site_name = site_config.get('site_name', '')
        main_xpath = site_config.get('main_xpath', '')
        title_xpath = site_config.get('title_xpath', '')
        text_xpath = site_config.get('text_xpath', '')
        href_xpath = site_config.get('href_xpath', '')
        city_xpath = site_config.get('city_xpath', '')
        date_xpath = site_config.get('date_xpath', '')
        base_url = site_config.get('base_url', '')
        encoding = site_config.get('encoding', '')
        for element in html.fromstring(context).xpath(main_xpath):
            title = ''
            date = ''
            text = ''
            city = ''
            href = ''
            href2 = ''
            if title_xpath:
                title_elem = element.xpath(title_xpath)
                if len(title_elem):
                    title = title_elem[0].text
                    if title:
                        if encoding:
                            try:
                                title = unicodedata.normalize(u'NFC', title).encode(encoding).decode('utf-8', 'ignore')
                            except UnicodeDecodeError as e:
                                logger.error(e)
                                title = ''
                        title = title.strip()
            if text_xpath:
                text_elem = element.xpath(text_xpath)
                if len(text_elem):
                    text = text_elem[0].text
                    if text:
                        if encoding:
                            try:
                                text = unicodedata.normalize(u'NFC', text).encode(encoding).decode('utf-8', 'ignore')
                            except UnicodeDecodeError as e:
                                logger.error(e)
                                text = ''
                        text = text.strip()
            if city_xpath:
                city_elem = element.xpath(city_xpath)
                if len(city_elem):
                    city = city_elem[0].text
                    if city:
                        if encoding:
                            try:
                                city = unicodedata.normalize(u'NFC', city).encode(encoding).decode('utf-8', 'ignore')
                            except UnicodeDecodeError as e:
                                logger.error(e)
                                city = ''
                        city = city.strip()
            if href_xpath:
                href_elem = element.xpath(href_xpath)
                link_elem = element.xpath(href_xpath)
                if len(href_elem):
                    href = href_elem[0].get('href')
                    if not href:
                        href = ''
                if not href and len(link_elem):
                    href2 = link_elem[0].tail.strip()
            if date_xpath:
                date_elem = element.xpath(date_xpath)
                if len(date_elem):
                    date = date_elem[0].text
                    if date:
                        date = date.strip()

            date = parse_date(date, self.now)
            if (date.year, date.month, date.day) != (self.now.year, self.now.month, self.now.day):
                continue

            found_keywords = False
            if title or text:
                if self.find_words(title) or self.find_words(text):
                    found_keywords = True

            if not FILTER_BY_KEYWORDS or found_keywords:
                self.items[site_name].append({
                    'href': href,
                    'href2': href2,
                    'title': title,
                    'date': str(date),
                    'text': text,
                    'city': city,
                    'base_url': base_url,
                })

    def _parse(self):
        for site_config in self.configs:
            session = requests.Session()

            if site_config.get('lower_ssl_security', False):
                session.mount('https://', TLSAdapter())

            urls_path = site_config.get('url_path', '')
            is_rss = site_config.get('rss', False)
            try:
                urls = open(urls_path, 'r', encoding='utf-8')
            except FileNotFoundError as e:
                logger.warning(e)
                return
            except Exception as e:
                logger.error(e)
                return
            for url_line in urls:
                url = url_line.strip()
                logger.debug("Work on: {}".format(url))
                if not url:
                    logger.warning("Empty url line in file {}".format(urls_path))
                    continue
                if not validators.url(url):
                    logger.warning("{url} is not correct in file {urls_path}".format(url=url, urls_path=urls_path))
                    continue
                try:
                    url_parsed = urlparse(url)
                except Exception as e:
                    logger.warning(e)
                    continue
                site_config['base_url'] = "{scheme}://{netloc}".format(scheme=url_parsed.scheme, netloc=url_parsed.netloc)

                def do_request(session, url, timeout, proxies=None):
                    has_failed = False
                    request = None
                    exp = None
                    try:
                        request = session.get(
                            url,
                            timeout=timeout,
                            proxies=proxies,
                        )
                    except Exception as e:
                        has_failed = True
                        exp = e
                    return request, has_failed, exp

                request, has_failed, exp = do_request(
                    session,
                    url,
                    TIMEOUT,
                )
                for proxy in PROXIES:
                    if not has_failed and request.status_code == 200:
                        break
                    proxies = {
                        'http': f'http://{proxy}',
                        'https': f'https://{proxy}',
                    }
                    request, has_failed, exp = do_request(
                        session,
                        url,
                        TIMEOUT,
                        proxies=proxies,
                    )
                if has_failed:
                    logger.error(exp)
                    continue
                if request.status_code != 200:
                    logger.warning("Status code is {status_code}".format(status_code=request.status_code))

                try:
                    if is_rss:
                        self.parse_rss(request.content, site_config)
                    else:
                        self.parse(request.content, site_config)
                except Exception as e:
                    logger.error(e)
                    logger.error("Ошибка обработки парсинга")
                session.close()
            urls.close()
        self.postprocess()

    def parse_url(self, url):
        pass

    def postprocess(self):
        for site_name, value in self.items.items():
            for item in value:
                href = item.get('href', '')
                href2 = item.get('href2', '')
                if not href2:
                    if 'http' in href or 'https' in href:
                        #TODO: добавить регулярку
                        href2 = href
                    else:
                        href2 = item.get('base_url', '') + href
                item['href2'] = href2
                if href2 in self.items_accum[site_name]:
                    continue
                self.new_items[site_name].append(item)
        for site_name, value in self.new_items.items():
            for item in value:
                self.items_accum[site_name][item.get('href2', '')] = item

    def build_report(self):
        if not self.items_accum:
            logger.warning("Парсер {name} не нашел данных, либо не отработал поиск xpath".format(name=self.__class__.__name__))
            return
        try:
            find_urls = open(RESULT_FILE_PATH, "w", encoding='UTF-8')
        except FileNotFoundError as e:
            logger.warning(e)
            return
        except Exception as e:
            logger.error(e)
            return
        find_urls.write('<head><link rel="stylesheet" href="page.css" type="text/css">'
                        '<meta http-equiv="Content-Type" content="text/html;charset=utf-8">'
                        '</head>')
        find_urls.write('<h2>{}</h2>'.format(datetime.datetime.now().strftime("%d-%m-%Y %H:%M")))
        for site_config in self.configs:
            site_name = site_config.get('site_name', '')
            value = self.items_accum[site_name]
            find_urls.write('<h2>{}</h2>'.format(site_name))
            find_urls.write('<table class="table">'
                            '<tr>'
                            '<th>Дата</th>'
                            '<th>Текстовка</th>'
                            '<th>Ссылка</th>'
                            '</tr>')
            keys = sorted(value.keys())
            for key in keys:
                item = value[key]
                href2 = item.get('href2', '')
                title = item.get('title', '')
                date = item.get('date', '')
                find_urls.write(
                    '<th>{date}</th><th>{title}</th><th><a href="{base_url}">{base_url}</a></th></tr>'.format(date=date, title=title, base_url=href2))
            if not value:
                find_urls.write('<th>Ничего не найдено</th><th></th></tr>')
            find_urls.write('</table>')
        find_urls.close()

    def rearrange_links(
            self,
            items):
        '''
        Rearrange links so different sources will alternate like vk.com, t.me, vk.com, ... 
        '''
        items_map = defaultdict(list)
        for item in items:
            url_parsed = urlparse(item.get('url', ''))
            items_map[url_parsed.netloc].append(item)
        items_map = sorted(
            list(items_map.items()),
            key=lambda x: len(x[1]),
            reverse=True,
        )
        res = []
        for i in range(len(items_map[0][1])):
            for _, value in items_map:
                if i >= len(value):
                    break
                res.append(value[i])
        return res

    def remove_reposts(self, items, history):
        '''
        Remove vk.com reposts (if reposted record is also in parser output)
        '''
        prog = re.compile('.*Reposted \(.*data-post-id=\"(.*?)\".*')

        for idx, item in enumerate(items):
            url = item.get('url', '')
            url_parsed = urlparse(url)
            item['is_vk'] = url_parsed.netloc == 'vk.com'
            item['repost'] = False

        for idx, item in enumerate(items):
            if not item['is_vk']:
                continue
            text = item.get('text', '')
            match = prog.match(text.replace('\n', ' '))
            if not match:
                continue
            urls = {v['url'] for j, v in enumerate(items) if j != idx and v['is_vk']}
            urls = urls.union(set(history.url_map.keys()))
            for i in range(len(match.groups())):
                post_url = 'https://vk.com/wall' + match[i + 1]
                if post_url in urls:
                    item['repost'] = True                   
        items = [item for item in items if not item['repost']]
        return items

    def filter_urls(self):
        checkpoint = {}
        try:
            checkpoint = load_checkpoint(Path('models/tfidf_logreg'))
        except Exception as e:
            logger.error(f'Error loading checkpoint: {e}')
            return

        path_stops = 'resources/stopwords_ru.txt'
        path_navec_weights = 'resources/navec_news_v1_1B_250K_300d_100q.tar'
        path_ner_weights = 'resources/slovnet_ner_news_v1.tar'
        path_pkl_vectorizer = 'weights/zbs_tfidf_vectorizer.pkl'
        path_pkl_model = 'weights/zbs_logreg.pkl'
        base = Path('models/weighs_resources/')
        classifier_v2 = ZabastcomClassificator(
            str(base / path_stops),
            str(base / path_navec_weights),
            str(base / path_ner_weights),
            str(base / path_pkl_vectorizer),
            str(base / path_pkl_model),
        )

        items = []
        for _, value in self.new_items.items():
            for item in value:
                title = item.get('title', '')
                text = item.get('text', '')
                text = '\n'.join([title, text])
                items.append({
                    'url': item.get('href2', ''),
                    'date': item.get('date', ''),
                    'text': text,
                })

        if len(items) == 0:
            return

        items = self.remove_reposts(items, checkpoint['history'])

        items = self.rearrange_links(items)

        # split texts into batches
        n_batches = (len(items) - 1) // BATCH_SIZE + 1
        items = np.asarray(items, dtype=object)
        batches_idx = np.array_split(range(len(items)), n_batches)

        # predict
        found_urls = []
        for i, batch_idx in enumerate(batches_idx):
            try:
                batch = items[batch_idx]
                found_urls += search_news_v2(
                    [item['text'] for item in batch],
                    [item['url'] for item in batch],
                    [item['date'] for item in batch],
                    checkpoint,
                    classifier=classifier_v2,
                )
            except Exception as e:
                logger.error(f'Error searching news at batch {i}: {e}')
                continue

        # dump result to a file with today's history
        try:
            checkpoint['history_v2'].to_file()
        except Exception as e:
            logger.error(f'Error writing today history: {e}')

        # find duplicates
        idx_texts = []
        if found_urls:
            idx_texts = classifier_v2.find_duplicates(
                [item[-1] for item in found_urls],
                ksim=0.8,
                verbose=False
            )

        # sort by probability
        groups = []
        for group_idxs in idx_texts:
            max_proba = max([found_urls[idx][0] for idx in group_idxs])
            groups.append([max_proba, group_idxs])
        groups = sorted(groups, key=lambda x: x[0], reverse=True)

        wo_dub = []
        w_dub = []
        for i, item in enumerate(groups):
            if len(item[1]) == 1:
                wo_dub.append(item)
            else:
                w_dub.append(item)

        # form a message and send to tg channel
        res = ['News without duplicates:']
        for _, group_idxs in wo_dub:
            for idx in group_idxs:
                prob, url, _ = found_urls[idx]
                res.append(' '.join([
                    f'{prob:0.3f}',
                    url
                ]))

        res.append('News with duplicates:')
        for _, group_idxs in w_dub:
            res.append('-' * 30)
            for idx in group_idxs:
                prob, url, _ = found_urls[idx]
                res.append(' '.join([
                    f'{prob:0.3f}',
                    url
                ]))
        res.append('-' * 30)

        self.send_urls_to_channel(
            res,
            channel_name='@zabastcom_news_v2',
        )

    def send_urls_to_channel(self, urls, channel_name):
        msg_text = ''
        try:
            msg_text = '\n'.join(
                urls
            )
            logger.info(f'Sending message {msg_text}')
            bot = telebot.TeleBot(TG_TOKEN)
            bot.send_message(
                channel_name,
                msg_text
            )
        except Exception as e:
            logger.error(f'Error sending message {msg_text} to telegram channel: {e}')
