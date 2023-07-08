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

