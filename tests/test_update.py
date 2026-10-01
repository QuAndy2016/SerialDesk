"""U127: version handling for the update check (pure functions, no network)."""

from app.update import is_newer, parse_version


def test_parse_version_accepts_the_shapes_github_returns():
    assert parse_version("v1.4.0") == (1, 4, 0)
    assert parse_version("1.4.0") == (1, 4, 0)
    assert parse_version("v1.4") == (1, 4)
    assert parse_version(" v0.14.0 ") == (0, 14, 0)


def test_parse_version_rejects_junk():
    for bad in ("", None, "latest", "vNext", "v1.x"):
        assert parse_version(bad) == ()


def test_is_newer_only_when_strictly_newer():
    assert is_newer("v1.5.0", "1.4.0")
    assert is_newer("1.4.1", "1.4.0")
    assert is_newer("v2.0", "1.9.9")
    assert not is_newer("v1.4.0", "1.4.0")
    assert not is_newer("v1.3.9", "1.4.0")
    assert not is_newer("latest", "1.4.0")
    assert not is_newer("v1.5.0", "not-a-version")


def test_padding_keeps_short_versions_comparable():
    assert is_newer("1.4.1", "1.4")
    assert not is_newer("1.4", "1.4.0")
