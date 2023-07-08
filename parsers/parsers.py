from bs4 import BeautifulSoup


class ParserBase:
    def parse(self):
        raise RuntimeError("Method must be redefined")

class ParserInit(ParserBase):
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
