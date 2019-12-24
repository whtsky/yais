#!/usr/bin/env python3
import logging
import os.path
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List
from urllib.parse import unquote, urlparse

import imagesize
import pkg_resources
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

try:
    __version__ = pkg_resources.get_distribution("yais").version
except pkg_resources.DistributionNotFound:
    __version__ = "dev"


@dataclass
class Image:
    url: str
    filename: str
    origin: str


__MAPPING = {}


def support_prefix(prefixes):
    def wrapper(f):
        for p in prefixes:
            __MAPPING[prefixes] = f
        return f

    return wrapper


@support_prefix(("https://twitter.com/",))
def get_image_data_from_twitter(url: str) -> List[Image]:
    content = requests.get(url).content
    soup = BeautifulSoup(content, features="html.parser")
    return [
        Image(
            url=image["data-image-url"] + ":orig",
            filename=os.path.basename(urlparse(image["data-image-url"]).path),
            origin=url,
        )
        for image in soup.find_all("div", {"class": "js-adaptive-photo"})
    ]


pixiv_id_re = re.compile(r"\d{7,}")


@support_prefix(("https://www.pixiv.net", "https://pixiv.net"))
def get_image_data_from_pixiv(url: str) -> Image:
    pixiv_id = pixiv_id_re.findall(url)[0]
    img_url = f"https://pixiv.cat/{pixiv_id}.png"
    resp = requests.head(img_url)
    return Image(
        url=img_url,
        filename=os.path.basename(urlparse(resp.headers["x-origin-url"]).path),
        origin=url,
    )


@support_prefix(
    (
        "https://konachan.net/post/show/",
        "http://konachan.net/post/show/",
        "https://konachan.com/post/show/",
        "http://konachan.com/post/show/",
        "https://yande.re/post/show/",
    )
)
def get_image_data_from_moebooru(url: str) -> Image:
    content = requests.get(url).content
    soup = BeautifulSoup(content, features="html.parser")
    img_url = soup.find("a", {"class": "highres-show"})["href"]
    return Image(url=img_url, filename=unquote(os.path.basename(img_url)), origin=url)


@support_prefix(("https://www.zerochan.net/"))
def get_image_data_from_zerochan(url: str) -> Image:
    content = requests.get(url).content
    soup = BeautifulSoup(content, features="html.parser")
    img_url = soup.find("a", {"class": "preview"})["href"]
    return Image(url=img_url, filename=unquote(os.path.basename(img_url)), origin=url)


def get_image_data(url: str) -> List[Image]:
    for prefix, f in __MAPPING.items():
        if url.startswith(prefix):
            rv = f(url)
            if isinstance(rv, list):
                return rv
            return [rv]

    raise ValueError(f"Unsupported url: {url}")


def download_image(img: Image, path: Path) -> Path:
    r = requests.get(img.url, stream=True)
    if r.status_code == 200:
        img_path = path / img.filename
        with open(img_path, "wb") as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)
        return img_path
    else:
        raise r


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
        "-v", "--version", action="version", version="%(prog)s " + __version__
    )

    args = parser.parse_args()

    dest = Path(args.dest)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    for url in args.urls:
        logging.info("Processing %s" % url)
        for image_data in get_image_data(url):
            logging.info("Downloading %s" % image_data.url)
            img_path = download_image(image_data, dest)
            logging.info("Saved to %s." % (img_path))
            img_size = get_image_size(img_path)
            logging.info("Image Size: %sx%s" % (img_size.width, img_size.height))
        logging.info("%s Done" % url)

    logger.info("Finish")


if __name__ == "__main__":
    cli()
