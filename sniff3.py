import asyncio
import time
import yaml
# from scrapper.scrapper import Scrapper
import scrapper
    
if __name__ == "__main__":
    f = open("config.yaml", encoding='utf-8')
    configs = [scrapper.SiteConfigClass.from_yaml(i) for i in yaml.load(f, Loader=yaml.FullLoader)[:10]]
    scrapper_ = scrapper.Scrapper()
    print(configs[0])
    loop = asyncio.get_event_loop()
    try:
        q = loop.run_until_complete(asyncio.run(scrapper_.proc(configs[0])))
        print(q[0])
    finally:
        loop.close()
    