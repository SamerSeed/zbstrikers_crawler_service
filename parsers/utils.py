from dataclasses import dataclass, field
from typing import List
import ahocorasick
import pickle
import telebot
import numpy as np
from bs4 import BeautifulSoup
import re
from dateutil import parser

class WordSearchWrapper:
    def __init__(self, words:List[str], assemble:bool=True)->None:
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


class TgParser:
    variants = [lambda url:{
                    'class': 'tgme_widget_message js-widget_message',
                    'data-post': '/'.join(url.split('/')[-2:]),
                }, 
                lambda url:{
                'class': 'tgme_widget_message text_not_supported_wrap js-widget_message',
                'data-post': '/'.join(url.split('/')[-2:]),
                }]
    seek_vars = [{'class': 'tgme_widget_message_text js-message_text'}, {'class': 'tgme_widget_message_text js-message_text before_footer'}]
    def parse_tg(self, data:str, url:str):
        soup = BeautifulSoup(data, features='lxml')
        div = None
        for variant in self.variants:
            div = soup.find('div', variant(url))
            if div: break
        if not div:return None
        for s_var in self.seek_vars:
            div = div.find('div', s_var)
            if div:
                return div.getText()    
        return None

    
if __name__=="__main__":
    wswrper = WordSearchWrapper(["два", "пятнадцать", "нет"])
    assert wswrper.check_text("grkenog нет ")
    assert not wswrper.check_text("gjvngnrvoin мташтмт ")
    assert not wswrper.check_text("")
    