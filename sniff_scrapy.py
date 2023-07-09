import scrapper.scrapy_crapper
from scrapy.crawler import CrawlerProcess
from scrapy import signals

import yaml

from scrapy.signalmanager import dispatcher


if __name__ == "__main__":
    fabriq = scrapper.scrapy_crapper.SpiderMaker("config.yaml")
    spd = fabriq.prepare_process()
    results = []
    def crawler_results(signal, sender, item, response, spider):
        print(item)
        results.append(item)
    dispatcher.connect(crawler_results, signal=signals.item_scraped)
    spd.start()
    print(results)
    
    # process = CrawlerProcess({
    #     'USER_AGENT': 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)'
    # })
    # process.crawl(spd)
    # process.start()
    