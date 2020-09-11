#!/usr/bin/env python
# -*- coding:utf-8 -*-

from .curl import query
from .html_extractors import Extractor
from .data_storage import DataStorage

import uuid
from urllib.parse import urlparse

from rq import Queue

from .worker_connector import redis_connection
from .screenshot import get_screenshot

def go_depth(target, parent, depth=0, is_onion=True,
             in_scope=False, use_proxy=True, re_crawl=True):
    spider = Spider(base_url=target,
           depth=depth,
           is_onion=is_onion,
           in_scope=in_scope,
           use_proxy=use_proxy,
           re_crawl=re_crawl,
           parent=parent)
    spider.proccess()

class Spider:

    def __init__(self, base_url, depth=0, is_onion=True,
                 in_scope=False, use_proxy=True, re_crawl=True, parent=None):
        self.base_url = base_url
        self.netloc = urlparse(self.base_url).netloc
        self.is_onion = is_onion
        self.in_scope = in_scope
        self.depth = depth
        self.proxy = use_proxy
        self.re_crawl = re_crawl
        self.response = query(base_url)
        self.parent = parent
        self.q = Queue(name="high", connection=redis_connection)


    def _save_or_update(self, data):
        ds = DataStorage()
        if ds.is_url_exist(self.base_url):
            if self.re_crawl:
                ds.update_crawled_url(self.base_url, data)
        else:
            return ds.add_crawled_url(data)

    def proccess(self):

        json_data = {'netloc': self.netloc,
                     'url': self.base_url,
                     'status': self.response['status'],
                     'seen_time': self.response['seen_time'],
                     'parent': self.parent}

        if self.response['status']:
            if 'html' in self.response:
                data = Extractor(base_url=self.base_url, html=self.response['html'])
                try:
                    body = data.get_body()
                except Exception as e:
                    print(e)
                    body = ""
                json_data = {'netloc': self.netloc,
                             'url': self.base_url,
                             'is_onion': self.is_onion,
                             'in_scope': self.in_scope,
                             'parent': self.parent,
                             'status': self.response['status'],
                             'html': self.response['html'],
                             'body': body,
                             'title': data.get_title(),
                             'emails': data.get_emails(),
                             'links': data.get_links(),
                             'images': data.get_img_links(),
                             'addresses': {
                                 'btc': data.get_bitcoin_addrs(),
                                 'monero': data.get_monero_addrs(),
                                 'eth': data.get_eth_addrs()},
                             'seen_time': self.response['seen_time'],
                             }

                obj_uuid = uuid.uuid4().hex
                if int(self.response['status']) == 200: #OK
                    get_screenshot(self.base_url, obj_uuid)
                    json_data['capture_id'] = obj_uuid


            parent_id = self._save_or_update(json_data)

            if 'links' in json_data and self.depth: # depth > 0
                depth_step = 0
                while depth_step < self.depth: # while step not reached the thr
                    for link in json_data['links']:
                        self.q.enqueue_call(func=go_depth,
                                       args=(link['url'], parent_id,
                                             depth_step, link['is_onion'],
                                             link['in_scope'],),
                                       ttl=86400, result_ttl=1)
                    depth_step = depth_step + 1
