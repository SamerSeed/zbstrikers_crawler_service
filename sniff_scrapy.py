import scrapper.scrapy_crapper
from scrapy.crawler import CrawlerProcess
import yaml


if __name__ == "__main__":
    fabriq = scrapper.scrapy_crapper.SpiderMaker("config.yaml")
    spd = fabriq.spawn_spider(0)
    # process = CrawlerProcess({
    #     'USER_AGENT': 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)'
    # })
    # process.crawl(spd)
    # process.start()
    