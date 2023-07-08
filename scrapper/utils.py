import abc
import yaml
from dataclasses import dataclass, field
from typing import List
import ahocorasick
import pickle
from urllib import parse
import ssl
import requests

class TLSAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = ctx
        return super(TLSAdapter, self).init_poolmanager(*args, **kwargs)

@dataclass
class SiteConfigClass:
    is_rss:bool = False
    lower_ssl_security:bool = False
    site_name:str = ''
    main_xpath:str = ''
    title_xpath:str = ''
    text_xpath:str = ''
    href_xpath:str = ''
    city_xpath:str = ''
    date_xpath:str = ''
    base_url:str = ''
    encoding:str = ''
    urls_path:str = ''
    urls_list:List[str] = field(default_factory=list) 
    @staticmethod
    def from_yaml(site_config:dict):
        res = SiteConfigClass()
        res.is_rss = site_config.get("rss", False)
        res.site_name = site_config.get('site_name', '')
        res.main_xpath = site_config.get('main_xpath', '')
        res.title_xpath = site_config.get('title_xpath', '')
        res.text_xpath = site_config.get('text_xpath', '')
        res.href_xpath = site_config.get('href_xpath', '')
        res.city_xpath = site_config.get('city_xpath', '')
        res.date_xpath = site_config.get('date_xpath', '')
        res.base_url = site_config.get('base_url', '')
        res.encoding = site_config.get('encoding', '')
        res.urls_path = site_config.get('url_path', '')
        res.lower_ssl_security =  site_config.get('lower_ssl_security', False)
        with open(res.urls_path, 'r', encoding='utf-8') as ff:
            res.urls_list = ff.readlines()
        
        return res

def fix_tg_links(links:List[str]):
    for i, url in enumerate(links):
        url_parsed = parse.urlparse(url)
        if 't.me' == url_parsed.netloc:
            url = url.replace('://t.me/', '://t.me/s/')
            links[i] = url
    return links


def undo_fix_tg_link(url:str):
    url_parsed = parse.urlparse(url)
    if 't.me' == url_parsed.netloc:
        url = url.replace('://t.me/s/', '://t.me/')
    return url


class WordSearchWrapper:
    def __init__(self, words:List[str], assemble=True)->None:
        self.automaton = ahocorasick.Automaton()
        for idx, word in enumerate(words):
            self.automaton.add_word(word, (idx, word))
        if assemble:
            self.automaton.make_automaton()
    def check_text(self, text:str)->bool:
        return len(list(self.automaton.iter(text))) > 0
    def dump(self, path:str)->None:
        self.automaton.dump(path, pickle.dumps)
    @staticmethod
    def from_pickle(path:str):
        res = WordSearchWrapper([], assemble=False)
        res.automaton.load(path, pickle.loads)
        return res

    
if __name__=="__main__":
    wswrper = WordSearchWrapper(["два", "пятнадцать", "нет"])
    assert wswrper.check_text("grkenog нет ")
    assert not wswrper.check_text("gjvngnrvoin мташтмт ")
    assert not wswrper.check_text("")
    