import re
import pickle
from datetime import datetime
import logger
import numpy as np
from natasha import Segmenter, MorphVocab, NewsEmbedding, NewsMorphTagger, Doc
from navec import Navec
from slovnet import NER

THRESHOLD_V2 = 0.2792921738167593


rename_dict = {'ORG': ' _орг ',
               'PER': ' _пер ',
               'LOC': ' _лок '}

text_numbers = ['ноль', 'нуль', 'один', 'два', 'три', 'четыре', 'пять',
                'шесть', 'семь', 'восемь', 'девять', 'десять',
                'одиннадцать', 'двенадцать', 'тринадцать', 'четырнадцать',
                'пятнадцать', 'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать',
                'двадцать', 'тридцать', 'сорок', 'пятьдесят', 'шестьдесят',
                'семьдесят', 'восемьдесят', 'девяносто',
                'сто', 'двести', 'триста', 'четыреста', 'пятьсот',
                'шестьсот', 'семьсот', 'восемьсот', 'девятьсот',
                'тысяча', 'миллион', 'миллиард', 'триллион',
                'полтысяча', 'полмиллиона', 'полмиллиард', 'полумиллиард', 'полмиллиарда',
                'полутриллион', 'полтриллиона', 'млрд', 'млд', 'млн']

dats = ['декабрь', 'январь', 'февраль', 'март', 'апрель', 'май',
        'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь',
        'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресение']

kys = set(['коллектив', 'отдел', 'экипаж', 'группа',
           'подразделение', 'отделение', 'забастовка', 'митинг'])


class ZabastcomClassificator:
    def __init__(self,
                 path_stops,
                 path_navec_weights,
                 path_ner_weights,
                 path_pkl_vectorizer,
                 path_pkl_model):

        self.stops = self.get_stops(path_stops)
        self.ner = self.prepare_ner(path_navec_weights, path_ner_weights)
        self.morph_vocab = MorphVocab()
        self.segmenter = Segmenter()
        self.morph_tagger = NewsMorphTagger(NewsEmbedding())
        self.vectorizer = pickle.load(open(path_pkl_vectorizer, 'rb'))
        self.model = pickle.load(open(path_pkl_model, 'rb'))

    def get_stops(self, path_stops):
        stops = []
        with open(path_stops, 'r', encoding='utf-8') as file:
            for line in file:
                stops.append(line.strip())
        stops = set(stops)
        stops.remove('не')
        return stops

    def prepare_ner(self, path_navec_weights, path_ner_weights):
        navec = Navec.load(path_navec_weights)
        ner = NER.load(path_ner_weights)
        ner.navec(navec)
        return ner

    def prep_text(self, text):
        text = self.clean_news(text)
        text = self.extra_clean_text(text)
        return text

    def clean_news(self, ftext):
        cleaned_ftext = ''
        paragraphs = [x for x in ftext.split('\n') if len(x.split()) > 0]
        for paragraph in paragraphs:
            doc = Doc(paragraph)
            doc.segment(self.segmenter)
            for sent in doc.sents:
                cleaned_sent = self.clean_text(sent.text)
                cleaned_ftext = cleaned_ftext + cleaned_sent + ' . '
            cleaned_ftext = cleaned_ftext + '\n'
        return cleaned_ftext

    def extra_clean_text(self, text):
        for x in text_numbers:
            text = text.replace(' '+x+' ', ' _чсл ')
        for x in dats:
            text = text.replace(' '+x+' ', ' _дат ')
        text = re.sub(r'(_чсл )+', r'_чсл ', text+' ')
        text = re.sub(r'(_дат )+', r'_дат ', text+' ')
        return text

    def clean_text(self, text):
        markup = self.ner(text)
        text = text.lower()
        lemm_tokens = []
        doc = Doc(text)
        doc.segment(self.segmenter)
        doc.tag_morph(self.morph_tagger)
        for x in doc.tokens:
            flag1 = False
            for span in markup.spans:
                if span.start <= x.start and span.stop >= x.stop:
                    flag1 = True
                    y = rename_dict[span.type]
                    lemm_tokens.append(y)
                    break
            if not flag1:
                x.lemmatize(self.morph_vocab)
                y = x.lemma
                lemm_tokens.append(y)
        text = ' '.join(lemm_tokens)
        text = re.sub(r'«\w+»', r' _орг ', text)
        text = re.sub(r'"\w+"', r' _орг ', text)
        text = re.sub(r'\d+', r' _чсл ', text)
        text = re.sub(r'[^а-я_ ]', r' ', text)
        text = re.sub(r' _ ', r' ', text)
        text = ' '.join([w for w in text.split() if w not in self.stops])
        text = ' '.join([w for w in text.split() if (len(w) > 2 or w == 'не')])
        text = re.sub(r'(_орг )+', r'_орг ', text+' ')
        text = re.sub(r'(_пер )+', r'_пер ', text+' ')
        text = re.sub(r'(_лок )+', r'_лок ', text+' ')
        text = re.sub(r'(_чсл )+', r'_чсл ', text+' ')
        text = text.replace(
                'Если ваши трудовые права нарушены, вы можете обратиться в государственную инспекцию труда, ' +
                'в том числе дистанционно через сервис "Сообщить о проблеме" на портале "Онлайнинспекция.рф"',
                '',
        )
        text = text.replace(
                'Подписывайтесь на нас в',
                '',
        )

        l = text.split()
        for i in range(len(l)-1):
            if l[i] == 'не':
                l[i] = l[i] + '_' + l[i+1]
                l[i+1] = ' '
        text = ' '.join(l)
        text = ' '.join(text.split())
        return text

    def is_it_plural(self, list_of_texts):
        result = []
        if isinstance(list_of_texts, str):
            list_of_texts = [list_of_texts]
        for text in list_of_texts:
            text = str(text)
            doc = Doc(text)
            doc.segment(self.segmenter)
            doc.tag_morph(self.morph_tagger)
            plur_nouns = []
            for token in doc.tokens:
                if 'NOUN' in token.pos and 'Plur' in str(token.feats):
                    plur_nouns.append(token.text)
                    break
            if len(plur_nouns) == 0 and len(kys.intersection(text.lower().split())) == 0:
                result.append(0)
            else:
                result.append(1)
        return result

    def find_duplicates_cleaned_texts(self, list_of_texts, ksim=0.95, verbose=True):
        """
        input:
        list_of_texts = ['cleaned text A','cleaned text B','cleaned text A','cleaned text D',...]
        ksim = threshold of cosine distance between text_vectors
        
        output:
        idx_texts = [[0,2],[1],[3],...]
        """
        clusters = np.array([-1]*len(list_of_texts))
        X = self.vectorizer.transform(list_of_texts)
        for i in range(len(list_of_texts)):
            if clusters[i]==-1:
                clusters_idx = (clusters==-1)
                temp = X[clusters_idx,:]
                cos_idx = (temp.dot(X[i].T)>ksim).T.toarray()[0]
                clusters[clusters_idx] += cos_idx.astype(np.int32)*(i+1)
        idx_texts = []
        for x in np.unique(clusters):
            idx = np.where(clusters == x)[0]
            idx_texts.append(idx.tolist())
        if verbose:    
            verbose_text = 'В {} текстах найдено: {} уникальных и {} дубликатов'
            print(verbose_text.format(len(clusters),
                                      len(np.unique(clusters)),
                                      len(clusters)-len(np.unique(clusters)))) 
        return idx_texts

    def find_duplicates(self, list_of_texts, ksim=0.95, verbose=True):
        """
        то же самое, что и find_duplicates_cleaned_texts,
        только перед запуском запускаем чистку каждого текста
        """
        cleaned_texts = []
        for text in list_of_texts:
            cleaned_text = self.prep_text(text)
            paragraphs = cleaned_text.split('\n')[:4]
            cleaned_text = ' '.join(paragraphs)
            cleaned_texts.append(cleaned_text)
        idx_texts = self.find_duplicates_cleaned_texts(cleaned_texts, ksim=ksim, verbose=verbose)
        return idx_texts

    def predict(self, list_of_texts, verbose=False):
        cleaned_texts = []
        if isinstance(list_of_texts, str):
            list_of_texts = [list_of_texts]
        for text in list_of_texts:
            cleaned_text = self.prep_text(text)
            paragraphs = cleaned_text.split('\n')[:4]
            cleaned_text = ' '.join(paragraphs)
            cleaned_texts.append(cleaned_text)
        if verbose:
            for x in cleaned_texts:
                print(x)
        X = self.vectorizer.transform(cleaned_texts)
        y = self.model.predict_proba(X)[:, 1]
        y = np.round(y, 3)
        return y

def search_news_v2(
        texts,
        links,
        dates_s,
        checkpoint,
        classifier):
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

    pred_prob = classifier.predict(texts)

    # predict
    pred = (pred_prob >= THRESHOLD_V2).astype(np.bool8)
    if 0 == np.count_nonzero(pred):
        return []

    pred_prob = pred_prob[pred]
    links = links[pred]
    texts = texts[pred]
    res = []
    for idx, (prob, url, text) in enumerate(zip(pred_prob, links, texts)):
        if url in checkpoint['history_v2'].url_map:
            continue
        checkpoint['history_v2'].url_map[url] = prob
        url_to_show = undo_fix_tg_link(url)
        res.append((prob, url_to_show, text))
    return res



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
