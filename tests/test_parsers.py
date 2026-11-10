import pytest
from bs4 import BeautifulSoup

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from autoshift_scraper import (
    remap_dict_keys,
    cleanse_codes,
    scrape_polygon_bl4_codes,
    scrape_ign_bl4_codes,
    scrape_xsmash_codes,
    carry_forward_previous_codes,
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

    def dummy_get(url, timeout=15, headers=None):
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

    def dummy_get(url, timeout=15, headers=None):
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

    def dummy_get(url, timeout=15, headers=None):
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

    def dummy_get(url, timeout=15, headers=None):
        return DummyResp(html)

    import autoshift_scraper

    monkeypatch.setattr(autoshift_scraper.requests, "get", dummy_get)
    codes = scrape_polygon_bl4_codes(existing_codes_set=set())
    assert codes == []


def test_scrape_xsmash_codes_reads_gold_and_skins(monkeypatch):
        html = """
        <script>
        const GOLD_KEYS_DATA = [
            {
                code: "AAAAA-BBBBB-CCCCC-DDDDD-EEEEE",
                expires: createDate(2030, 12, 31, 0, 0, 0, 0),
                title: '3 Gold Keys'
            },
            {
                code: "DUPPE-DUPPE-DUPPE-DUPPE-DUPPE",
                expires: createDate(2030, 12, 31, 0, 0, 0, 0),
                title: '1 Gold Key'
            }
        ];

        const SKINS_DATA = [
            {
                code: "FFFFF-GGGGG-HHHHH-IIIII-JJJJJ",
                expires: createDate(2030, 12, 31, 0, 0, 0, 0),
                title: 'Vault Hunter Skin'
            },
            {
                code: "DUPPE-DUPPE-DUPPE-DUPPE-DUPPE",
                expires: createDate(2030, 12, 31, 0, 0, 0, 0),
                title: 'Duplicate Skin Entry'
            }
        ];
        </script>
        """

        class DummyResp:
                def __init__(self, text):
                        self.text = text

                def raise_for_status(self):
                        pass

        def dummy_get(url, timeout=15, headers=None):
                return DummyResp(html)

        import autoshift_scraper

        monkeypatch.setattr(autoshift_scraper.requests, "get", dummy_get)
        codes = scrape_xsmash_codes(existing_codes_set={"DUPPE-DUPPE-DUPPE-DUPPE-DUPPE"})

        assert len(codes) == 2
        assert codes[0]["code"] == "AAAAA-BBBBB-CCCCC-DDDDD-EEEEE"
        assert codes[0]["reward"] == "3 Gold Keys"
        assert codes[1]["code"] == "FFFFF-GGGGG-HHHHH-IIIII-JJJJJ"
        assert codes[1]["reward"] == "Vault Hunter Skin"


def _ign_dummy(monkeypatch, html, status_code=200):
    class DummyResp:
        def __init__(self, text):
            self.content = text.encode("utf-8")
            self.status_code = status_code

        def raise_for_status(self):
            pass

    def dummy_get(url, timeout=15, headers=None):
        return DummyResp(html)

    import autoshift_scraper

    warnings = []
    monkeypatch.setattr(autoshift_scraper.requests, "get", dummy_get)
    monkeypatch.setattr(
        autoshift_scraper._L, "warning", lambda msg, *a: warnings.append(msg % a)
    )
    return warnings


def test_scrape_ign_bl4_codes_valid_no_warning(monkeypatch):
    html = """
    <table><tbody>
      <tr><td>AAAAA-BBBBB-CCCCC-DDDDD-EEEEE (3 Golden Keys)</td></tr>
      <tr><td><s>FFFFF-GGGGG-HHHHH-IIIII-JJJJJ (1 Golden Key)</s></td></tr>
    </tbody></table>
    <ul><li>KKKKK-LLLLL-MMMMM-NNNNN-OOOOO (Skin)</li></ul>
    """
    warnings = _ign_dummy(monkeypatch, html)
    codes = scrape_ign_bl4_codes(existing_codes_set=set())

    assert [c["code"] for c in codes] == [
        "AAAAA-BBBBB-CCCCC-DDDDD-EEEEE",
        "FFFFF-GGGGG-HHHHH-IIIII-JJJJJ",
        "KKKKK-LLLLL-MMMMM-NNNNN-OOOOO",
    ]
    assert codes[0]["reward"] == "3 Golden Keys"
    assert codes[1]["expired"] is True
    assert warnings == []


def test_scrape_ign_bl4_codes_empty_page_warns(monkeypatch):
    html = "<html><body><div>Checking your browser...</div></body></html>"
    warnings = _ign_dummy(monkeypatch, html, status_code=202)
    codes = scrape_ign_bl4_codes(existing_codes_set=set())

    assert codes == []
    assert len(warnings) == 1
    assert "no tables or lists" in warnings[0]
    assert "HTTP 202" in warnings[0]
    assert f"{len(html)} bytes" in warnings[0]


def _prev_entry(code, game="Borderlands 4", platform="universal", expired=False):
    return {
        "code": code,
        "type": "shift",
        "game": game,
        "platform": platform,
        "reward": "1 Golden Key",
        "archived": "2026-01-01 00:00:00+00:00",
        "expires": "Unknown",
        "expired": expired,
        "link": "https://example.invalid/",
    }


def test_carry_forward_keeps_unseen_previous_codes():
    scraped = _prev_entry("AAAAA-BBBBB-CCCCC-DDDDD-EEEEE")
    autoshift = [{"meta": {"newcodecount": 0}, "codes": [dict(scraped)]}]
    previous = [
        {
            "meta": {"version": "2"},
            "codes": [
                dict(scraped, reward="stale reward"),  # seen this run: not duplicated
                _prev_entry("FFFFF-GGGGG-HHHHH-IIIII-JJJJJ"),  # unseen: carried
                _prev_entry("FFFFF-GGGGG-HHHHH-IIIII-JJJJJ", platform="steam"),
                _prev_entry("KKKKK-LLLLL-MMMMM-NNNNN-OOOOO", expired=True),
                _prev_entry("not-a-valid-code"),  # invalid: never carried
            ],
        }
    ]

    carried = carry_forward_previous_codes(autoshift, previous, include_expired=True)

    keys = [(c["code"], c["platform"]) for c in autoshift[0]["codes"]]
    assert carried == 3
    assert keys == [
        ("AAAAA-BBBBB-CCCCC-DDDDD-EEEEE", "universal"),
        ("FFFFF-GGGGG-HHHHH-IIIII-JJJJJ", "universal"),
        ("FFFFF-GGGGG-HHHHH-IIIII-JJJJJ", "steam"),
        ("KKKKK-LLLLL-MMMMM-NNNNN-OOOOO", "universal"),
    ]
    # the freshly scraped entry wins over the previous one
    assert autoshift[0]["codes"][0]["reward"] == "1 Golden Key"
    # carrying forward never counts as a new code
    assert autoshift[0]["meta"]["newcodecount"] == 0


def test_carry_forward_skips_expired_when_excluded():
    autoshift = [{"meta": {}, "codes": []}]
    previous = [
        {
            "meta": {"version": "2"},
            "codes": [
                _prev_entry("AAAAA-BBBBB-CCCCC-DDDDD-EEEEE"),
                _prev_entry("KKKKK-LLLLL-MMMMM-NNNNN-OOOOO", expired=True),
            ],
        }
    ]
    carried = carry_forward_previous_codes(autoshift, previous, include_expired=False)
    assert carried == 1
    assert [c["code"] for c in autoshift[0]["codes"]] == [
        "AAAAA-BBBBB-CCCCC-DDDDD-EEEEE"
    ]


@pytest.mark.parametrize("previous", [None, [], [{"meta": {}}]])
def test_carry_forward_handles_missing_previous_file(previous):
    autoshift = [{"meta": {}, "codes": []}]
    assert carry_forward_previous_codes(autoshift, previous, True) == 0
    assert autoshift[0]["codes"] == []


def test_main_keeps_codes_when_a_source_returns_nothing(monkeypatch, tmp_path):
    """IGN returning an empty page must not drop the codes only IGN listed."""
    import json
    import types
    import autoshift_scraper

    seen_code = "AAAAA-BBBBB-CCCCC-DDDDD-EEEEE"
    ign_only_code = "FFFFF-GGGGG-HHHHH-IIIII-JJJJJ"
    previous = [
        {
            "meta": {"version": "2"},
            "codes": [_prev_entry(seen_code), _prev_entry(ign_only_code)],
        }
    ]
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "shiftcodes.json").write_text(json.dumps(previous))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(autoshift_scraper, "DIRNAME", str(tmp_path))

    def fake_scrape_codes(webpage):
        if webpage.get("game") != "Borderlands 4":
            return []
        return [
            {
                "game": "Borderlands 4",
                "platform": "universal",
                "sourceURL": "https://example.invalid/",
                "archived": "2026-11-10 00:00:00+00:00",
                "raw_table_html": "",
                "codes": [
                    {
                        "code": seen_code,
                        "reward": "1 Golden Key",
                        "expires": "Unknown",
                        "expired": False,
                    }
                ],
            }
        ]

    monkeypatch.setattr(autoshift_scraper, "scrape_codes", fake_scrape_codes)
    monkeypatch.setattr(autoshift_scraper, "scrape_polygon_bl4_codes", lambda s: [])
    monkeypatch.setattr(autoshift_scraper, "scrape_ign_bl4_codes", lambda s: [])
    monkeypatch.setattr(autoshift_scraper, "scrape_xsmash_codes", lambda s: [])

    autoshift_scraper.main(types.SimpleNamespace(user=None, repo=None, token=None))

    out = json.loads((tmp_path / "data" / "shiftcodes.json").read_text())
    by_code = {c["code"]: c for c in out[0]["codes"]}
    assert set(by_code) == {seen_code, ign_only_code}
    assert by_code[ign_only_code]["archived"] == "2026-01-01 00:00:00+00:00"
    assert out[0]["meta"]["newcodecount"] == 0
