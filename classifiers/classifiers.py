import re
import pickle
from datetime import datetime

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

