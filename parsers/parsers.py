import datetime
import unicodedata
from collections import defaultdict
import feedparser
from logger import logger
from lxml import html
from . import utils
from tasks import tasks
from parsers import WORDS
from dataclasses import dataclass,  field
from typing import Dict, List

@dataclass
class SiteItem:
    href:str = ''
    href2:str = ''
    title:str = ''
    date:str = ''
    text:str = ''
    city:str = ''
    base_url:str = ''
                
class ParserBase:
    kword_checker = utils.WordSearchWrapper(WORDS)
    reject_not_current = True
    FILTER_BY_KEYWORDS = True
    now = datetime.datetime.now()
    def parse_(self, context, config: tasks.UrlTask)->Dict[str, List[SiteItem]]:
        raise RuntimeError("Method must be overriden")
    
    def parse(self, context, config: tasks.UrlTask)->Dict[str, List[SiteItem]]:
        pre_res = self.parse_(context, config)
        return self.postprocess(pre_res)
    
    def update_now(self):
        self.now = datetime.datetime.now()
    def postprocess(self, items:Dict[str, List[SiteItem]])->Dict[str, List[SiteItem]]:
        new_items = defaultdict(list)
        items_accum = defaultdict(list)
        for site_name, site_parse_list in items.items():
            for item in site_parse_list:
                if not item.href2:
                    if 'http' in item.href or 'https' in item.href:
                        #TODO: добавить регулярку
                        item.href2 = item.href
                    else:
                        item.href2 = item.base_url + item.href
                
                if item.href2 in items_accum[site_name]:
                    continue
                new_items[site_name].append(item)
        for site_name, value in new_items.items():
            for item in value:
                items_accum[site_name][item.href2] = item
        return new_items
    
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
        
    
    def parse_(self, context, config: tasks.UrlTask)->Dict[str, List[SiteItem]]:
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
                itm = SiteItem(
                    href,
                    href2,
                    title,
                    str(date),
                    text,
                    city,
                    config.base_url)
                items[config.site_name].append(itm)
        return items



class ParserRss(ParserBase):
    def __init__(self, *args, **kwargs):
        super(ParserRss, self).__init__(*args, **kwargs)
    def check_format(self, thefeed:feedparser.FeedParserDict):
        return 'links' in thefeed.channel and thefeed.channel['links'] and \
                'href' in thefeed.channel['links'][0] and \
                'bezformata' in thefeed.channel['links'][0]['href']
    def parse_(self, context, config: tasks.UrlTask)->Dict[str, List[SiteItem]]:
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
                itm = SiteItem(
                    '',
                    href2,
                    title,
                    str(date),
                    text,
                    '',
                    config.base_url)
                
                items[site_name].append(itm)
        return items

class UniParser:
    def __init__(self):
        self.base_parser = ParserInit()
        self.rss_parser = ParserRss()

from bs4 import BeautifulSoup


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

 