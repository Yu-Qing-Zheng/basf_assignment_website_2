# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service

from scrapy.pipelines.files import FilesPipeline
from scrapy.http import Request
from itemadapter import ItemAdapter
from pathlib import Path
import shutil
import json


class SaveJsonPipeline:

    def open_spider(self, spider):

        main_dir = Path('./data')
        if main_dir.exists() and main_dir.is_dir():
            shutil.rmtree(main_dir)

        self.meta_group = {}

    def process_item(self, item, spider):

        meta = item['meta']
        key = (meta['Source_page'], meta['Info_index'])
        SCRAPY_META_KEYS = {'depth', 'download_timeout', 'download_slot', 'download_latency'}
        if key not in self.meta_group:
            self.meta_group[key] = {k: v for k, v in meta.items() if k != 'Attachment_URLs' and k not in SCRAPY_META_KEYS}
            self.meta_group[key]['Attachment_URLs'] = list(meta.get('Attachment_URLs', []))

        else:
            self.meta_group[key]['Attachment_URLs'].extend(meta.get('Attachment_URLs', []))

        
        return item

    def close_spider(self, spider):

        try:
            
            for meta in self.meta_group.values():
                
                meta.pop('Attachment_index', None)

                # create project folder
                main_dir = Path('./data')
                page_id = meta['Source_page']
                page_dir = main_dir / Path(f"page_{str(page_id)}")
                info_index = meta['Info_index']
                report_index_dir = page_dir / Path(f"project_{str(info_index)}")
                report_index_dir.mkdir(parents=True, exist_ok=True)

                file_path = report_index_dir / 'metadata.json'
                with open(file_path, mode='w', encoding='utf-8') as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)
            

        except Exception as e:
            spider.logger.error(f"Failed to save JSON: {e}")

    

class SaveFilePipeline(FilesPipeline):

    def file_path(self, request, response = None, info = None, *, item = None):
        
        # create page folder
        meta = item['meta']
        page_id = meta['Source_page']
        info_id = meta['Info_index']
        info_dir = f"page_{str(page_id)}/project_{str(info_id)}/attachment/"

        real_name = Path(request.url.split("%")[-1]).name

        # info_dir.mkdir(parents=True, exist_ok=True)

        print(f"item_in_file_path: {item}")

        return info_dir + real_name
    
    def item_completed(self, results, item, info):
        
        item['files'] = [x['path'] for ok, x in results if ok]
        
        return item
    

class SaveHtmlPipeline:

    @classmethod
    def from_crawler(cls, crawler):

        settings = crawler.settings
        executable_path = settings.get("SELENIUM_DRIVER_EXECUTABLE_PATH")
        driver_args = settings.getlist("SELENIUM_DRIVER_ARGUMENTS")
        timeout = settings.getint("SELENIUM_PAGELOAD_TIMEOUT", 10)
        waiting_time = settings.getint("WAITING_TIME", 10)
    
        return cls(executable_path, driver_args, timeout, waiting_time)
    
    def __init__(self, executable_path, driver_args, timeout, waiting_time):
        self.executable_path = executable_path
        self.driver_args = driver_args
        self.timeout = timeout
        self.waiting_time = waiting_time
        options = Options()
        for arg in self.driver_args:
            options.add_argument(arg)
        
        service = Service(executable_path=self.executable_path)
        self.pipelinedriver = webdriver.Chrome(
            options=options,
            service=service,
        )
    
    def close_spider(self, spider):
        self.pipelinedriver.quit()
        
    def process_item(self, item, spider):
        
        meta = item['meta']
        detail_url = meta['Detail_URL']
        self.pipelinedriver.get(detail_url)
        wait = WebDriverWait(self.pipelinedriver, self.timeout)
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "img.fotorama__img")))
            map_element = self.pipelinedriver.find_element(By.CSS_SELECTOR, "img.fotorama__img")
            self.pipelinedriver.execute_script("arguments[0].scrollIntoView();", map_element)
            # wait.until(
            #     EC.presence_of_element_located(
            #         (By.CSS_SELECTOR, "img.fotorama__img")
            #     )
            # )
            import time
            time.sleep(self.waiting_time)

            # create page folder
            main_dir = Path('./data')
            page_id = meta['Source_page']
            info_id = meta['Info_index']
            page_dir = main_dir / Path(f"page_{str(page_id)}")
            info_dir = page_dir / Path(f"project_{str(info_id)}")
            info_dir.mkdir(parents=True, exist_ok=True)

            image_name = "Thumbnail.jpg"
            html_name = "Source.html"

            image_path = info_dir / image_name
            html_path = info_dir / html_name

            map_element.screenshot(str(image_path))

        except Exception as e:
            spider.logger.error(f"Failed to save IMAGE: {e}")

        try:
            html = self.pipelinedriver.page_source
            f = open(html_path, mode="w", encoding="UTF-8")
            f.write(html)
            f.close()

        except Exception as e:
            spider.logger.error(f"Failed to save HTML: {e}")

        return item