def duration_to_str(duration_strings: float) -> str:
    """Takes in a duration in seconds and returns a fancy string."""

    minutes, seconds = divmod(duration_strings, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    duration_strings = []

    if days == 1:
        duration_strings.append(f"{int(round(days))} day")
    elif days > 0:
        duration_strings.append(f"{int(round(days))} days")

    if hours == 1:
        duration_strings.append(f"{int(round(hours))} hour")
    elif hours > 0:
        duration_strings.append(f"{int(round(hours))} hours")

    if minutes == 1:
        duration_strings.append(f"{int(round(minutes))} minute")
    elif minutes > 0:
        duration_strings.append(f"{int(round(minutes))} minutes")

    if seconds == 1:
        duration_strings.append(f"{int(round(seconds))} second")
    elif seconds > 0 or len(duration_strings) == 0:
        duration_strings.append(f"{int(round(seconds))} seconds")

    return ", ".join(duration_strings)


__all__ = ["duration_to_str"]
