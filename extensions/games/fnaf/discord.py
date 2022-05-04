import functools
import operator
from asyncio import get_event_loop, AbstractEventLoop
from io import BytesIO
from typing import Optional, Type

import discord
from PIL.Image import Image as ImageType
from discord import Interaction
from discord.app_commands import describe
from discord.ext import commands, tasks, menus
from discord.ext.commands import hybrid_group, guild_only
from discord.ui import Button

from utils import bots, misc
from utils.database import Document
from .abstract import *
from .render import *


def fully_render(game_state: GameState) -> BytesIO:
    image: ImageType = render(game_state)
    return save_buffer(image, "PNG")


async def get_fazpoints(bot: bots.BOT_TYPES, user: discord.abc.User) -> int:
    return (await bot.get_user_document(user)).get("fazpoints", 0)


async def set_fazpoints(
        bot: bots.BOT_TYPES, user: discord.abc.User, fazpoints: int
) -> None:
    doc: Document = await bot.get_user_document(user)
    await doc.update_db({"$set": {"fazpoints": fazpoints}})


class LevelSource(menus.ListPageSource):
    def __init__(
            self, data: list[tuple[discord.Member, int]], guild: discord.Guild
    ) -> None:
        self.guild = guild
        super().__init__(data, per_page=10)

    async def format_page(self, menu, page_entries):
        offset = menu.current_page * self.per_page
        base_embed: discord.Embed = discord.Embed(
            title=f"{self.guild.name}'s Leaderboard"
        )
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
    def __init__(
            self,
            message: discord.Message,
            bot: bots.BOT_TYPES,
            view: Optional[discord.ui.View] = None,
            game_state: GameState = GameState.initialize(),
            invoker: Optional[discord.abc.User] = None,
            initial_fazpoints: int = 0,
            *,
            loop: Optional[AbstractEventLoop] = None,
            debug_win: bool = False,
    ) -> None:
        self._current_view: Optional[discord.ui.View] = view
        self._message: discord.Message = message
        self._bot: bots.BOT_TYPES = bot
        self._invoker: Optional[discord.abc.User] = invoker
        self._game_state: GameState = game_state
        self._initial_fazpoints: int = initial_fazpoints
        self.loop: AbstractEventLoop = loop or get_event_loop()
        self._debug_win: bool = debug_win
        self._closed: bool = False

    @property
    def invoker(self) -> Optional[discord.abc.User]:
        return self._invoker

    @property
    def game_state(self) -> GameState:
        return self._game_state

    @game_state.setter
    def game_state(self, game_state: GameState) -> None:
        self._game_state = game_state

    def message_of(self, message: Optional[discord.Message] = None) -> discord.Message:
        return message or self._message

    async def stop(self, delete_view: bool = True) -> None:
        if self._current_view is not None:
            self._current_view.stop()
        if delete_view:
            await self._message.edit(view=None)

    async def new_view(
            self, interaction: Optional[discord.Interaction] = None
    ) -> Optional[discord.ui.View]:
        target_view_type: Type = (
            CameraSelectionView if self.game_state.camera_state.camera_up else OfficeGUI
        )
        if self._current_view is None or not isinstance(
                self._current_view, target_view_type
        ):
            return target_view_type(self)
        else:
            return None

    async def render(self) -> BytesIO:
        partial: functools.partial = functools.partial(fully_render, self.game_state)
        return await self.loop.run_in_executor(None, partial)

    async def on_update(
            self, interaction: Optional[discord.Interaction] = None
    ) -> None:
        if not self._closed:
            if self.game_state.power_left <= 0:
                self.game_state = self.game_state.process_input_changes(
                    camera_state=self.game_state.camera_state.change_position(False),
                    light_state=LightState.empty(),
                    door_state=DoorState.empty(),
                )
                await self.stop()

            message: discord.Message = self.message_of(
                interaction.message if interaction is not None else None
            )
            if self.game_state.won or self._debug_win:
                self._closed = True
                await message.edit(
                    content=f"You win! It is 6AM! "
                            f"You earned {self._initial_fazpoints} fazpoints, "
                            f"plus {self.game_state.fazpoints - self._initial_fazpoints} bonus fazpoints!",
                    view=None,
                    attachments=(
                        discord.File("resources/images/fnaf/end/Clock_6AM.gif"),
                    ),
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
                match killer:
                    case Animatronic.FOXY:
                        file_name: str = "resources/images/fnaf/end/foxy.gif"
                    case Animatronic.FREDDY:
                        file_name: str = (
                            "resources/images/fnaf/end/freddy.gif"
                            if self.game_state.power_left <= 0
                            else "resources/images/fnaf/end/freddy1.gif"
                        )
                    case Animatronic.CHICA:
                        file_name: str = "resources/images/fnaf/end/chica.gif"
                    case Animatronic.BONNIE:
                        file_name: str = "resources/images/fnaf/end/bonnie.gif"
                    case _:
                        file_name: str = "resources/fnaf/end/gfred.png"
                await message.edit(
                    content=f"You lose! You were killed by {killer.friendly_name}!",
                    view=None,
                    attachments=(discord.File(file_name),),
                )
                await self.stop(delete_view=False)
            else:
                possible_view: discord.ui.View = (
                    await self.new_view(interaction)
                    if self.game_state.power_left > 0
                    else None
                )
                with await self.render() as fp:
                    # Behaves very weirdly when this isn't sent via a webhook.
                    await message.edit(
                        content="__**Five Nights At Freddy's**__",
                        view=possible_view
                        if possible_view is not None
                        else discord.utils.MISSING,
                        attachments=(discord.File(fp, filename="game.png"),),
                    )


class OfficeGUI(discord.ui.View):
    def __init__(self, game_state_holder: GameStateHolder) -> None:
        assert not game_state_holder.game_state.camera_state.camera_up

        self._game_state_holder: GameStateHolder = game_state_holder

        super().__init__()

    @discord.ui.button(emoji="🟥")
    async def left_door_close(self, interaction: Interaction, button: Button) -> None:
        self._game_state_holder.game_state = (
            self._game_state_holder.game_state.process_input_changes(
                door_state=self._game_state_holder.game_state.door_state.change_left()
            )
        )
        await self._game_state_holder.on_update(interaction)
        await interaction.response.defer()

    @discord.ui.button(emoji="⬜")
    async def left_door_light(self, interaction: Interaction, button: Button) -> None:
        self._game_state_holder.game_state = (
            self._game_state_holder.game_state.process_input_changes(
                light_state=self._game_state_holder.game_state.light_state.change_left()
            )
        )
        await self._game_state_holder.on_update(interaction)
        await interaction.response.defer()

    @discord.ui.button(emoji="⏬", label="Open Cameras")
    async def open_cams(self, interaction: Interaction, button: Button) -> None:
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            camera_state=self._game_state_holder.game_state.camera_state.change_position(
                True
            )
        )
        await self._game_state_holder.on_update(interaction)
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(emoji="⬜")
    async def right_door_light(self, interaction: Interaction, button: Button) -> None:
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            light_state=self._game_state_holder.game_state.light_state.change_right()
        )
        await self._game_state_holder.on_update(interaction)
        await interaction.response.defer()

    @discord.ui.button(emoji="🟥")
    async def right_door_close(self, interaction: Interaction, button: Button) -> None:
        self._game_state_holder.game_state = (
            self._game_state_holder.game_state.process_input_changes(
                door_state=self._game_state_holder.game_state.door_state.change_right()
            )
        )
        await self._game_state_holder.on_update(interaction)
        await interaction.response.defer()


class CameraSelectionMenu(discord.ui.Select):
    def __init__(self, game_state_holder: GameStateHolder) -> None:
        assert game_state_holder.game_state.camera_state.camera_up

        options: list[discord.SelectOption] = [
            discord.SelectOption(
                label=room.simple_name, description=room.room_name, emoji=room.emoji
            )
            for room in Room.cameras()
        ]

        self._game_state_holder: GameStateHolder = game_state_holder

        super().__init__(placeholder="Cameras", options=options)

    async def callback(self, interaction: discord.Interaction):
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            camera_state=self._game_state_holder.game_state.camera_state.change_camera(
                Room.from_simple_name(self.values[0])
            )
        )
        await self._game_state_holder.on_update(interaction)


class CameraSelectionView(discord.ui.View):
    def __init__(self, game_state_holder: GameStateHolder) -> None:
        assert game_state_holder.game_state.camera_state.camera_up

        self._game_state_holder: GameStateHolder = game_state_holder

        super().__init__()

        self.add_item(CameraSelectionMenu(game_state_holder))

    @discord.ui.button(emoji="⏬", label="Exit", style=discord.ButtonStyle.grey)
    async def on_exit(
            self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            camera_state=self._game_state_holder.game_state.camera_state.change_position(
                False
            )
        )
        await self._game_state_holder.on_update(interaction)
        await interaction.response.defer()
        self.stop()


class FiveNightsAtFreddys(commands.Cog):
    """Play Five Night's At Freddys in Discord"""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot: bots.BOT_TYPES = bot
        self.games: list[GameStateHolder] = []
        self.update_games.start()

    def get_game(
            self, model: discord.abc.User | discord.Message
    ) -> Optional[GameStateHolder]:
        for game in self.games:
            if game.invoker.id == model.id or game.message_of(None).id == model.id:
                return game
        else:
            return None

    @tasks.loop(seconds=5)  # Determines how many minutes the game will last
    async def update_games(self):
        for game in list(self.games):
            game.game_state = game.game_state.full_tick()
            await game.on_update()
            if game.game_state.done:
                await game.stop()
                self.games.remove(game)

    def cog_unload(self) -> None:
        self.update_games.stop()

    @hybrid_group(fallback="start")
    @commands.cooldown(1, 60, commands.BucketType.channel)
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
            ctx: bots.CustomContext,
            night: Optional[int] = 5,
            freddy: Optional[int] = Animatronic.FREDDY.default_diff,
            bonnie: Optional[int] = Animatronic.BONNIE.default_diff,
            chica: Optional[int] = Animatronic.CHICA.default_diff,
            foxy: Optional[int] = Animatronic.FOXY.default_diff,
    ) -> None:
        """Play a game of Five Nights at Freddy's!"""
        result = self.get_game(ctx.author)
        if freddy == 1 and bonnie == 9 and chica == 8 and foxy == 7:
            await ctx.send(file=discord.File("resources/images/fnaf/end/gfred.png"))
            return
        if result is not None:
            if result.game_state.done:
                self.games.remove(result)
            else:
                await ctx.send("You have a game ongoing!", ephemeral=True)
                return
        await ctx.defer()
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
        response_message: discord.abc.Message = await ctx.send(
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

    @fnaf.command()
    @describe(user="The user to get the fazpoints of. Defaults to you!")
    async def fazpoints(
            self,
            ctx: bots.CustomContext,
            *,
            user: Optional[discord.Member],
    ) -> None:
        """Get the fazpoints of a member."""
        await ctx.defer()
        user: discord.Member = user or ctx.author
        embed: discord.Embed = discord.Embed(
            title=f"{user.display_name}'s Fazpoints",
            description=f"```{await get_fazpoints(ctx.bot, user)}```",
            color=user.color,
        )
        embed.set_thumbnail(
            url=(
                user.guild_avatar.url
                if user.guild_avatar is not None
                else user.avatar.url
            )
        )
        await ctx.send(embed=embed)

    @fnaf.command()
    @guild_only()
    async def fpleaderboard(self, ctx: bots.CustomContext) -> None:
        """Displays the fazpoints all members of the server relative to each other."""
        await ctx.defer()

        member_fazpoints: list[tuple[discord.Member, int]] = []

        for member in ctx.guild.members[:500]:  # To prevent DB from exploding
            member_fazpoints.append((member, await get_fazpoints(ctx.bot, member)))

        source = LevelSource(
            sorted(member_fazpoints, key=operator.itemgetter(-1), reverse=True),
            ctx.guild,
        )

        await menus.ViewMenuPages(source=source).start(ctx)


async def setup(bot: bots.BOT_TYPES) -> None:
    await bot.add_cog(FiveNightsAtFreddys(bot))


__all__: list[str] = ["FiveNightsAtFreddys", "setup", "get_fazpoints", "set_fazpoints"]
