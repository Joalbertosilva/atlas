"""Normalização e sanitização de resultados externos. Texto remoto é dado, nunca HTML nem instrução."""
import html
import re
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import nh3

_WS = re.compile(r"\s+")
_CTRL = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\u200b-\u200f\u202a-\u202e]")
_TRACKING = re.compile(r"^(utm_|fbclid$|gclid$|mc_|igshid$|ref_src$)")


def clean_text(value, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    text = nh3.clean(value, tags=set(), attributes={})  # remove toda marcação
    text = html.unescape(text)
    text = _CTRL.sub("", text)
    text = _WS.sub(" ", text).strip()
    text = text.replace("<", "‹").replace(">", "›")  # nenhuma tag sobrevive mesmo após unescape
    return text[: limit - 1] + "…" if len(text) > limit else text


def safe_url(value) -> str | None:
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        return None
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def dedupe_key(url: str) -> str:
    p = urlsplit(url)
    host = (p.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    query = urlencode(sorted((k, v) for k, v in parse_qsl(p.query) if not _TRACKING.match(k)))
    return f"{host}{p.path.rstrip('/')}?{query}"


def domain_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def parse_date(value) -> str | None:
    """Mantém somente datas fornecidas pelo mecanismo e válidas; nunca inventa data."""
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.year < 1990 or dt.year > 2100:
        return None
    return dt.isoformat()
