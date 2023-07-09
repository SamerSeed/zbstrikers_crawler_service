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
from . import utils
from tasks import tasks
from parsers import WORDS


class ParserBase:
    kword_checker = utils.WordSearchWrapper(WORDS)
    reject_not_current = True
    FILTER_BY_KEYWORDS = True
    now = datetime.datetime.now()
    def parse(self):
        raise RuntimeError("Method must be redefined")
    def update_now(self):
        self.now = datetime.datetime.now()


class ParserInit(ParserBase):
    def __init__(self, *args, **kwargs):
        super(ParserInit, self).__init__(*args, **kwargs)

    def standart_text_routine(self, element:html.HtmlElement, config: tasks.UrlTask, text_part:str):
        text__ = ''
        if text_part:
            text_elem = element.xpath(text_part)
            if len(text_elem):
                text__ = text_elem[0].text
                if text__:
                    if config.encoding:
                        try:
                            text__ = unicodedata.normalize(u'NFC', text__).encode(
                                config.encoding).decode('utf-8', 'ignore')
                        except UnicodeDecodeError as e:
                            logger.error(e)
                            text__ = ''
                    text__ = text__.strip()
        return text__

    def title_routine(self, element:html.HtmlElement, config: tasks.UrlTask):
        return self.standart_text_routine(element, config, config.title_xpath)
    def text_routine(self, element:html.HtmlElement, config: tasks.UrlTask):
        return self.standart_text_routine(element, config, config.text_xpath)
    def city_routine(self, element:html.HtmlElement, config: tasks.UrlTask):
        return self.standart_text_routine(element, config, config.city_xpath)
    
    def href_routine(self, element:html.HtmlElement, config:tasks.UrlTask):
        href = ''
        href2 = ''
        if config.href_xpath:
            href_elem = element.xpath(config.href_xpath)
            if len(href_elem):
                href = href_elem[0].get('href')
                if not href:
                    href = ''
                    href2 = href_elem[0].tail.strip()
        return href, href2
    def date_parse_routine(self, element:html.HtmlElement, config:tasks.UrlTask):
        date = ''
        if config.date_xpath:
            date_elem = element.xpath(config.date_xpath)
            if len(date_elem):
                date = date_elem[0].text
                if date:
                    date = date.strip()

        return utils.parse_date(date, self.now)
        
    def parse(self, context, config: tasks.UrlTask):
        items = defaultdict(list)
        for element in html.fromstring(context).xpath(config.main_xpath):
            date = self.date_parse_routine(element, config)
            if self.reject_not_current:
                if (date.year, date.month, date.day) != (self.now.year, self.now.month, self.now.day):
                    continue
            title = self.title_routine(element, config)            
            text = self.text_routine(element, config)
            city = self.city_routine(element, config)
            href, href2 = self.href_routine(element, config)
            found_keywords = self.kword_checker.check_text(title) or self.kword_checker.check_text(text)
            if not self.FILTER_BY_KEYWORDS or found_keywords:
                items[config.site_name].append({
                    'href': href,
                    'href2': href2,
                    'title': title,
                    'date': str(date),
                    'text': text,
                    'city': city,
                    'base_url': config.base_url,
                })
        return items



class ParserRss(ParserBase):
    def __init__(self, *args, **kwargs):
        super(ParserRss, self).__init__(*args, **kwargs)
    def check_format(self, thefeed:feedparser.FeedParserDict):
        return 'links' in thefeed.channel and thefeed.channel['links'] and \
                'href' in thefeed.channel['links'][0] and \
                'bezformata' in thefeed.channel['links'][0]['href']
    def parse(self, context, config: tasks.UrlTask):
        items = defaultdict(list)
        site_name = config.site_name
        thefeed = feedparser.parse(context, sanitize_html=False)
        is_bezformata = self.check_format(thefeed)
        for thefeedentry in thefeed.entries:
            date = thefeedentry.get('published', '')
            date = utils.parse_date(date, self.now)
            if self.reject_not_current:
                if (date.year, date.month, date.day) != (self.now.year, self.now.month, self.now.day):
                    continue
            
            title = thefeedentry.get("title", "")
            href2 = thefeedentry.get("link", "")
            text = thefeedentry.get("summary", "").strip()
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
            found_keywords = self.kword_checker.check_text(title) or self.kword_checker.check_text(text)
            if not self.FILTER_BY_KEYWORDS or found_keywords:
                items[site_name].append({
                    'href2': href2,
                    'title': title,
                    'date': str(date),
                    'text': text,
                    'base_url': config.base_url,
                })
        return items

class UniParser:
    def __init__(self):
        self.base_parser = ParserInit()
        self.rss_parser = ParserRss()
    