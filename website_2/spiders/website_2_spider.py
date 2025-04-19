from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service

from scrapy.http import HtmlResponse
import scrapy

from website_2.items import Website2Item
from pathlib import Path
import re



class Website2Spider(scrapy.Spider):
    name = "website_2"

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        # "CONCURRENT_REQUESTS": 1,
        "RETRY_TIMES": 2,
        'DOWNLOAD_TIMEOUT': 30,
        'RETRY_ENABLED': True,

        "DEFAULT_REQUEST_HEADERS": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd"
        },
    }


    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):

        # initialize chromedriver
        spider = super().from_crawler(crawler, *args, *kwargs)

        spider.SELENIUM_DRIVER_EXECUTABLE_PATH = crawler.settings.get("SELENIUM_DRIVER_EXECUTABLE_PATH")
        spider.SELENIUM_DRIVER_ARGUMENTS = crawler.settings.getlist("SELENIUM_DRIVER_ARGUMENTS")
        spider.SELENIUM_PAGELOAD_TIMEOUT = crawler.settings.getint("SELENIUM_PAGELOAD_TIMEOUT", 10)
        spider.WAITING_TIME = crawler.settings.get("WAITING_TIME")
        options = Options()
        for arg in spider.SELENIUM_DRIVER_ARGUMENTS:
            options.add_argument(arg)
        
        service = Service(executable_path=spider.SELENIUM_DRIVER_EXECUTABLE_PATH)
        spider.driver = webdriver.Chrome(
            options=options,
            service=service,
        )

        # page_limit
        spider.page_limit = crawler.settings.getint("PAGE_LIMIT", 1)

        return spider


    # use selenium to click "Carian" button
    def start_requests(self):

        # use selenium to get the dynamically rendered HTML of the first page
        start_url = "https://edl.doe.gov.my/discovery?query=+where+category%3d+%2527EIA+Report%2527&category=EIA%20Report&main=Digital"

        self.driver.get(start_url)
        wait = WebDriverWait(self.driver, self.SELENIUM_PAGELOAD_TIMEOUT)

        try:

            target_area = "content_body_lblSearchResult"
            wait.until(EC.presence_of_element_located((By.ID, "content_body_btnSearch")))
            search_button_element = self.driver.find_element(By.ID, "content_body_btnSearch")
            wait.until(
                EC.presence_of_element_located(
                    (By.ID, target_area)
                )
            )
            
            before_html = self.driver.find_element(By.ID, target_area).get_attribute("innerHTML")
            self.driver.execute_script("arguments[0].scrollIntoView();", search_button_element)
            self.driver.execute_script("arguments[0].click();", search_button_element)

            wait.until(
                EC.presence_of_element_located(
                    (By.ID, target_area)
                )
            )

            wait.until(
                lambda d: d.find_element(By.ID, target_area).get_attribute("innerHTML") != before_html
            )

            html = self.driver.page_source

            current_url = self.driver.current_url
          
            # build scrapy Response
            response = HtmlResponse(
                url=current_url,
                body=html,
                encoding='utf-8',
                request=scrapy.Request(url=current_url),
            )
            yield from self.parse(response)

        except Exception as e:
            self.logger.error(f"Failed to open the first page: {e}")
        
        finally:
            self.driver.quit()


    # get the formdata for POST
    @staticmethod
    def extract_all_formdata(response):
        
        formdata = {
            x.attrib['name']: x.attrib.get('value', '')
            for x in response.xpath('//input[@type="hidden"][@name]')
        }
        for sel in response.xpath('//select[@name]'):
            name = sel.attrib['name']
            selected = sel.xpath('.//option[@selected]/@value').get()
            if not selected:
                selected = sel.xpath('.//option[1]/@value').get()
            formdata[name] = selected or ""

        return formdata


    # POST different pages from 1 to self.page_limit
    def parse(self, response):

        # yield the current page 
        yield response.follow(
            url=response.url, 
            callback=self.parse_listing_page,meta={"Source_page": 1},
            dont_filter=True, # IMPORTANT!!!
        )

        # post pagination targets
        for i in range(0, self.page_limit):
            page_button_str = f'//a[@id="content_body_rptPaging_lbPaging_{i}"]'
            href = response.xpath(f'{page_button_str}/@href').get()
            
            if href and '__doPostBack' in href:
                
                try:

                    # post
                    event_target = re.search(r"__doPostBack\('([^']+)'", href).group(1)

                    if not event_target:
                        self.logger.warning(f"Page {i+1}: __doPostBack href not matched, skipping")
                        continue
                    
                    formdata = Website2Spider.extract_all_formdata(response)
                    formdata['__EVENTTARGET'] = event_target
                    formdata['__EVENTARGUMENT'] = ""
                    
                    yield scrapy.FormRequest(
                        url=response.url,
                        method="POST",
                        formdata=formdata,
                        callback=self.parse_listing_page,
                        dont_filter=True,
                        meta={"Source_page": i+1},
                    )
                
                except Exception as e:
                    self.logger.error(f"Failed to open Page {i+1}: {e}")

                    # formdata={
                    #         "__EVENTTARGET": event_target,
                    #         "__EVENTARGUMENT": "",
                    #         "__VIEWSTATE": viewstate,
                    #         "__EVENTVALIDATION": eventvalidation,
                    #         "__VIEWSTATEGENERATOR": viewstategen,
                    #     },


    # POST info targets to get the URL of info
    def parse_listing_page(self, response):

        # post info targets
        info_button_str = f'//div[@class="col-md-10 sgd"]'
        info_buttons = response.xpath(info_button_str)
        if info_buttons:
            
            for i, info in enumerate(info_buttons, start=1):
                href = info.xpath('a/@href').get()
                if href and '__doPostBack' in href:

                    try:

                        # post
                        event_target = re.search(r"__doPostBack\('([^']+)'", href).group(1)

                        if not event_target:
                            self.logger.warning(f"Page {i}: __doPostBack href not matched, skipping")
                            continue
                        
                        formdata = Website2Spider.extract_all_formdata(response)
                        formdata['__EVENTTARGET'] = event_target
                        formdata['__EVENTARGUMENT'] = ""

                        meta = response.meta.copy()
                        Info_index = (meta['Source_page'] - 1)*len(info_buttons) + i
                        meta["Info_index"] = Info_index

                        yield scrapy.FormRequest(
                            url=response.url,
                            method="POST",
                            formdata=formdata,
                            callback=self.window_open_detail_page,
                            dont_filter=True,
                            meta=meta,
                        )

                    except Exception as e:
                        self.logger.error(f"Failed to open Page {i}: {e}")    


    # deal with "window.open" after POST to get the URL of info
    def window_open_detail_page(self, response):

        try:
            info_url = re.search(r"window\.open\('([^']+)'", response.text).group(1)
            full_url = response.urljoin(info_url)
            yield scrapy.Request(
                url=full_url,
                callback=self.parse_metadata,
                meta=response.meta,
            )

        except Exception as e:
            self.logger.error(f"Failed to get the URL of info: {e}")


    # get metadata of each info
    def parse_metadata(self, response):

        meta = response.meta.copy()
        page_id = meta['Source_page']
        info_id = meta['Info_index']
        metadata = {}
        metadata['Detail_URL'] = response.url
        metadata['Info_index'] = info_id
        metadata['Source_page'] = page_id

        # get page info
        tajuk_title = response.xpath('//span[@id="content_body_lblTitle"]/text()').get()
        tajuk_info = response.xpath('//textarea[@id="content_body_txtTitle"]/text()').get()
        if tajuk_title:
            tajuk_title = tajuk_title.strip()
        if tajuk_info:
            metadata[tajuk_title] = tajuk_info.strip()

        kategori_title = response.xpath('//span[@id="content_body_lblcategory"]/text()').get()
        kategori_info = response.xpath('//textarea[@id="content_body_txtsubcategory"]/text()').get()
        if kategori_title:
            kategori_title = kategori_title.strip()
        if tajuk_info:
            metadata[kategori_title] = kategori_info.strip()

        penulis_title = response.xpath('//span[@id="content_body_lblyear_dc"]/text()').get()
        penulis_info = response.xpath('//textarea[@id="content_body_txtauthor_dc"]/text()').get()
        if penulis_title:
            penulis_title = penulis_title.strip()
        if tajuk_info:
            metadata[penulis_title] = penulis_info.strip()

        pencetak_title = response.xpath('//span[@id="content_body_lblpublisher_dc"]/text()').get()
        pencetak_info = response.xpath('//textarea[@id="content_body_txtpublisher_dc"]/text()').get()
        if pencetak_title:
            pencetak_title = pencetak_title.strip()
        if tajuk_info:
            metadata[pencetak_title] = pencetak_info.strip()

        bahasa_title = response.xpath('//span[@id="content_body_lbllanguage_dc"]/text()').get()
        bahasa_info = response.xpath('//textarea[@id="content_body_txtlanguage_dc"]/text()').get()
        if bahasa_title:
            bahasa_title = bahasa_title.strip()
        if tajuk_info:
            metadata[bahasa_title] = bahasa_info.strip()

        isbn_title = response.xpath('//span[@id="content_body_lblisbn"]/text()').get()
        isbn_info = response.xpath('//textarea[@id="content_body_txtisbn_dc"]/text()').get()
        if isbn_title:
            isbn_title = isbn_title.strip()
        if tajuk_info:
            metadata[isbn_title] = isbn_info.strip()

        keluaran_title = response.xpath('//span[@id="content_body_lblreleased_dc"]/text()').get()
        keluaran_info = response.xpath('//textarea[@id="content_body_txtreleased_dc"]/text()').get()
        if keluaran_title:
            keluaran_title = keluaran_title.strip()
        if tajuk_info:
            metadata[keluaran_title] = keluaran_info.strip()
        
        # post attachment target
        button_str = f'//div[@class="col-md-9 sgd"]'
        buttons = response.xpath(button_str)
        if buttons:
            for i, button in enumerate(buttons):
                button_title = button.xpath('a/text()').get()
                href = button.xpath('a/@href').get()
                if href and '__doPostBack' in href:

                    try:

                        # post
                        event_target = re.search(r"__doPostBack\('([^']+)'", href).group(1)

                        if not event_target:
                            self.logger.warning(f"Page {i}: __doPostBack href not matched, skipping")
                            continue
                        
                        formdata = Website2Spider.extract_all_formdata(response)
                        formdata['__EVENTTARGET'] = event_target
                        formdata['__EVENTARGUMENT'] = ""
                        metadata['Attachment_index'] = i+1
                        metadata['Button_title'] = button_title

                        yield scrapy.FormRequest(
                            url=response.url,
                            method="POST",
                            formdata=formdata,
                            callback=self.window_open_attachment,
                            dont_filter=True,
                            meta=metadata,
                        )        

                    except Exception as e:
                        self.logger.error(f"Failed to POST attachments target {i}: {e}")

                else: 
                    metadata['Attachment_index'] = -1
                    yield scrapy.Request(
                        url=response.url,
                        callback=self.no_attachment, 
                        meta=metadata,
                        dont_filter=True,
                    )
        else:
            metadata['Attachment_index'] = -2
            yield scrapy.Request(
                url=response.url,
                callback=self.no_attachment, 
                meta=metadata,
                dont_filter=True,
            )


    # deal with "window.open" after POST to get the URL of attachments
    def window_open_attachment(self, response):

        try:
            file_url = re.search(r"window\.open\('([^']+)'", response.text).group(1)
            full_url = response.urljoin(file_url)
            
            yield scrapy.Request(
                url=full_url,
                callback=self.save_attachment,
                errback=self.handle_timeout,
                meta=response.meta,
            )

        except Exception as e:
            self.logger.error(f"Failed to get the URL of attachment: {e}")

    
    # pass item to pipeline
    def save_attachment(self, response):

        item = Website2Item()
        file_url = response.url
        if "epub" in file_url:
            pdf_path = response.xpath('//input[@id="inpHide"]/@value').get()
            file_url = response.urljoin(pdf_path)
        else:
            file_url = file_url.replace("viewerVID?p=", "")
            file_url = file_url.replace("https://docs.google.com/viewerng/viewer?url=", "")
        
        item['file_urls'] = [file_url]
        meta = response.meta.copy()
        meta['Attachment_URLs'] = [file_url]

        item['meta'] = meta

        yield item


    # in case that there is timeout for self.window_open_attachment()
    def handle_timeout(self, failure):
        request = failure.request
        item_err = Website2Item()
        file_url = request.url

        file_url = file_url.replace("viewerVID?p=", "")
        file_url = file_url.replace("https://docs.google.com/viewerng/viewer?url=", "")

        item_err['file_urls'] = [file_url]
        meta = request.meta.copy()
        meta['Attachment_URLs'] = [file_url]
        item_err['meta'] = meta

        print(f"timeout_meta:{meta}")

        yield item_err


    # there are some info without attachments, empty item['file_urls']
    def no_attachment(self, response):

        item = Website2Item()
        item['file_urls'] = []
        meta = response.meta.copy()
        meta['Attachment_URLs'] = []

        print(f"missing_meta:{meta}")

        item['meta'] = meta
        yield item   