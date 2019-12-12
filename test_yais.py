from pathlib import Path

import pytest

from yais import Image, get_image_data, get_image_size


def get_single_image_data(url) -> Image:
    rv = get_image_data(url)
    assert len(rv) == 1
    assert rv[0].origin == url
    return rv[0]


def test_get_image_data_from_twitter():
    data = get_single_image_data(
        "https://twitter.com/k_yuizaki/status/1177894721785483264"
    )
    assert data.url == "https://pbs.twimg.com/media/EFi5AWIVAAAmfML.jpg:orig"
    assert data.filename == "EFi5AWIVAAAmfML.jpg"


def test_tweet_with_multiple_images():
    rv = get_image_data("https://twitter.com/hunwaritoast/status/1188048064948293632")
    assert len(rv) == 4


@pytest.mark.parametrize(
    "url",
    [
        "https://www.pixiv.net/member_illust.php?mode=medium&illust_id=77005971",
        "https://pixiv.net/member_illust.php?mode=medium&illust_id=77005971",
    ],
)
def test_get_image_data_from_pixiv(url: str):
    data = get_single_image_data(url)
    assert data.origin == url
    assert data.url == "https://pixiv.cat/77005971.png"
    assert data.filename == "77005971_p0.jpg"


def test_get_image_data_from_yandere():
    data = get_single_image_data("https://yande.re/post/show/573334")
    assert (
        data.url
        == "https://files.yande.re/image/e7b0d395ea4975225f62af064077efbe/yande.re%20573334%20animal_ears%20nekomimi%20sakura_koharu%20seifuku%20skirt_lift.jpg"
    )
    assert (
        data.filename
        == "yande.re 573334 animal_ears nekomimi sakura_koharu seifuku skirt_lift.jpg"
    )


def test_get_image_data_from_konachan():
    data = get_single_image_data("https://konachan.net/post/show/292001")
    assert (
        data.url
        == "https://konachan.net/image/543f77cc6a3d7453a868b4ec37396f47/Konachan.com%20-%20292001%20anthropomorphism%20bow%20breasts%20brown_hair%20christmas%20cleavage%20dress%20game_console%20girls_frontline%20green_eyes%20long_hair%20lotpi%20pantyhose%20snow%20snowman.jpg"
    )


def test_get_image_data_from_zerochan():
    data = get_single_image_data("https://www.zerochan.net/1936674")
    assert (
        data.url == "https://static.zerochan.net/Hibike%21.Euphonium.full.1936674.jpg"
    )
    assert data.filename == "Hibike!.Euphonium.full.1936674.jpg"


def test_get_image_size():
    dc_img = Path(__file__).resolve().parent / "fixtures" / "dc.png"
    size = get_image_size(dc_img)
    assert size.width == 512
    assert size.height == 154
