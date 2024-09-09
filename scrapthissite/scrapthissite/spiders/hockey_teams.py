import scrapy


class HockeyTeamsSpider(scrapy.Spider):
    name = "hockey_teams"
    allowed_domains = ["scrapethissite.com"]

    def start_requests(self):
        yield scrapy.Request(url="https://scrapethissite.com/pages/forms/", callback=self.parse)

    def parse(self, response):

        team_name = response.xpath("//td[@class='name']/text()").getall()
        
        for each_team in team_name:
            yield{
                'Team name': (each_team).replace('\n', '').replace('  ', '')
            }
