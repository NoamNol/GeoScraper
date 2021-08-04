import unicodedata
from urllib.parse import urlparse


def normalize_caseless(text: str) -> str:
    return unicodedata.normalize("NFKD", text.casefold())


def caseless_equal(left: str, right: str) -> bool:
    '''Compare strings without worrying about case or encoding.
    See: https://stackoverflow.com/a/29247821/10727283
    '''
    return normalize_caseless(left) == normalize_caseless(right)


def is_base_url(url: str, baseurl: str) -> bool:
    p_url = urlparse(url)
    p_baseurl = urlparse(baseurl)
    return p_url.netloc == p_baseurl.netloc and p_url.path.startswith(p_baseurl.path)
