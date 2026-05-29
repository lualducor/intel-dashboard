import hashlib
import re
import unicodedata
import urllib.parse


TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "ref",
    "ref_src",
    "_hsenc",
    "_hsmi",
    "spm",
}


def canonicalize(url: str) -> str:
    if not url:
        return ""

    parsed = urllib.parse.urlsplit(url)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    port = parsed.port

    netloc = hostname
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{netloc}:{port}"

    path = parsed.path
    if path != "/":
        path = path.rstrip("/")

    params = []
    for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        normalized_key = key.lower()
        if normalized_key.startswith("utm_") or normalized_key in TRACKING_PARAMS:
            continue
        params.append((key, value))

    query = urllib.parse.urlencode(sorted(params, key=lambda item: item[0]))
    return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))


def dedup_hash(canonical_url: str) -> str:
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()


def normalized_title(title: str) -> str:
    if not title:
        return ""

    decomposed = unicodedata.normalize("NFD", title)
    without_accents = "".join(
        c for c in decomposed if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", without_accents.lower()).strip()


def content_hash(title: str, summary: str | None) -> str:
    basis = normalized_title(title) + "\n" + (summary or "")[:1000]
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()
