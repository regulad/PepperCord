import asyncio
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, cast

from aiohttp import ClientSession
from aiosplatoon2ink import CoopSchedules, Festivals, Region, Schedules, Timeline

# The shop feed's envelope is private: the client unwraps it. These tests read the library's snapshot directly.
from aiosplatoon2ink.gear import _MerchandisesFeed
from PIL import Image

from extensions.external.splatoon2 import TOPICS, Splatoon2, Splatoon2Watch
from utils.bots.bot import CustomBot

FIXTURES = Path(__file__).parent / "fixtures" / "splatoon2"
NOW = datetime(2026, 11, 16, 10, 30, tzinfo=UTC)


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class FakeBot:
    loop: Any = None

    def get_custom_emoji(self, name: str) -> None:
        return None


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
    """Serves the same small PNG for every image, instead of fetching splatoon2.ink's."""

    closed = False

    def __init__(self) -> None:
        buffer = BytesIO()
        Image.new("RGBA", (8, 8)).save(buffer, "PNG")
        self.png = buffer.getvalue()

    def get(self, url: str) -> FakeResponse:
        return FakeResponse(self.png)


def splatoon(coop: str = "coop-schedules.json") -> Splatoon2:
    cog = Splatoon2(cast(CustomBot, FakeBot()))
    cog.cs = cast(ClientSession, FakeSession())
    cog.schedules = Schedules.model_validate_json(fixture("schedules.json"))
    cog.salmon_run = CoopSchedules.model_validate_json(fixture(coop))
    cog.merchandises = _MerchandisesFeed.model_validate_json(
        fixture("merchandises.json")
    ).merchandises
    cog.festivals = Festivals.model_validate_json(fixture("festivals.json"))
    cog.timeline = Timeline.model_validate_json(fixture("timeline.json"))
    return cog


def due(watch: Splatoon2Watch, now: datetime) -> list[str]:
    return sorted(event.key for event in watch.events(now) if event.is_due(now))


def test_topics_fit_discords_choices() -> None:
    assert len(TOPICS) <= 25
    assert all(
        len(topic) <= 100 and 1 <= len(description) <= 100
        for topic, description in TOPICS.items()
    )


def test_watch_events() -> None:
    watch = Splatoon2Watch(splatoon())

    assert due(watch, NOW) == [
        "gear:item:15522297627952547280",
        "gear:item:15522297627952547281",
        "gear:item:15522297627952547282",
        "gear:item:15522297627952547283",
        "gear:item:15522297627952547284",
        "gear:item:15522297627952547285",
        "gear:reward:21005:2026-11-14T12:00:00+00:00",
        "league:2026-11-16T10:00:00+00:00",
        "ranked:2026-11-16T10:00:00+00:00",
        "regular:2026-11-16T10:00:00+00:00",
    ]
    # Each item leaves the watch's due list when it's off sale; Salmon Run's rotation starts at noon.
    later = due(watch, datetime(2026, 11, 16, 12, 30, tzinfo=UTC))
    assert "gear:item:15522297627952547280" not in later
    assert "salmon-run:2026-11-16T12:00:00+00:00" in later


async def test_renders_each_kind_of_update() -> None:
    cast(Any, FakeBot).loop = asyncio.get_running_loop()
    watch = Splatoon2Watch(splatoon())
    events = {
        event.key: event
        for event in watch.events(datetime(2026, 11, 16, 12, 30, tzinfo=UTC))
    }

    rotation = await events["regular:2026-11-16T12:00:00+00:00"].render()
    assert rotation.content == "A new Regular Battle rotation has started."
    assert [name for name, _ in rotation.files] == [
        "stages.png"
    ]  # and no favicon, which the resources lack

    salmon_run = await events["salmon-run:2026-11-16T12:00:00+00:00"].render()
    assert [field.value for field in salmon_run.embed.fields][3:] == [
        "Splash-o-matic",
        "Slosher",
        "Splat Brella",
        "Bamboozler 14 Mk I",
    ]
    assert [name for name, _ in salmon_run.files] == ["weapons.png"]

    reward = await events["gear:reward:21005:2026-11-14T12:00:00+00:00"].render()
    assert reward.content == "Salmon Run's reward gear is now North-Country Parka."


async def test_a_random_weapon_and_a_rotation_without_details() -> None:
    cast(Any, FakeBot).loop = asyncio.get_running_loop()
    cog = splatoon("coop-schedules-random-weapon.json")
    assert cog.salmon_run is not None
    first, *_, last = cog.salmon_run.schedules

    embed, _ = await cog.salmon_run_message(first, cog.salmon_run.detail(first))
    assert [field.value for field in embed.fields][-1] == "Random"

    embed, files = await cog.salmon_run_message(last, cog.salmon_run.detail(last))
    assert (
        embed.description
        == "Grizzco hasn't announced this rotation's stage and weapons yet."
    )
    assert files == []


async def test_splatfest_results_under_both_scorings() -> None:
    cog = splatoon()
    assert cog.festivals is not None
    newest, *_, first = cog.festivals.in_region(Region.NA)

    embed, _ = await cog.splatfest_message(newest)
    assert embed.title == "Super Mushroom vs. Super Star"
    lines = [
        line for field in embed.fields[3:] for line in (field.value or "").splitlines()
    ]
    assert any(line.startswith(("Normal:", "**Normal:")) for line in lines)
    assert not any("Solo" in line for line in lines)

    embed, _ = await cog.splatfest_message(first)
    lines = [
        line for field in embed.fields[3:] for line in (field.value or "").splitlines()
    ]
    assert any(line.startswith(("Solo:", "**Solo:")) for line in lines)
    assert not any("Normal" in line for line in lines)


async def test_gear() -> None:
    embed, _ = await splatoon().gear_message()

    assert len(embed.fields) == 6
    assert embed.fields[0].name == "Canary Trainers"
