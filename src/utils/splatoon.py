"""The parts of the Splatoon cogs that don't depend on the game: the menus under each schedule and Splatfest, and the
images stitched together from a feed's pictures."""

from asyncio import get_running_loop
from collections.abc import Awaitable, Callable, Iterable, Sequence
from datetime import datetime, tzinfo
from functools import reduce
from typing import Any, Protocol, cast

from aiohttp import ClientSession
from discord import Emoji, Interaction, Message, SelectOption
from discord.ui import Select, View
from discord.utils import get
from pytz import UTC

from utils.bots.context import CustomContext
from utils.consts import TIME_EMOJIS
from utils.images import hrz_concat_pngs, vrt_concat_pngs
from utils.misc import edit_with_files_send_wrapper

TIMESLOT_LONG: str = "%m/%d"
TIMESLOT_SHORT: str = "%I:%M %p"
TIMESLOT_TZ: str = "%Z"

SPLATFEST_LONG: str = "%m/%d/%y"


class Period(Protocol):
    """Anything with a start and an end, such as a rotation."""

    @property
    def start_time(self) -> datetime: ...

    @property
    def end_time(self) -> datetime: ...


class SplatoonCog(Protocol):
    """What the menus need from the cog whose schedules and Splatfests they page through."""

    @property
    def modes(self) -> Sequence[str]:
        """The modes the mode menu offers, in order."""
        ...

    def mode_emoji(self, mode: str) -> Emoji | None: ...

    def splatfest_emoji(self) -> Emoji | None: ...

    async def send_schedule(
        self,
        ctx: CustomContext,
        mode: Any,
        index: int,
        send: Callable[..., Awaitable[Message]],
    ) -> Message:
        """Send the rotation at ``index`` of ``mode``, which is always one of ``modes``."""
        ...

    async def send_splatfest(
        self,
        ctx: CustomContext,
        current: bool,
        index: int,
        region: Any,
        send: Callable[..., Awaitable[Message]],
    ) -> Message:
        """Send the Splatfest at ``index`` in ``region``, which is always a region the cog made a SplatfestView for."""
        ...


def _edit_response(
    ctx: CustomContext,
) -> Callable[..., Awaitable[Message]]:
    return lambda *args, **kwargs: edit_with_files_send_wrapper(
        ctx["response"].edit, *args, **kwargs
    )


class TimeSlotData:  # This could probably extend SelectOption, but this is separate for the sake of selfbot support.
    def __init__(self, start: datetime, end: datetime, index: int, mode: str) -> None:
        self.start: datetime = start
        self.end: datetime = end
        self.index: int = index
        self.mode: str = mode

    @classmethod
    def from_nodes(
        cls,
        nodes: Sequence[Period],
        mode: str,
    ) -> list["TimeSlotData"]:
        return [
            cls(node.start_time, node.end_time, index, mode)
            for index, node in enumerate(nodes)
        ]

    __slots__ = ("start", "end", "index", "mode")

    @property
    def name(self) -> str:
        now: datetime = datetime.now()
        ctz: tzinfo = now.tzinfo or UTC
        return (
            f"{self.start.astimezone(ctz).strftime(TIMESLOT_SHORT)} "
            f"- {self.end.astimezone(ctz).strftime(TIMESLOT_SHORT)} "
            f"({self.index + 1})"
        )

    @property
    def description(self) -> str:
        now: datetime = datetime.now()
        ctz: tzinfo = now.tzinfo or UTC
        now = now.astimezone(ctz)  # weird.
        return (
            f"{self.start.astimezone(ctz).strftime(TIMESLOT_LONG)} "
            f"- {self.end.astimezone(ctz).strftime(TIMESLOT_LONG)} "
            f"({now.strftime(TIMESLOT_TZ)})"
        )

    @property
    def emoji(self) -> str:
        now: datetime = datetime.now()
        ctz: tzinfo = now.tzinfo or UTC
        localized_start: datetime = self.start.astimezone(ctz)

        hour_str: str = localized_start.strftime("%I")
        hour: int = int(hour_str)

        while hour > 11:
            hour -= 12

        return TIME_EMOJIS[hour]

    def __repr__(self) -> str:
        return f"<TimeSlotData start={self.start} end={self.end} index={self.index}>"


class SplatfestData:  # Same deal as above with SelectOption
    def __init__(self, name: str, start: datetime, end: datetime, index: int) -> None:
        self.name: str = name
        self.start: datetime = start
        self.end: datetime = end
        self.index: int = index

    __slots__ = ("name", "start", "end", "index")

    @property
    def description(self) -> str:
        now: datetime = datetime.now()
        ctz: tzinfo = now.tzinfo or UTC
        now = now.astimezone(ctz)  # weird.
        return (
            f"{self.start.astimezone(ctz).strftime(SPLATFEST_LONG)} "
            f"- {self.end.astimezone(ctz).strftime(SPLATFEST_LONG)} "
            f"({now.strftime(TIMESLOT_TZ)})"
        )

    @classmethod
    def listing(
        cls, splatfests: Iterable[tuple[str, datetime, datetime]]
    ) -> list["SplatfestData"]:
        """List Splatfests, each given as its name, start and end, in the order the menu shows them."""
        return [
            cls(name, start, end, index)
            for index, (name, start, end) in enumerate(splatfests)
        ]


class ScheduleSelectionMenu(Select["ScheduleView"]):
    def __init__(
        self,
        cog: SplatoonCog,
        ctx: CustomContext,
        data: list[TimeSlotData],
        mode: str,
    ) -> None:
        self.cog = cog
        self.ctx: CustomContext = ctx
        self.data: list[TimeSlotData] = data
        self.game: str = mode

        options: list[SelectOption] = [
            SelectOption(
                label=timeslot.name,
                emoji=timeslot.emoji,
                description=timeslot.description,
            )
            for timeslot in data
        ]

        super().__init__(
            placeholder="Select Time Window...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()

        # Each option is named after one of self.data, and the user can't pick anything else.
        timeslot = cast(TimeSlotData, get(self.data, name=self.values[0]))

        await self.cog.send_schedule(
            self.ctx, self.game, timeslot.index, _edit_response(self.ctx)
        )


class ModeSelectionMenu(Select["ScheduleView"]):
    def __init__(self, cog: SplatoonCog, ctx: CustomContext) -> None:
        self.cog = cog
        self.ctx = ctx

        options: list[SelectOption] = [
            SelectOption(label=mode, emoji=cog.mode_emoji(mode)) for mode in cog.modes
        ]

        super().__init__(
            placeholder="Select Game Mode...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()

        await self.cog.send_schedule(
            self.ctx, self.values[0], 0, _edit_response(self.ctx)
        )


class SplatfestSelectionMenu(Select["SplatfestView"]):
    def __init__(
        self,
        cog: SplatoonCog,
        ctx: CustomContext,
        data: list[SplatfestData],
        region: str,
    ) -> None:
        self.cog = cog
        self.ctx: CustomContext = ctx
        self.data: list[SplatfestData] = data
        self.region: str = region

        options: list[SelectOption] = [
            SelectOption(
                label=splatfest.name,
                description=splatfest.description,
                emoji=cog.splatfest_emoji(),
            )
            # A select menu takes at most 25 options. The feeds list the newest first, and have more than 25.
            for splatfest in data[:25]
        ]

        super().__init__(
            placeholder="Select Splatfest...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()

        # Each option is named after one of self.data, and the user can't pick anything else.
        splatfest = cast(SplatfestData, get(self.data, name=self.values[0]))

        await self.cog.send_splatfest(
            self.ctx, False, splatfest.index, self.region, _edit_response(self.ctx)
        )


class ScheduleView(View):
    def __init__(
        self,
        cog: SplatoonCog,
        ctx: CustomContext,
        data: list[TimeSlotData],
        mode: str,
    ) -> None:
        self.ctx: CustomContext = ctx
        self.data: list[TimeSlotData] = data
        self.game: str = mode

        super().__init__()

        self.add_item(ScheduleSelectionMenu(cog, ctx, data, mode))
        self.add_item(ModeSelectionMenu(cog, ctx))


class SplatfestView(View):
    def __init__(
        self,
        cog: SplatoonCog,
        ctx: CustomContext,
        data: list[SplatfestData],
        region: str,
    ) -> None:
        self.ctx: CustomContext = ctx
        self.data: list[SplatfestData] = data
        self.game: str = region

        super().__init__()

        self.add_item(SplatfestSelectionMenu(cog, ctx, data, region))


async def _download(session: ClientSession, urls: Iterable[str]) -> list[bytes]:
    pngs: list[bytes] = []
    for url in urls:
        async with session.get(url) as resp:
            pngs.append(await resp.read())
    return pngs


async def stack_images(session: ClientSession, urls: Sequence[str]) -> bytes:
    """Download images and stack them top to bottom, each scaled to the first's width."""
    pngs = await _download(session, urls)
    return await get_running_loop().run_in_executor(None, reduce, vrt_concat_pngs, pngs)


async def tile_four_images(session: ClientSession, urls: Sequence[str]) -> bytes | None:
    """Download four images, such as Salmon Run's weapons, and tile them two by two. None unless there are four."""
    if len(urls) != 4:
        return None  # TODO(#156): Handle this case (probably for special weapons)
    pngs = await _download(session, urls)
    loop = get_running_loop()
    top: bytes = await loop.run_in_executor(None, hrz_concat_pngs, pngs[0], pngs[1])
    bottom: bytes = await loop.run_in_executor(None, hrz_concat_pngs, pngs[2], pngs[3])
    return await loop.run_in_executor(None, vrt_concat_pngs, top, bottom)


__all__ = [
    "ModeSelectionMenu",
    "Period",
    "ScheduleSelectionMenu",
    "ScheduleView",
    "SplatfestData",
    "SplatfestSelectionMenu",
    "SplatfestView",
    "SplatoonCog",
    "TimeSlotData",
    "stack_images",
    "tile_four_images",
]
