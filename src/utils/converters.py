import datetime
from typing import Any, List, Dict, Optional

from discord.ext.commands import Converter, Context, BadArgument, CommandError


def duration_to_str(seconds: int) -> str:  # TODO: Make this take a timedelta.
    """Takes in a duration in seconds and returns a fancy string."""

    minutes, seconds = divmod(seconds, 60)
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


class TimedeltaShorthand(Converter[datetime.timedelta]):
    async def convert(self, ctx: Context[Any], argument: str) -> datetime.timedelta:
        try:
            return shorthand_to_timedelta(argument)
        except TypeError as exception:
            raise BadArgument(str(exception))
        except Exception as exception:
            raise CommandError(str(exception))


shorthands: List[str] = [
    "y",
    "mo",
    "w",
    "d",
    "h",
    "m",
    "s",
]


def shorthand_to_timedelta(shorthand: str) -> datetime.timedelta:
    """Shorthand:
    y: Years
    mo: Months
    w: Weeks
    d: Days
    h: Hours
    m: Minutes
    s: Seconds"""

    # Checks if a known unit of time is present in the shorthand.
    for possible_shorthand in shorthands:
        if possible_shorthand in shorthand:
            break
    else:
        raise TypeError("No unit of time in shorthand.")

    # Splits the shorthand up into smaller pieces.
    units: Dict[str, Optional[float]] = {
        "y": None,
        "mo": None,
        "w": None,
        "d": None,
        "h": None,
        "m": None,
        "s": None,
    }
    for possible_shorthand in shorthands:
        if len(shorthand) == 0:
            break
        if shorthand.find(possible_shorthand) != -1:
            index: int = shorthand.find(possible_shorthand)
            units[possible_shorthand] = float(shorthand[:index])
            shorthand = shorthand[index + 1 :]

    days: float = (units["y"] * 365 if units["y"] is not None else 0) + (
        units["mo"] * 30 if units["mo"] is not None else 0
    )

    return datetime.timedelta(
        weeks=units["w"] or 0,
        days=days + units["d"] if units["d"] is not None else days,  # Kinda stupid!
        hours=units["h"] or 0,
        minutes=units["m"] or 0,
        seconds=units["s"] or 0,
    )


__all__ = [
    "duration_to_str",
    "TimedeltaShorthand",
    "shorthand_to_timedelta",
]
