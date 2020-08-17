#!/usr/bin/env python3
from dataclasses import dataclass
import logging
from pathlib import Path
import re
from typing import Dict, Iterator, List, Optional, Union, Iterable, Callable
from urllib.parse import unquote, urlparse
from appdirs import user_cache_dir
import json
import os
import collections

from bs4 import BeautifulSoup
import imagesize
import pkg_resources
import requests

logger = logging.getLogger(__name__)

try:
    __version__ = pkg_resources.get_distribution("yais").version
except pkg_resources.DistributionNotFound:
    __version__ = "dev"

DEFAULT_CACHE_DIR = user_cache_dir("yais", "whtsky", __version__)


@dataclass
class Image:
    url: str
    filename: str
    origin: str


_GET_IMAGE_DATA_FUNCTION = Callable[
    [str, Optional[Path]], Union[Image, Iterable[Image]]
]
__MAPPING: Dict[str, _GET_IMAGE_DATA_FUNCTION] = {}


def support_prefix(prefixes: Iterable[str]):
    def wrapper(f):
        for p in prefixes:
            __MAPPING[p] = f
        return f

    return wrapper


tweet_id_re = re.compile(r"status\/(\d+)")

twitter_headers = {
    "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
}


def get_guest_token() -> str:
    response = requests.post(
        "https://api.twitter.com/1.1/guest/activate.json",
        headers=twitter_headers,
        data=b"",
    )
    data: Dict[str, str] = response.json()
    logging.debug("get guest token response: %s", data)
    return data["guest_token"]


_twitter_guest_token_filename = "guest_token"


def read_twitter_guest_token_from_cache(cache: Path) -> Optional[str]:
    try:
        with open(cache / _twitter_guest_token_filename, "r") as f:
            return f.read()
    except:
        return None


def save_twitter_guest_token(cache: Path, guest_token: str):
    with open(cache / _twitter_guest_token_filename, "w") as f:
        f.write(guest_token)


@support_prefix(("https://twitter.com/",))
def get_image_data_from_twitter(url: str, cache_dir: Optional[Path]) -> List[Image]:
    # https://github.com/ytdl-org/youtube-dl/issues/12726#issuecomment-304779835
    tweet_id_match = tweet_id_re.search(url)
    if not tweet_id_match:
        raise ValueError("Can't find tweet id")
    tweet_id = tweet_id_match.group(1)

    def _try_download_with_guest_token(guest_token: str) -> List[Image]:
        headers = twitter_headers.copy()
        headers["x-guest-token"] = guest_token
        data = requests.get(
            f"https://api.twitter.com/2/timeline/conversation/{tweet_id}.json",
            headers=headers,
        ).json()
        logging.debug("get twitter metadata: %s", data)
        return [
            Image(
                url=media["media_url_https"] + ":orig",
                filename=os.path.basename(urlparse(media["media_url_https"],).path),
                origin=url,
            )
            for media in data["globalObjects"]["tweets"][tweet_id]["extended_entities"][
                "media"
            ]
        ]

    if cache_dir:
        guest_token = read_twitter_guest_token_from_cache(cache_dir)
        if guest_token:
            logger.debug("got guest token from cache:", guest_token)
            try:
                return _try_download_with_guest_token(guest_token)
            except:
                pass
    guest_token = get_guest_token()
    logger.debug("got new guest token:", guest_token)
    rv = _try_download_with_guest_token(guest_token)
    if cache_dir:
        save_twitter_guest_token(cache_dir, guest_token)
    return rv


pixiv_id_re = re.compile(r"\d{7,}")


@support_prefix(("https://www.pixiv.net", "https://pixiv.net"))
def get_image_data_from_pixiv(url: str, cache_dir: Optional[Path]) -> Image:
    pixiv_id = pixiv_id_re.findall(url)[0]
    img_url = f"https://pixiv.cat/{pixiv_id}.png"
    resp = requests.head(img_url)
    return Image(
        url=img_url,
        filename=os.path.basename(urlparse(resp.headers["x-origin-url"]).path),
        origin=url,
    )


_post_register_re = re.compile(rb"Post\.register\(({.+})\)")


@support_prefix(
    (
        "https://konachan.net/post/show/",
        "http://konachan.net/post/show/",
        "https://konachan.com/post/show/",
        "http://konachan.com/post/show/",
        "https://yande.re/post/show/",
    )
)
def get_image_data_from_moebooru(url: str, cache_dir: Optional[Path]) -> Image:
    content = requests.get(url).content
    soup = BeautifulSoup(content, features="html.parser")
    try:
        img_url = soup.find("a", {"class": "highres-show"})["href"]
    except TypeError:
        post_register_match = _post_register_re.search(content)
        if not post_register_match:
            raise Exception(f"Can't find img_url from {url}")
        data = json.loads(post_register_match.group(1))
        img_url = data["file_url"]
    return Image(url=img_url, filename=unquote(os.path.basename(img_url)), origin=url)


@support_prefix(("https://www.zerochan.net/"))
def get_image_data_from_zerochan(url: str, cache_dir: Optional[Path]) -> Image:
    content = requests.get(url).content
    soup = BeautifulSoup(content, features="html.parser")
    img_url = soup.find("a", {"class": "preview"})["href"]
    return Image(url=img_url, filename=unquote(os.path.basename(img_url)), origin=url)


def get_image_data(
    url: str, cache_dir: Optional[Union[str, Path]] = None
) -> Iterable[Image]:
    """

    :param url: URL to get imgae data from.
    :param cache_dir: path to store cache. pass `None` to disable cache.
    """
    if isinstance(cache_dir, str):
        cache_dir = Path(cache_dir)
    for prefix, f in __MAPPING.items():
        if url.startswith(prefix):
            func_cache_dir: Optional[Path] = cache_dir and cache_dir / f.__name__
            if func_cache_dir and not func_cache_dir.exists():
                func_cache_dir.mkdir(parents=True)
            rv = f(url, func_cache_dir)
            if isinstance(rv, collections.Iterable):
                return rv
            return [rv]

    raise ValueError(f"Unsupported url: {url}")


def download_image(img: Image, path: Path) -> Path:
    r = requests.get(img.url, stream=True)
    if r.status_code == 200:
        img_path = path / img.filename
        with open(img_path, "wb") as f:
            f.write(r.content)
        return img_path
    else:
        raise Exception(r)


@dataclass
class ImageSize:
    width: int
    height: int


def get_image_size(path: Path) -> ImageSize:
    width, height = imagesize.get(path)
    return ImageSize(width=width, height=height)


def cli():
    import argparse

    parser = argparse.ArgumentParser(description="Download image from url")
    parser.add_argument("urls", nargs="+")
    parser.add_argument(
        "-d", "--dest", default=".", help="folder to store downloaded images."
    )
    parser.add_argument(
        "--debug", default=False, help="enable debug logging", action="store_true"
    )
    parser.add_argument(
        "-c", "--cache", default=DEFAULT_CACHE_DIR, help="folder to store caches.",
    )
    parser.add_argument(
        "-v", "--version", action="version", version="%(prog)s " + __version__
    )

    args = parser.parse_args()

    dest = Path(args.dest)
    cache = Path(args.cache)

    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s",)
    logger.setLevel(level=args.debug and logging.DEBUG or logging.INFO,)

    for url in args.urls:
        logger.info("Processing %s" % url)
        for image_data in get_image_data(url, cache):
            logger.info("Downloading %s" % image_data.url)
            img_path = download_image(image_data, dest)
            logger.info("Saved to %s." % (img_path))
            img_size = get_image_size(img_path)
            logger.info("Image Size: %sx%s" % (img_size.width, img_size.height))
        logger.info("%s Done" % url)

    logger.info("Finish")


if __name__ == "__main__":
    cli()
