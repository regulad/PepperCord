from datetime import UTC, datetime, timedelta
from io import BytesIO
from os.path import exists
from pathlib import Path
from typing import Any, cast

import pytest
from aiohttp import ClientSession

# The library's feed envelopes are private: the client unwraps them. These tests read its snapshots directly.
from aiosplatoon3ink import Festivals
from aiosplatoon3ink.gear import _CoopFeed, _GearFeed
from aiosplatoon3ink.schedules import _SchedulesFeed
from PIL import Image

from extensions.external.splatoon3 import TOPICS, Splatoon3, Splatoon3Watch
from utils.bots.bot import CustomBot

FIXTURES = Path(__file__).parent / "fixtures" / "splatoon3"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class FakeBot:
    loop: Any = None

    def get_custom_emoji(self, name: str) -> None:
        return None


def splatoon(schedules: str = "schedules.json") -> Splatoon3:
    cog = Splatoon3(cast(CustomBot, FakeBot()))
    cog.schedules = _SchedulesFeed.model_validate_json(fixture(schedules)).data
    cog.festivals = Festivals.model_validate_json(fixture("festivals.json"))
    cog.monthly_gear = _CoopFeed.model_validate_json(
        fixture("coop.json")
    ).data.coop_result.monthly_gear
    cog.gear = _GearFeed.model_validate_json(fixture("gear.json")).data.gesotown
    return cog


def due(watch: Splatoon3Watch, now: datetime) -> list[str]:
    return sorted(event.key for event in watch.events(now) if event.is_due(now))


def test_topics_fit_discords_choices() -> None:
    assert len(TOPICS) <= 25
    assert all(
        len(topic) <= 100 and 1 <= len(description) <= 100
        for topic, description in TOPICS.items()
    )


def test_a_day_without_a_splatfest() -> None:
    watch = Splatoon3Watch(splatoon())

    assert due(watch, datetime(2026, 11, 16, 9, tzinfo=UTC)) == [
        "anarchy-open:2026-11-16T08:00:00+00:00",
        "anarchy-series:2026-11-16T08:00:00+00:00",
        "challenge:SpecialRush_UltraStamp:2026-11-19T02:00:00+00:00:announced",
        "challenge:SuperSubWeapon_SplashBomb:2026-11-26T02:00:00+00:00:announced",
        "gear:brand:QnJhbmQtNg==:2026-11-17T00:00:00+00:00",
        "gear:monthly:70985cc8ba0a905e",
        "regular:2026-11-16T08:00:00+00:00",
        "salmon-run:salmon-run:2026-11-16T08:00:00+00:00",
        "x:2026-11-16T08:00:00+00:00",
    ]


def test_rotations_are_posted_until_two_hours_after_they_start_or_they_end() -> None:
    watch = Splatoon3Watch(splatoon())

    assert "x:2026-11-16T08:00:00+00:00" in due(
        watch, datetime(2026, 11, 16, 9, 59, tzinfo=UTC)
    )
    assert "x:2026-11-16T08:00:00+00:00" not in due(
        watch, datetime(2026, 11, 16, 10, tzinfo=UTC)
    )
    assert "x:2026-11-16T10:00:00+00:00" in due(
        watch, datetime(2026, 11, 16, 10, tzinfo=UTC)
    )


def test_challenge_periods() -> None:
    watch = Splatoon3Watch(splatoon())
    ident = "challenge:SpecialRush_UltraStamp:2026-11-19T02:00:00+00:00"

    during = due(watch, datetime(2026, 11, 19, 6, 30, tzinfo=UTC))
    assert f"{ident}:2026-11-19T06:00:00+00:00" in during
    assert (
        f"{ident}:announced" not in during
    )  # once it's on, its announcement is old news
    assert not any(
        key.startswith(ident)
        for key in due(watch, datetime(2026, 11, 19, 8, 30, tzinfo=UTC))
    )


def test_a_splatfest_from_announcement_to_results() -> None:
    watch = Splatoon3Watch(splatoon())
    ident = "splatfest:JUEA-00108"  # 2026-10-31 to 2026-11-02

    # The snapshot was taken after this Splatfest's results came in, so they're due throughout; each step checks for
    # its own event.
    assert f"{ident}:announced" in due(watch, datetime(2026, 10, 25, tzinfo=UTC))
    started = due(watch, datetime(2026, 10, 31, 1, tzinfo=UTC))
    assert f"{ident}:started" in started and f"{ident}:announced" not in started
    second_half = due(watch, datetime(2026, 11, 1, 0, 30, tzinfo=UTC))
    assert (
        f"{ident}:second-half" in second_half and f"{ident}:started" not in second_half
    )
    assert f"{ident}:results" in due(watch, datetime(2026, 11, 3, 12, tzinfo=UTC))
    assert not any(
        key.startswith("splatfest:")
        for key in due(watch, datetime(2026, 11, 6, tzinfo=UTC))
    )


def test_splatfest_battles_replace_the_other_modes() -> None:
    keys = due(
        Splatoon3Watch(splatoon("schedules-splatfest.json")),
        datetime(2026, 1, 10, 22, 30, tzinfo=UTC),
    )

    assert "splatfest-open:2026-01-10T22:00:00+00:00" in keys
    assert "splatfest-pro:2026-01-10T22:00:00+00:00" in keys
    assert not any(key.startswith(("regular:", "anarchy-", "x:")) for key in keys)


def test_the_current_splatfest_gives_its_exact_second_half() -> None:
    watch = Splatoon3Watch(splatoon("schedules-splatfest.json"))

    assert "splatfest:JUEA-00105:second-half" in due(
        watch, datetime(2026, 1, 11, 0, 30, tzinfo=UTC)
    )


def test_big_runs_and_eggstra_work_are_announced_and_started() -> None:
    big_run = Splatoon3Watch(splatoon("schedules-big-run.json"))
    ident = "salmon-run:big-run:2025-06-14T00:00:00+00:00"

    assert f"{ident}:announced" in due(big_run, datetime(2025, 6, 13, 12, tzinfo=UTC))
    assert ident in due(big_run, datetime(2025, 6, 14, 0, 30, tzinfo=UTC))

    eggstra_work = Splatoon3Watch(splatoon("schedules-eggstra-work.json"))
    assert "salmon-run:eggstra-work:2025-05-10T00:00:00+00:00:announced" in due(
        eggstra_work, datetime(2025, 5, 8, 5, tzinfo=UTC)
    )


def test_noticed_events_keep_the_time_they_were_first_noticed() -> None:
    watch = Splatoon3Watch(splatoon())
    now = datetime(2026, 11, 16, 9, tzinfo=UTC)
    key = "gear:brand:QnJhbmQtNg==:2026-11-17T00:00:00+00:00"

    first = next(event for event in watch.events(now) if event.key == key)
    later = next(
        event for event in watch.events(now + timedelta(hours=1)) if event.key == key
    )

    assert first.at == later.at == now
    assert later.expires == datetime(2026, 11, 17, tzinfo=UTC)


needs_resources = pytest.mark.skipif(
    not exists("resources/images/splatoon3/favicon.png"),
    reason="needs the private resources submodule, which CI doesn't check out",
)


class FakeResponse:
    def __init__(self, data: bytes) -> None:
        self.data = data

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def read(self) -> bytes:
        return self.data


class FakeSession:
    """Serves the same small PNG for every image, instead of fetching splatoon3.ink's."""

    closed = False

    def __init__(self) -> None:
        buffer = BytesIO()
        Image.new("RGBA", (8, 8)).save(buffer, "PNG")
        self.png = buffer.getvalue()

    def get(self, url: str) -> FakeResponse:
        return FakeResponse(self.png)


@needs_resources
async def test_renders_each_kind_of_update() -> None:
    import asyncio

    cog = splatoon()
    cast(Any, cog.bot).loop = asyncio.get_running_loop()
    cog.cs = cast(ClientSession, FakeSession())
    watch = Splatoon3Watch(cog)
    now = datetime(2026, 11, 16, 9, tzinfo=UTC)
    events = {event.key: event for event in watch.events(now)}

    rotation = await events["x:2026-11-16T08:00:00+00:00"].render()
    assert rotation.content == "A new X Battle rotation has started."
    assert [name for name, _ in rotation.files] == ["favicon.png", "stages.png"]

    challenge = await events[
        "challenge:SpecialRush_UltraStamp:2026-11-19T02:00:00+00:00:announced"
    ].render()
    assert challenge.content == "A new Challenge is coming: Ultra Stamp Rally."
    assert [field.name for field in challenge.embed.fields][-2:] == ["Times", "Rules"]

    brand = await events["gear:brand:QnJhbmQtNg==:2026-11-17T00:00:00+00:00"].render()
    assert brand.content == "SplatNet's brand of the day is Firefin."
    assert brand.embed.title == "Brand of the day: Firefin"

    salmon_run = await events[
        "salmon-run:salmon-run:2026-11-16T08:00:00+00:00"
    ].render()
    assert salmon_run.embed.title == "Salmon Run"

    results = await next(
        event
        for event in watch.events(datetime(2026, 11, 3, tzinfo=UTC))
        if event.key.endswith(":results")
    ).render()
    assert (
        results.content
        == "The results of What would you be in a fantasy world? are in!"
    )
    assert any("Votes" in (field.value or "") for field in results.embed.fields)
