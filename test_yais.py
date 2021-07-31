from pathlib import Path

import pytest
import responses

from yais import get_image_data
from yais import get_image_size
from yais import Image

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def get_single_image_data(url) -> Image:
    rv = list(get_image_data(url))
    assert len(rv) == 1
    assert rv[0].origin == url
    return rv[0]


def test_tweet_with_multiple_images():
    rv = get_image_data("https://twitter.com/hunwaritoast/status/1188048064948293632")
    assert len(list(rv)) == 4


@responses.activate
def test_moebooru_teapot():
    responses.add(
        responses.GET,
        "https://konachan.net/post/show/296375",
        body=open(FIXTURES_DIR / "296375.html").read(),
    )
    rv = get_single_image_data("https://konachan.net/post/show/296375")
    assert (
        rv.url
        == "https://konachan.net/image/987f3116299ee612238f08c0c95a46c2/Konachan.com%20-%20296727%20aqua_eyes%20blonde_hair%20boots%20brown_eyes%20brown_hair%20forest%20gloves%20gray_hair%20group%20gun%20long_hair%20pink_hair%20ponytail%20snow%20thighhighs%20tree%20uniform%20weapon.jpg"
    )


@pytest.mark.parametrize(
    "origin,url,filename",
    [
        [
            "https://www.pixiv.net/member_illust.php?mode=medium&illust_id=77005971",
            "https://i.pximg.net/img-original/img/2019/09/28/18/00/27/77005971_p0.jpg",
            "77005971_p0.jpg",
        ],
        [
            "https://pixiv.net/member_illust.php?mode=medium&illust_id=77005971",
            "https://i.pximg.net/img-original/img/2019/09/28/18/00/27/77005971_p0.jpg",
            "77005971_p0.jpg",
        ],
        [
            "https://yande.re/post/show/573334",
            "https://files.yande.re/image/e7b0d395ea4975225f62af064077efbe/yande.re%20573334%20animal_ears%20nekomimi%20sakura_koharu%20seifuku%20skirt_lift.jpg",
            "yande.re 573334 animal_ears nekomimi sakura_koharu seifuku skirt_lift.jpg",
        ],
        [
            "https://konachan.net/post/show/292001",
            "https://konachan.net/image/543f77cc6a3d7453a868b4ec37396f47/Konachan.com%20-%20292001%20anthropomorphism%20bow%20breasts%20brown_hair%20christmas%20cleavage%20dress%20game_console%20girls_frontline%20green_eyes%20long_hair%20lotpi%20pantyhose%20snow%20snowman.jpg",
            "Konachan.com - 292001 anthropomorphism bow breasts brown_hair christmas cleavage dress game_console girls_frontline green_eyes long_hair lotpi pantyhose snow snowman.jpg",
        ],
        [
            "https://www.zerochan.net/1936674",
            "https://static.zerochan.net/Hibike%21.Euphonium.full.1936674.jpg",
            "Hibike!.Euphonium.full.1936674.jpg",
        ],
        [
            "https://twitter.com/k_yuizaki/status/1177894721785483264",
            "https://pbs.twimg.com/media/EFi5AWIVAAAmfML.jpg:orig",
            "EFi5AWIVAAAmfML.jpg",
        ],
    ],
)
def test_get_image_data(origin: str, url: str, filename: str):
    data = get_single_image_data(origin)
    assert data.origin == origin
    assert data.url == url
    assert data.filename == filename


def test_get_image_size():
    dc_img = FIXTURES_DIR / "dc.png"
    size = get_image_size(dc_img)
    assert size.width == 512
    assert size.height == 154
