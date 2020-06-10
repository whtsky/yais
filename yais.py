#!/usr/bin/env python3
from dataclasses import dataclass
import json
import logging
import os.path
from pathlib import Path
import re
from typing import List
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup
import imagesize
import pkg_resources
import requests

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


tweet_id_re = re.compile(r"status\/(\d+)")


@support_prefix(("https://twitter.com/",))
def get_image_data_from_twitter(url: str) -> List[Image]:
    # https://github.com/ytdl-org/youtube-dl/issues/12726#issuecomment-304779835
    tweet_id_match = tweet_id_re.search(url)
    if not tweet_id_match:
        raise ValueError("Can't find tweet id")
    tweet_id = tweet_id_match.group(1)

    headers = {
        "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
    }

    try:
        headers["x-guest-token"] = requests.post(
            "https://api.twitter.com/1.1/guest/activate.json", headers=headers, data=b""
        ).json()["guest_token"]
    except:
        logger.exception("failed to get guest token")
        return []

    data = requests.get(
        f"https://api.twitter.com/2/timeline/conversation/{tweet_id}.json",
        headers=headers,
    ).json()
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
def get_image_data_from_moebooru(url: str) -> Image:
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
            f.write(r.content)
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
