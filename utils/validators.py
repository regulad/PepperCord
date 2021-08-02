from urllib.parse import urlparse


def str_is_url(url: str) -> bool:
    """Validates that a string is a URL."""

    try:
        parsed = urlparse(url)
        return all([parsed.scheme, parsed.netloc])
    except ValueError:
        return False


__all__ = ["str_is_url"]
