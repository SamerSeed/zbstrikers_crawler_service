import scrapper.scrapy_crapper
import yaml


if __name__ == "__main__":
    fabriq = scrapper.scrapy_crapper.SpiderMaker("config.yaml")
    spd = fabriq.spawn_spider(0)