from pytest import LogCaptureFixture

from tiktok_downloader.cookies import _parse_expires


def test_parse_expires_negative() -> None:
    assert _parse_expires(-1) == 0
    assert _parse_expires(-1.0) == 0


def test_parse_expires_none() -> None:
    assert _parse_expires(None) == 0


def test_parse_expires_string_number() -> None:
    assert _parse_expires("123.0") == 123  # noqa: PLR2004


def test_parse_expires_bad_string_logs(caplog: LogCaptureFixture) -> None:
    caplog.set_level("DEBUG")
    assert _parse_expires("bad") == 0
    assert "Could not parse expires value" in caplog.text
