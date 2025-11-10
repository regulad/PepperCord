from asyncio import get_event_loop, AbstractEventLoop
from dataclasses import MISSING
import functools
from io import BytesIO
import operator
from typing import Any, Optional, Self, Type, cast

from discord import ButtonStyle, File, SelectOption, ui, Message
from PIL.Image import Image as ImageType
from discord import Embed, Guild, Interaction, Member, Message, User
from discord.user import BaseUser
from discord.app_commands import describe
from discord.ext import tasks
from discord.ext.commands import hybrid_group, guild_only, Cog, cooldown, BucketType

from discord.ext.menus import ListPageSource, MenuPages
from utils import bots, misc, checks
from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext
from utils.database import PCDocument
from .abstract import *
from .render import *


def fully_render(game_state: GameState) -> BytesIO:
    image: ImageType = render(game_state)
    return save_buffer(image, "PNG")


async def get_fazpoints(bot: CustomBot, user: Member | BaseUser) -> int:
    return cast(int, (await bot.get_user_document(user)).get("fazpoints", 0))


async def set_fazpoints(
    bot: CustomBot, user: Member | BaseUser, fazpoints: int
) -> None:
    doc: PCDocument = await bot.get_user_document(user)
    await doc.update_db({"$set": {"fazpoints": fazpoints}})


class LevelSource(
    ListPageSource[
        tuple[Member, int], MenuPages[CustomBot, CustomContext, "LevelSource"]
    ]
):
    def __init__(self, data: list[tuple[Member, int]], guild: Guild) -> None:
        self.guild = guild
        super().__init__(data, per_page=10)

    async def format_page(
        self,
        menu: MenuPages[CustomBot, CustomContext, "LevelSource"],
        page_entries: list[tuple[Member, int]] | tuple[Member, int],
    ) -> Embed:
        assert isinstance(page_entries, list)  # asserted by per_page above
        offset = menu.current_page * self.per_page
        base_embed = Embed(title=f"{self.guild.name}'s Leaderboard")
        if self.guild.icon is not None:
            base_embed.set_thumbnail(url=self.guild.icon.url)
        base_embed.set_footer(
            text=f"Page {menu.current_page + 1}/{self.get_max_pages()}"
        )
        for iteration, value in enumerate(page_entries, start=offset):
            base_embed.add_field(
                name=f"{iteration + 1}: {value[0].display_name}",
                value=f"{value[-1]} fazpoints",
                inline=False,
            )
        return base_embed


class GameStateHolder:
    """
    This class represents a current, ongoing game.
    """

    def __init__(
        self,
        message: Message,
        bot: CustomBot,
        view: Optional[ui.View] = None,
        game_state: GameState = GameState.initialize(),
        invoker: Optional[Member | BaseUser] = None,
        initial_fazpoints: int = 0,
        *,
        loop: Optional[AbstractEventLoop] = None,
        debug_win: bool = False,
    ) -> None:
        self._current_view = view
        self.message = message
        self._bot = bot
        self._invoker = invoker
        self._game_state = game_state
        self._initial_fazpoints = initial_fazpoints
        self.loop = loop or get_event_loop()
        self._debug_win = debug_win
        self._closed = False

    @property
    def invoker(self) -> Optional[Member | BaseUser]:
        return self._invoker

    @property
    def game_state(self) -> GameState:
        return self._game_state

    @game_state.setter
    def game_state(self, game_state: GameState) -> None:
        self._game_state = game_state

    async def stop(self, delete_view: bool = True) -> None:
        if self._current_view is not None:
            self._current_view.stop()
        if delete_view:
            await self.message.edit(view=None)

    def new_view(self, interaction: Optional[Interaction] = None) -> Optional[ui.View]:
        """
        Generates a new view of the game's current state, linked into to this object.
        This operation is idempotent, as it merely wraps itself.
        When the current view suffices, no new view is created, and this function returns None.
        """
        target_view_type = (
            CameraSelectionView if self.game_state.camera_state.camera_up else OfficeGUI
        )
        if self._current_view is None or not isinstance(
            self._current_view, target_view_type
        ):
            return target_view_type(self)
        else:
            return None

    async def render(self) -> BytesIO:
        partial = functools.partial(fully_render, self.game_state)
        return await self.loop.run_in_executor(None, partial)

    async def on_update(self, interaction: Optional[Interaction] = None) -> None:
        """
        Runs once per tick, or in response to a stimuli.
        interaction will be None when called on the timer
        """
        if not self._closed:
            if self.game_state.power_left <= 0:
                self.game_state = self.game_state.process_input_changes(
                    camera_state=self.game_state.camera_state.change_position(False),
                    light_state=LightState.empty(),
                    door_state=DoorState.empty(),
                )
                await self.stop()

            message = (
                interaction.message if interaction is not None else None
            ) or self.message
            if self.game_state.won or self._debug_win:
                self._closed = True
                await message.edit(
                    content=f"You win! It is 6AM! "
                    f"You earned {self._initial_fazpoints} fazpoints, "
                    f"plus {self.game_state.fazpoints - self._initial_fazpoints} bonus fazpoints!",
                    view=None,
                    attachments=(File("resources/images/fnaf/end/Clock_6AM.gif"),),
                )
                await self.stop(delete_view=False)
                if self._invoker is not None:
                    await set_fazpoints(
                        self._bot,
                        self._invoker,
                        (await get_fazpoints(self._bot, self._invoker))
                        + self.game_state.fazpoints,
                    )
            elif self.game_state.lost:
                self._closed = True
                animatronics: list[Animatronic] = self.game_state.animatronics_in(
                    Room.OFFICE
                )
                killer: Animatronic = animatronics[-1]
                file_name: str
                match killer:
                    case Animatronic.FOXY:
                        file_name = "resources/images/fnaf/end/foxy.gif"
                    case Animatronic.FREDDY:
                        file_name = (
                            "resources/images/fnaf/end/freddy.gif"
                            if self.game_state.power_left <= 0
                            else "resources/images/fnaf/end/freddy1.gif"
                        )
                    case Animatronic.CHICA:
                        file_name = "resources/images/fnaf/end/chica.gif"
                    case Animatronic.BONNIE:
                        file_name = "resources/images/fnaf/end/bonnie.gif"
                    # case _:
                    #     file_name = "resources/fnaf/end/gfred.png"
                await message.edit(
                    content=f"You lose! You were killed by {killer.friendly_name}!",
                    view=None,
                    attachments=(File(file_name),),
                )
                await self.stop(delete_view=False)
            else:
                view_to_insert = (
                    (self.new_view(interaction) or MISSING)
                    if self.game_state.power_left > 0
                    else None
                )
                with await self.render() as fp:
                    # Behaves very weirdly when this isn't sent via a webhook.
                    await message.edit(
                        content="__**Five Nights At Freddy's**__",
                        view=view_to_insert,  # type: ignore[arg-type]  # d.py exports incorrectly, omitting MISSING
                        attachments=(File(fp, filename="game.png"),),
                    )


class OfficeGUI(ui.View):
    def __init__(self, game_state_holder: GameStateHolder) -> None:
        assert not game_state_holder.game_state.camera_state.camera_up

        self._game_state_holder: GameStateHolder = game_state_holder

        super().__init__()

    @ui.button(emoji="🟥")
    async def left_door_close(
        self, interaction: Interaction, button: ui.Button[Any]
    ) -> None:
        self._game_state_holder.game_state = (
            self._game_state_holder.game_state.process_input_changes(
                door_state=self._game_state_holder.game_state.door_state.change_left()
            )
        )
        await self._game_state_holder.on_update(interaction)
        await interaction.response.defer()

    @ui.button(emoji="⬜")
    async def left_door_light(
        self, interaction: Interaction, button: ui.Button[Any]
    ) -> None:
        self._game_state_holder.game_state = (
            self._game_state_holder.game_state.process_input_changes(
                light_state=self._game_state_holder.game_state.light_state.change_left()
            )
        )
        await self._game_state_holder.on_update(interaction)
        await interaction.response.defer()

    @ui.button(emoji="⏬", label="Open Cameras")
    async def open_cams(self, interaction: Interaction, button: ui.Button[Any]) -> None:
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            camera_state=self._game_state_holder.game_state.camera_state.change_position(
                True
            )
        )
        await self._game_state_holder.on_update(interaction)
        await interaction.response.defer()
        self.stop()

    @ui.button(emoji="⬜")
    async def right_door_light(
        self, interaction: Interaction, button: ui.Button[Any]
    ) -> None:
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            light_state=self._game_state_holder.game_state.light_state.change_right()
        )
        await self._game_state_holder.on_update(interaction)
        await interaction.response.defer()

    @ui.button(emoji="🟥")
    async def right_door_close(
        self, interaction: Interaction, button: ui.Button[Any]
    ) -> None:
        self._game_state_holder.game_state = (
            self._game_state_holder.game_state.process_input_changes(
                door_state=self._game_state_holder.game_state.door_state.change_right()
            )
        )
        await self._game_state_holder.on_update(interaction)
        await interaction.response.defer()


class CameraSelectionMenu(ui.Select["CameraSelectionView"]):
    def __init__(self, game_state_holder: GameStateHolder) -> None:
        assert game_state_holder.game_state.camera_state.camera_up

        options = [
            SelectOption(
                label=room.simple_name, description=room.room_name, emoji=room.emoji
            )
            for room in Room.cameras()
        ]

        self._game_state_holder: GameStateHolder = game_state_holder

        super().__init__(placeholder="Cameras", options=options)

    async def callback(self, interaction: Interaction) -> None:
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            camera_state=self._game_state_holder.game_state.camera_state.change_camera(
                Room.from_simple_name(self.values[0])
            )
        )
        await self._game_state_holder.on_update(interaction)


class CameraSelectionView(ui.View):
    def __init__(self, game_state_holder: GameStateHolder) -> None:
        assert game_state_holder.game_state.camera_state.camera_up

        self._game_state_holder: GameStateHolder = game_state_holder

        super().__init__()

        self.add_item(CameraSelectionMenu(game_state_holder))

    @ui.button(emoji="⏬", label="Exit", style=ButtonStyle.grey)
    async def on_exit(self, interaction: Interaction, button: ui.Button[Any]) -> None:
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            camera_state=self._game_state_holder.game_state.camera_state.change_position(
                False
            )
        )
        await self._game_state_holder.on_update(interaction)
        await interaction.response.defer()
        self.stop()


class FiveNightsAtFreddys(Cog):
    """Play Five Nights at Freddy's in Discord"""

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot
        self.games: list[GameStateHolder] = []
        self.update_games.start()

    def get_game(self, model: Member | BaseUser | Message) -> Optional[GameStateHolder]:
        for game in self.games:
            if (
                game.invoker is not None
                and not isinstance(model, Message)
                and game.invoker == model
            ) or (isinstance(model, Message) and game.message == model):
                return game
        else:
            return None

    @tasks.loop(seconds=5)  # Determines how many minutes the game will last
    async def update_games(self) -> None:
        for game in list(self.games):
            game.game_state = game.game_state.full_tick()
            await game.on_update()
            if game.game_state.done:
                await game.stop()
                self.games.remove(game)

    def cog_unload(self) -> None:  # type: ignore[override]  # it is compatible
        self.update_games.stop()

    @hybrid_group(fallback="start")  # type: ignore[arg-type]  # bad types in d.py
    @cooldown(1, 60, BucketType.channel)
    @describe(
        night="The night to simulate. Overrides all other options. "
        "To use custom settings, set to 7.",
        freddy="The difficulty for Freddy.",
        bonnie="The difficulty for Bonnie.",
        chica="The difficulty for Chica.",
        foxy="The difficulty for Foxy.",
    )
    async def fnaf(
        self,
        ctx: CustomContext,
        night: Optional[int] = 5,
        freddy: Optional[int] = Animatronic.FREDDY.default_diff,
        bonnie: Optional[int] = Animatronic.BONNIE.default_diff,
        chica: Optional[int] = Animatronic.CHICA.default_diff,
        foxy: Optional[int] = Animatronic.FOXY.default_diff,
    ) -> None:
        """Play a game of Five Nights at Freddy's!"""
        assert night is not None
        assert freddy is not None
        assert bonnie is not None
        assert chica is not None
        assert foxy is not None
        # informing mypy that Optional is merely an annotation
        result = self.get_game(ctx.author)
        if freddy == 1 and bonnie == 9 and chica == 8 and foxy == 7:
            # har har har har
            await ctx.send(file=File("resources/images/fnaf/end/gfred.png"))
            return
        if result is not None:
            if result.game_state.done:
                self.games.remove(result)
            else:
                await ctx.send("You have a game ongoing!", ephemeral=True)
                return
        async with ctx.typing():
            if night != 7:
                freddy = Animatronic.FREDDY.difficulty(night)
                bonnie = Animatronic.BONNIE.difficulty(night)
                chica = Animatronic.CHICA.difficulty(night)
                foxy = Animatronic.FOXY.difficulty(night)
            difficulty: AnimatronicDifficulty = AnimatronicDifficulty(
                night,
                misc.FrozenDict(
                    {
                        Animatronic.FREDDY: freddy,
                        Animatronic.BONNIE: bonnie,
                        Animatronic.CHICA: chica,
                        Animatronic.FOXY: foxy,
                    }
                ),
                night != 7,
            )
            initial_state: GameState = GameState.initialize(difficulty)
            response_message = await ctx.send(
                f"You will earn at least {initial_state.fazpoints} fazpoints for this game."
            )
        holder: GameStateHolder = GameStateHolder(
            response_message,
            ctx.bot,
            initial_fazpoints=initial_state.fazpoints,
            invoker=ctx.author,
            game_state=initial_state,
            loop=ctx.bot.loop,
        )
        self.games.append(holder)
        await holder.on_update()

    @fnaf.command()  # type: ignore[arg-type]  # bad type in d.py
    @describe(user="The user to get the fazpoints of. Defaults to you!")
    async def fazpoints(
        self,
        ctx: CustomContext,
        *,
        user: Optional[Member],
    ) -> None:
        """Get the fazpoints of a member."""
        async with ctx.typing():
            user_query = user or ctx.author
            embed = Embed(
                title=f"{user_query.display_name}'s Fazpoints",
                description=f"```{await get_fazpoints(ctx.bot, user_query)}```",
                color=user_query.color,
            )
            embed.set_thumbnail(url=user_query.display_avatar.url)
            await ctx.send(embed=embed)

    @fnaf.command()  # type: ignore[arg-type]  # d.py exports bad types
    @guild_only()
    async def fpleaderboard(self, ctx: CustomContext) -> None:
        """Displays the fazpoints all members of the server relative to each other."""
        assert ctx.guild is not None  # guaranteed by check
        async with ctx.typing():
            member_fazpoints: list[tuple[Member, int]] = []

            for member in ctx.guild.members[:500]:  # To prevent DB from exploding
                member_fazpoints.append((member, await get_fazpoints(ctx.bot, member)))

            source = LevelSource(
                sorted(member_fazpoints, key=operator.itemgetter(-1), reverse=True),
                ctx.guild,
            )
            menu: MenuPages[CustomBot, CustomContext, "LevelSource"] = MenuPages(
                source=source
            )

            await menu.start(ctx)


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(FiveNightsAtFreddys(bot))


__all__: list[str] = ["FiveNightsAtFreddys", "setup", "get_fazpoints", "set_fazpoints"]
