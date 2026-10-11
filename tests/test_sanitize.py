"""Sanitização: texto remoto é dado, nunca HTML executável."""
from atlas_api.search.sanitize import clean_text, dedupe_key, parse_date, safe_url


def test_clean_text_strips_script_and_keeps_plain():
    raw = '<script>alert(1)</script>Apuração <b>oficial</b>'
    out = clean_text(raw, 200)
    assert "<script>" not in out and "</script>" not in out
    assert "<b>" not in out
    assert "oficial" in out
    assert "Apuração" in out


def test_clean_text_unescapes_then_neutralizes_tags():
    out = clean_text("&lt;img src=x onerror=alert(1)&gt;resultado", 200)
    assert "<" not in out
    assert "resultado" in out


def test_safe_url_blocks_private_and_non_http():
    assert safe_url("https://www.tse.jus.br/eleicoes")
    assert safe_url("http://g1.globo.com/x")
    assert safe_url("javascript:alert(1)") is None
    assert safe_url("file:///etc/passwd") is None
    assert safe_url("https://user:pass@example.com/") is None
    assert safe_url("ftp://example.com/a") is None


def test_dedupe_ignores_tracking_params_and_www():
    a = "https://www.g1.globo.com/noticia?utm_source=x&id=1"
    b = "https://g1.globo.com/noticia/?id=1"
    assert dedupe_key(a) == dedupe_key(b)


def test_parse_date_never_invents():
    assert parse_date(None) is None
    assert parse_date("") is None
    assert parse_date("ontem") is None
    assert parse_date("2026-10-04T18:38:00") == "2026-10-04T18:38:00"
    assert parse_date("1880-01-01T00:00:00") is None
