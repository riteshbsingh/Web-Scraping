from flask import Flask, request, jsonify
from scrapy.crawler import CrawlerRunner
from scrapy.utils.log import configure_logging
from scrapy import signals
from pydispatch import dispatcher
import scrapy
import threading
from twisted.internet import reactor
from flask_cors import CORS
import scrapy.crawler as crawler
from multiprocessing import Process, Queue
from twisted.internet import reactor
from scrapy.utils.project import get_project_settings
import multiprocessing

app = Flask(__name__)
CORS(app)

scraped_data = {}
scraping_lock = threading.Lock()
reactor_started = threading.Event()

class CompanyDetailsSpider(scrapy.Spider):
    name = "company_details"
    allowed_domains = ["europages.co.uk"]

    def __init__(self, url=None, *args, **kwargs):
        super(CompanyDetailsSpider, self).__init__(*args, **kwargs)
        self.start_urls = [url]
        dispatcher.connect(self.spider_closed, signal=signals.spider_closed)

    def parse(self, response):
        global scraped_data
        with scraping_lock:
            company_name = response.xpath("//h1[@class='ep-epages-header-title text-h6 text-sm-h4']/text()").get()
            company_address = response.xpath("//p[@class='ma-0']/text()").getall()
            company_country = response.xpath("//span[@class='font-weight-bold']/text()").get()
            company_website = response.xpath("//a[@class='ep-epages-home-link-card v-card v-sheet v-sheet--outlined theme--light pa-4 ep-epages-home-website-link v-card v-card--link v-sheet theme--light']/@href").get()

            company_info = response.xpath("//dd[@class='ep-key-value__value text-body-1']/text()").getall()
            company_specialize = response.xpath("//li[@class='ep-keywords__list-item black black--text body-2 rounded-sm px-2 py-1']/text()").getall()

            company_size = company_info[0] if len(company_info) > 0 else ''
            company_established = company_info[1] if len(company_info) > 1 else ''
            address_street = company_address[0] if len(company_address) > 0 else ''
            address_town = company_address[1] if len(company_address) > 1 else ''

            specializations_list = [each_specialization.strip().replace('\n', '').replace('  ', '') for each_specialization in company_specialize]

            scraped_data.update({
                'Platform use': 'https://www.europages.co.uk/',
                'Company Name': company_name.strip() if company_name else '',
                'Address street': address_street.strip(),
                'Address town': address_town.strip().replace(' -', ''),
                'Country Name': company_country.strip() if company_country else '',
                'Website': company_website.strip() if company_website else '',
                'Established': company_established.strip(),
                'Nr. Of employees': company_size.strip(),
                'Specialize in': ', '.join(specializations_list),
            })

            print(scraped_data)

    def spider_closed(self, spider):
        print("Spider closed")


def scrape_spider(q, url):
    """
    This function runs the spider and communicates the result via a multiprocessing queue.
    """
    try:
        runner = CrawlerRunner(get_project_settings())
        deferred = runner.crawl(CompanyDetailsSpider, url=url)
        deferred.addBoth(lambda _: reactor.stop())
        reactor.run()
        q.put(scraped_data)  # No exceptions occurred
    except Exception as e:
        q.put(e)  # Send the exception to the queue if something goes wrong


def run_crawler(url):
    """
    This function creates a multiprocessing process to run the spider in a separate process.
    """
    # Create a multiprocessing queue and process
    global scraped_data
    q = multiprocessing.Queue()
    p = multiprocessing.Process(target=scrape_spider, args=(q, url))

    # Start the process
    p.start()

    # Get the result from the queue (None if successful, exception if an error occurred)
    scraped_data = q.get()

    # Wait for the process to complete
    p.join()

    return scraped_data

    # If an exception was encountered, raise it
    # if result is not None:
    #     raise result


@app.route('/', methods=['POST'])
def index():
    global scraped_data
    print("Hello, world!")
    if request.method == 'POST':
        url = request.json.get('company_url')
        print(url)

        if not url:
            return jsonify({"error": "Please provide a valid URL"}), 400

        with scraping_lock:
            scraped_data.clear()  # Clear data before each scrape

        thread = threading.Thread(target=run_crawler, args=(url,))
        thread.start()
        thread.join()
        print(scraped_data)
        return jsonify(scraped_data)

    return jsonify({"error": "Invalid request method"}), 405


if __name__ == "__main__":
    multiprocessing.set_start_method('spawn')
    app.run(threaded=False, port=5001)
 