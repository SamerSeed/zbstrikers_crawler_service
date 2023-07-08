import json
import re
import zlib
from datetime import datetime
from time import sleep
from urllib.parse import urlparse
from logger import logger
from typing import Dict
from pathlib import Path
import joblib


def load_checkpoint(checkpoint_dir:str)->Dict:
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

