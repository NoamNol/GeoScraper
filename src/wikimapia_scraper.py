from typing import Iterator, Optional
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, parse_qs, urlparse
from geojson import Feature, Point, FeatureCollection
import logging
from dataclasses import dataclass, field
import re
import asyncio
from asyncio_pool import AioPool
from utils import caseless_equal, is_base_url


WIKIMAPIA_START_URL = 'https://wikimapia.org/country/'


class NotFoundError(Exception):
    pass


class SetAsyncioQueue(asyncio.Queue):
    """asyncio.Queue with 'in queue' operator.

    Note: this is only a basic implementation to use with the .put() and .get().
    """
    def __init__(self, *args, **kwargs):
        self.set_data = set()
        super().__init__(*args, **kwargs)

    async def put(self, item):
        self.set_data.add(item)
        await super().put(item)

    async def get(self):
        item = await super().get()
        self.set_data.remove(item)
        return item

    def __contains__(self, item):
        return item in self.set_data


class GeoPoint:
    def __init__(self, *, lon, lat):
        self.lon = lon
        self.lat = lat


@dataclass
class GeoLocation:
    url: str
    points: list[GeoPoint]
    data: dict = field(default_factory=dict)


class WikimapiaCrawler:
    def __init__(self, start_url: str = WIKIMAPIA_START_URL, workers_num: int = 1):
        self.start_url = start_url
        self.urls_to_visit: SetAsyncioQueue = SetAsyncioQueue()
        self.visited_urls: set[str] = set()
        self.geo_locations: list[GeoLocation] = []
        self.workers_num: int = workers_num  # too many workers will probably block the site

    async def download_html(self, url: str) -> BeautifulSoup:
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, requests.get, url)
        res = await future
        soup = BeautifulSoup(res.content, 'html.parser')
        return soup

    def get_linked_urls(self, url: str, soup: BeautifulSoup) -> Iterator[str]:
        a_tags = soup.find_all('a', href=True)
        for a_tag in a_tags:
            path = a_tag['href']
            if path:
                fullurl = urljoin(url, path)
                # Get only deeper urls:
                if is_base_url(fullurl, url):
                    yield fullurl

    def get_geo_locations(self, url: str, soup: BeautifulSoup) -> Iterator[GeoLocation]:
        # Pairs of 'Name map' are inside 'li' tags
        for li_tag in soup.find_all('li'):
            a_tags = li_tag.find_all('a')
            if len(a_tags) == 2 and a_tags[1].text == 'map':
                location_name = a_tags[0].text
                location_url = a_tags[0].get('href')
                location_fullurl = urljoin(url, location_url)
                map_url = a_tags[1].get('href')
                map_point = self.get_point_from_map_url(map_url)
                if map_point:
                    geo_location = GeoLocation(
                        points=[map_point], url=location_fullurl, data={'name': location_name})
                    yield geo_location

    def get_params_from_map_url(self, map_url: str) -> dict:
        """Get params from (illegal) map url.

        A 'map url' looks like: '/#lang=en&lat=-14.260057&lon=-170.649948&z=13&m=w'.
        This url is actually illegal, so normal utils can't read its params.
        """
        # Replace '/#lang=en&' with '?' to make map_url a legal url
        legal_url = re.sub(r'^.*?lat', '?lat', map_url)
        parsed = urlparse(legal_url)
        params: dict = parse_qs(parsed.query)

        # Now each param value is a list, like: {param: [value], param2: [value2, value3]}.
        # Convert lists of one item to the item:
        flatten_params = {
            key: params[key][0] if len(params[key]) == 1 else params[key] for key in params}
        return flatten_params

    def get_point_from_map_url(self, map_url: str) -> Optional[GeoPoint]:
        try:
            map_params = self.get_params_from_map_url(map_url)
            lat_value_str = map_params.get('lat')
            lon_value_str = map_params.get('lon')
            if lat_value_str and lon_value_str:
                return GeoPoint(lat=float(lat_value_str), lon=float(lon_value_str))
        except Exception:
            pass
        return None

    async def get_location_page_data(self, url: str) -> dict:
        soup = await self.download_html(url)
        placeinfo = {}
        place_description = soup.find(id='place-description')
        if place_description and place_description.text:
            placeinfo['description'] = place_description.text
        return placeinfo

    async def add_url_to_visit(self, url: str) -> None:
        if url not in self.visited_urls and url not in self.urls_to_visit:
            await self.urls_to_visit.put(url)

    def add_geo_location(self, geo_location: GeoLocation) -> None:
        if geo_location and geo_location.points and geo_location not in self.geo_locations:
            self.geo_locations.append(geo_location)

    async def crawl(self, url: str) -> None:
        soup = await self.download_html(url)
        # Find urls in page
        for url in self.get_linked_urls(url, soup):
            await self.add_url_to_visit(url)
        # Find 'map' locations in page
        for location in self.get_geo_locations(url, soup):
            self.add_geo_location(location)

    async def find_location_in_page(self, url: str, search_name: str) -> tuple[str, str]:
        soup = await self.download_html(url)
        a_tags = soup.select(".linkslist a", href=True)
        for a_tag in a_tags:
            if a_tag['href'] and caseless_equal(a_tag.text, search_name):
                return (a_tag.text, urljoin(self.start_url, a_tag['href']))
        raise NotFoundError(f'{search_name} not found in {url}')

    def can_be_location_page_url(self, url: str) -> bool:
        """Check if url can be location page url.

        Location page url looks like: 'http://wikimapia.org/15002/Arad-Israel'.
        Unlike most of the urls in Wikimapia, it doesn't start with '/country/'.
        """
        return not urlparse(url).path.startswith('/country/')

    def build_geojson(self) -> FeatureCollection:
        feature_list = []
        for location in self.geo_locations:
            if location.points:
                point = Point((location.points[0].lon, location.points[0].lat))
                feature = Feature(geometry=point, properties=location.data)
                feature_list.append(feature)
        return FeatureCollection(feature_list)

    async def url_handler(self) -> None:
        while True:
            url = await self.urls_to_visit.get()
            logging.info(f'Crawling: {url}')
            try:
                await self.crawl(url)
            except Exception:
                logging.exception(f'Failed to crawl: {url}')
            finally:
                self.visited_urls.add(url)
                self.urls_to_visit.task_done()

    async def location_handler(self, location: GeoLocation) -> None:
        if self.can_be_location_page_url(location.url):
            try:
                location.data |= await self.get_location_page_data(location.url)
            except Exception:
                logging.exception(f'Failed to crawl location page: {location.url}')

    async def run(self, location_name: str) -> Optional[FeatureCollection]:
        # (May raise NotFoundError)
        _, location_url = await self.find_location_in_page(self.start_url, location_name)
        await self.add_url_to_visit(location_url)

        # Find all locations and sub-locations in location_url
        handlers = [asyncio.create_task(self.url_handler()) for n in range(self.workers_num)]

        # Wait to all url_handlers to finish
        # See https://docs.python.org/3/library/asyncio-queue.html
        await self.urls_to_visit.join()
        for h in handlers:
            h.cancel()
        await asyncio.gather(*handlers, return_exceptions=True)

        # Now, self.geo_locations is just the data in the 'Name map' pairs in Wikimapia.
        # Add more info from the Wikimapia pages, like the description of each location:
        pool = AioPool(size=self.workers_num)
        await pool.map(self.location_handler, self.geo_locations)

        return self.build_geojson()
