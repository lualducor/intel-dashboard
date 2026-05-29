def is_paywalled(source_paywalled: bool) -> bool:
    return bool(source_paywalled)


def rewrite_link(url: str, prefix: str) -> str:
    if prefix:
        return f"{prefix}{url}"
    return url
