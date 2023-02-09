def bold(unformatted: str, should_bold: bool = True) -> str:
    return f"**{unformatted}**" if should_bold else unformatted


__all__ = ["bold"]
