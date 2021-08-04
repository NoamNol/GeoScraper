import os
from pathlib import Path
import argparse
import geojson
import logging
import time
import asyncio
from wikimapia_scraper import WikimapiaCrawler, NotFoundError, WIKIMAPIA_START_URL

DEFAULT_FILENAME = 'output.geojson'
DEFAULT_OUTDIR = 'output'
WORKERS_NUMBER = 10

# Config argparse
parser = argparse.ArgumentParser(description='Get Geo info from wikimapia.')
parser.add_argument('searchname', metavar='S', type=str, nargs='?',
                    help='Location name to search in [starturl] page')
parser.add_argument('-u', '--starturl', type=str,
                    help=f"Wikimapia start url, default to: '{WIKIMAPIA_START_URL}'")
parser.add_argument('-o', '--outdir', type=str,
                    help=f"Output dir for GeoJSON and log files, default to: '{DEFAULT_OUTDIR}'")
args = parser.parse_args()

# Get args from CLI, env variables, or user input
search_name = args.searchname or \
    os.environ.get('WIKI_SEARCHNAME') or \
    input("Enter search name: ")
start_url = args.starturl or \
    os.environ.get('WIKI_STARTURL') or \
    WIKIMAPIA_START_URL
outdir = args.outdir or \
    os.environ.get('WIKI_OUTDIR') or \
    DEFAULT_OUTDIR
filename_path = os.path.join(outdir, DEFAULT_FILENAME)

Path(outdir).mkdir(parents=True, exist_ok=True)

# Config logging
logging.basicConfig(
    filename=os.path.join(outdir, 'logging.log'),
    # filemode='w',  # use to start afresh
    format='%(asctime)s %(levelname)s:%(message)s',
    encoding='utf-8',
    level=logging.DEBUG
    )


async def main():
    if not search_name:
        print("Nothing to search.")
        return

    print(f"Outdir: '{outdir}'")
    print(f"Start url: '{start_url}'")
    print(f"Search '{search_name}'...")

    try:
        start_time = time.perf_counter()
        geojson_object = await WikimapiaCrawler(
            start_url=start_url, workers_num=WORKERS_NUMBER).run(search_name)
        elapsed = time.perf_counter() - start_time
        print(f"--- executed in {elapsed:0.2f} seconds. ---")
        with open(filename_path, 'w', encoding='utf8') as f:
            geojson.dump(geojson_object, f, ensure_ascii=False)
    except NotFoundError:
        print("Search not found.")
    except Exception:
        raise


if __name__ == "__main__":
    asyncio.run(main())
