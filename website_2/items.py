# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class Website2Item(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    file_urls = scrapy.Field()
    files = scrapy.Field()
    # Source_page = scrapy.Field()
    # Info_index = scrapy.Field()
    # Attachment_index = scrapy.Field()
    meta = scrapy.Field()