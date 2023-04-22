# -*- coding: utf-8 -*-
"""
Created on 2022-11-07 14:26:00
---------
@summary:
---------
@author: 逢高SAMA
"""

import os
import re
import json
import logging

import feapder
from items import european_union_data_item
from feapder.db.mysqldb import MysqlDB
from feapder.utils.log import log


class SpiderDevice(feapder.Spider):

    def __init__(self, redis_key, **kwargs):
        super().__init__(redis_key, **kwargs)
        self.db = MysqlDB()
        self.logger = self.log_handle()

    def start_requests(self):

        # self.db = MysqlDB()
        # self.logger = self.log_handle()
        scope_code = ["device", "system", "procedure-pack"]
        # scope_code = ["device"]
        search_url = "https://ec.europa.eu/tools/eudamed/api/devices/udiDiData?page=0&pageSize=25&size=25&sort=primaryDi%2CASC&sort=versionNumber%2CDESC&iso2Code=en&deviceScopes=refdata.device-scope.{scope}&languageIso2Code=en"

        for scope in scope_code:
            url = search_url.format(scope=scope)
            yield feapder.Request(url, scope=scope, first=True)

    def parse(self, request, response):

        response_json = json.loads(response.text)

        if response_json.get("content"):
            uuid_list = response_json.get("content")

            if request.first:
                total_page = int(response_json.get("totalPages"))
                total_page = 5
                
                for i in range(1, total_page):
                    url = re.sub(r"page=(.*?)&", "page="+str(i)+"&", response.url)
                    # self.logger.debug(url)
                    yield feapder.Request(url, scope=request.scope, first=False)

            for uuid_item in uuid_list:
                uuid = uuid_item["uuid"]

                url = "https://ec.europa.eu/tools/eudamed/api/devices/udiDiData/%s?languageIso2Code=en" % uuid
                yield self.parse_url(url, uuid, request.scope)
                
                url = "https://ec.europa.eu/tools/eudamed/api/devices/basicUdiData/udiDiData/%s?languageIso2Code=en" % uuid
                yield self.parse_url(url, uuid, request.scope)

        else:
            self.logger.error("查无此页 %s" % request.url)

    def parse_url(self, url, uuid, scope):

        result = self.db.find("select res_url from european_union_data where res_url='%s'" % url)
        if len(result) == 0:
            return feapder.Request(url, callback=self.parse_detail, uuid=uuid , scope=scope)
        elif len(result) == 1:
            log.debug("%s 已爬取" % url)
            # self.logger.debug("已爬取 %s " % url)
        else:
            log.error("%s 在数据库有多份数据存在" % url)
            self.logger.error("在数据库有多份数据存在 %s" % url)

    def parse_detail(self, request, response):

        item = european_union_data_item.EuropeanUnionDataItem()
        item.type = "Devices/SPPs"
        item.scope = request.scope
        item.res_url = request.url
        item.uuid = request.uuid
        item.json_data = response.text
        yield item

    def failed_request(self, request, response):

        log_text = "超过最大重试次数的request" + request.url
        self.logger.error(log_text)

        yield request

    def log_handle(self):

        log_dir_path = os.path.join(os.getcwd(), 'log')
        if not os.path.exists(log_dir_path):
            os.mkdir(log_dir_path)
        log_path = os.path.join(log_dir_path, 'log_device.txt')

        logger = logging.getLogger("log_device")
        logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger


if __name__ == "__main__":
    SpiderDevice(redis_key="feapder:devices").start()
