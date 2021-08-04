# Wikimapia Scraper

Get GeoJSON from Wikimapia

## Get started
### Windows
```powershell
py -m venv env
.\env\Scripts\activate
pip install -r requirements.txt
python src/geo_scraper.py "Country name"
```

### Unix/macOS
```shell
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
python src/geo_scraper.py "Country name"
```

### Docker
```shell
docker build -t geoscraper .
docker run -it -e WIKI_SEARCHNAME="Country name" geoscraper
```

## Options
**`WIKI_SEARCHNAME`**
> "Location name" to search in [starturl] page.

**`--starturl`** / **`WIKI_STARTURL`**
> Wikimapia start url, default to: 'https://wikimapia.org/country/'.

**`--outdir`** / **`WIKI_OUTDIR`**
> Output dir for GeoJSON and log files, default to: 'output'.

## Examples
**Python:**
```powershell
python src/geo_scraper.py "Rehovot" --starturl "https://wikimapia.org/country/Israel/Hamerkaz/" --outdir "geo-out"
```

**Docker:**
```shell
# You can replace '$PWD' with your host output dir
docker run -v "$PWD":/app/output -it \
    -e WIKI_SEARCHNAME="Rehovot" \
    -e WIKI_STARTURL="https://wikimapia.org/country/Israel/Hamerkaz/" \
    geoscraper
```

<br/>
