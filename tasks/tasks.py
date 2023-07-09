import abc
import yaml
from dataclasses import dataclass, field, fields
from typing import List

@dataclass
class UrlTask:
    is_rss:bool = False
    lower_ssl_security:bool = False
    site_name:str = ''
    main_xpath:str = ''
    title_xpath:str = ''
    text_xpath:str = ''
    href_xpath:str = ''
    city_xpath:str = ''
    date_xpath:str = ''
    base_url:str = ''
    encoding:str = ''
    url:str = ''


@dataclass
class SiteConfigClass:
    is_rss:bool = False
    lower_ssl_security:bool = False
    site_name:str = ''
    main_xpath:str = ''
    title_xpath:str = ''
    text_xpath:str = ''
    href_xpath:str = ''
    city_xpath:str = ''
    date_xpath:str = ''
    base_url:str = ''
    encoding:str = ''
    urls_path:str = ''
    urls_list:List[str] = field(default_factory=list) 
    @staticmethod
    def from_yaml(site_config:dict):
        res = SiteConfigClass()
        res.is_rss = site_config.get("rss", False)
        res.site_name = site_config.get('site_name', '')
        res.main_xpath = site_config.get('main_xpath', '')
        res.title_xpath = site_config.get('title_xpath', '')
        res.text_xpath = site_config.get('text_xpath', '')
        res.href_xpath = site_config.get('href_xpath', '')
        res.city_xpath = site_config.get('city_xpath', '')
        res.date_xpath = site_config.get('date_xpath', '')
        res.base_url = site_config.get('base_url', '')
        res.encoding = site_config.get('encoding', '')
        res.urls_path = site_config.get('url_path', '')
        res.lower_ssl_security =  site_config.get('lower_ssl_security', False)
        with open(res.urls_path, 'r', encoding='utf-8') as ff:
            res.urls_list = ff.readlines()
        
        return res
    def produce_task_head(self)->UrlTask:
        tsk = UrlTask()
        for cls_field in fields(self):
            if not (cls_field.name in  {"urls_path" , "urls_list"}):
                setattr(tsk, cls_field.name, getattr(self, cls_field.name))
        return tsk
    def create_task_list(self)->List[UrlTask]:
        tasklist = []
        for url in self.urls_list:
            tsk = self.produce_task_head()
            tsk.url = url
            tasklist += [tsk]
        return tasklist

