# website_2_crawler

A Scrapy-based crawler that extracts metadata, attachments, html, and geospatial visualizations from project pages on [edl.doe.gov.my](https://edl.doe.gov.my/).  
Designed as the second part of the BASF assignment for crawling.

## Features

- Crawls project reports from paginated search results
- Extracts:
  - Metadata (title, description, dates, categories ...)
  - All attachments
  - Thumbnail image
  - Full HTML source per project
- Organizes data in a clear directory structure:
  ```
  data/
  ├──page_<index>/
     ├── project_<index>/
         ├── metadata.json
         ├── Source.html
         ├── Thumbnail.jpg
         └── attachment/
             └── *.png / ...
  ```

## Setup

Create a virtual environment and install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

To run the crawler:

```bash
scrapy crawl website_2
```

To output metadata as JSONL:

```bash
scrapy crawl website_2 -o output.jsonl
```

## Project Structure

- `spiders/website_2_spider.py` — main crawling logic
- `pipelines.py` — handles attachment downloading, metadata saving, html and screenshot generation
- `settings.py` — Scrapy configuration settings

## Notes

- This crawler uses Selenium to capture thumbnail screenshots and full html content.
- Make sure to update the `SELENIUM_DRIVER_EXECUTABLE_PATH` in `settings.py` to match the path of your own ChromeDriver installation (default is `/usr/local/bin/chromedriver`).