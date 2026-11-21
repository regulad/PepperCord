from asyncio import Event
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from aiohttp import ClientConnectionError, ClientError
from discord import Emoji, Intents

from utils.bots import bot as bot_module
from utils.bots.bot import EMOJI_FETCH_ATTEMPTS, CustomBot


@pytest.fixture
def bot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CustomBot:
    # An empty resources/emojis, so the sync uploads nothing and only fetches.
    (tmp_path / "resources" / "emojis").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    return CustomBot(ddb=cast(Any, None), config={}, intents=Intents.none())


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Records the delays between attempts instead of waiting them out."""
    delays: list[float] = []

    async def record(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(bot_module, "sleep", record)
    return delays


async def test_a_stalled_emoji_fetch_is_cut_off_and_tried_again(
    bot: CustomBot, sleeps: list[float], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bot_module, "EMOJI_FETCH_TIMEOUT", 0.01)
    emoji = cast(Emoji, SimpleNamespace(name="checkmark"))
    calls = 0

    async def fetch() -> list[Emoji]:
        nonlocal calls
        calls += 1
        if calls == 1:
            await Event().wait()  # a response that never comes
        return [emoji]

    monkeypatch.setattr(bot, "fetch_application_emojis", fetch)

    await bot.sync_application_emojis()

    assert calls == 2
    assert sleeps == [2]
    assert bot.get_custom_emoji("checkmark.png") is emoji


async def test_the_emoji_fetch_gives_up_after_its_attempts(
    bot: CustomBot, sleeps: list[float], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    async def fetch() -> list[Emoji]:
        nonlocal calls
        calls += 1
        raise ClientConnectionError()

    monkeypatch.setattr(bot, "fetch_application_emojis", fetch)

    with pytest.raises(ClientError):
        await bot.sync_application_emojis()

    assert calls == EMOJI_FETCH_ATTEMPTS
    assert sleeps == [2, 4, 8]
