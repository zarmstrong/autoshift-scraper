import pytest
from bs4 import BeautifulSoup

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from autoshift_scraper import (
    remap_dict_keys,
    cleanse_codes,
    scrape_polygon_bl4_codes,
)


def test_remap_dict_keys_basic():
    d = {
        "SHiFT Code": "CODE1",
        "Reward": "Golden Key",
        "Expire Date": "2024-12-31",
        "Other": "foo",
    }
    mapped = remap_dict_keys(d)
    assert mapped["code"] == "CODE1"
    assert mapped["reward"] == "Golden Key"
    assert mapped["expires"] == "2024-12-31"
    assert mapped["Other"] == "foo"


def test_cleanse_codes_expiry_and_expired():
    codes = [
        {
            "SHiFT Code": "CODE1",
            "Reward": "Golden Key",
            "Expire Date": "Expires: 2024-12-31",
        },
        {"SHiFT Code": "CODE2", "Reward": "Golden Key", "expired": "yes"},
    ]
    cleansed = cleanse_codes(codes)
    assert cleansed[0]["expires"] == "2024-12-31"
    assert cleansed[0]["expired"] is False
    assert cleansed[1]["expired"] is True


def test_scrape_polygon_bl4_codes_valid(monkeypatch):
    html = """
    <h2 id="all-borderlands-4-shift-codes">All Borderlands 4 SHiFT codes</h2>
    <ul>
      <li>J9XBB-KK9T3-CRTBW-BBT3T-KTBTW (1 Golden Key) — added Sept. 22</li>
      <li>AAAAA-BBBBB-CCCCC-DDDDD-EEEEE (5 Golden Keys) — added Sept. 23</li>
      <li>invalid-format (Not a Key)</li>
    </ul>
    """

    class DummyResp:
        def __init__(self, text):
            self.content = text.encode("utf-8")

        def raise_for_status(self):
            pass

    def dummy_get(url, timeout=15):
        return DummyResp(html)

    import autoshift_scraper

    monkeypatch.setattr(autoshift_scraper.requests, "get", dummy_get)
    codes = scrape_polygon_bl4_codes(existing_codes_set=set())
    assert len(codes) == 2
    assert codes[0]["code"] == "J9XBB-KK9T3-CRTBW-BBT3T-KTBTW"
    assert codes[0]["reward"] == "1 Golden Key"
    assert codes[1]["code"] == "AAAAA-BBBBB-CCCCC-DDDDD-EEEEE"
    assert codes[1]["reward"] == "5 Golden Keys"


def test_scrape_polygon_bl4_codes_duplicates(monkeypatch):
    html = """
    <h2 id="all-borderlands-4-shift-codes">All Borderlands 4 SHiFT codes</h2>
    <ul>
      <li>J9XBB-KK9T3-CRTBW-BBT3T-KTBTW (1 Golden Key) — added Sept. 22</li>
    </ul>
    """

    class DummyResp:
        def __init__(self, text):
            self.content = text.encode("utf-8")

        def raise_for_status(self):
            pass

    def dummy_get(url, timeout=15):
        return DummyResp(html)

    import autoshift_scraper

    monkeypatch.setattr(autoshift_scraper.requests, "get", dummy_get)
    codes = scrape_polygon_bl4_codes(
        existing_codes_set={"J9XBB-KK9T3-CRTBW-BBT3T-KTBTW"}
    )
    assert len(codes) == 0


def test_scrape_polygon_bl4_codes_missing_h2(monkeypatch):
    html = "<div>No codes here</div>"

    class DummyResp:
        def __init__(self, text):
            self.content = text.encode("utf-8")

        def raise_for_status(self):
            pass

    def dummy_get(url, timeout=15):
        return DummyResp(html)

    import autoshift_scraper

    monkeypatch.setattr(autoshift_scraper.requests, "get", dummy_get)
    codes = scrape_polygon_bl4_codes(existing_codes_set=set())
    assert codes == []


def test_scrape_polygon_bl4_codes_missing_ul(monkeypatch):
    html = '<h2 id="all-borderlands-4-shift-codes">All Borderlands 4 SHiFT codes</h2>'

    class DummyResp:
        def __init__(self, text):
            self.content = text.encode("utf-8")

        def raise_for_status(self):
            pass

    def dummy_get(url, timeout=15):
        return DummyResp(html)

    import autoshift_scraper

    monkeypatch.setattr(autoshift_scraper.requests, "get", dummy_get)
    codes = scrape_polygon_bl4_codes(existing_codes_set=set())
    assert codes == []
