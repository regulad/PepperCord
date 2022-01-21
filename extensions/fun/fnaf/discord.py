import functools
from asyncio import get_event_loop, AbstractEventLoop
from io import BytesIO
from typing import Optional, Type

import discord
from PIL.Image import Image as ImageType
from discord.ext import commands, tasks

from utils import bots, misc
from .abstract import *
from .render import *


def fully_render(game_state: GameState) -> BytesIO:
    image: ImageType = render(game_state)
    return save_buffer(image, "PNG")


class GameStateHolder:
    def __init__(
            self,
            message: discord.Message,
            scratch_channel: discord.TextChannel,
            bot: bots.BOT_TYPES,
            view: Optional[discord.ui.View] = None,
            game_state: GameState = GameState.initialize(),
            invoker: Optional[discord.abc.User] = None,
            *,
            loop: Optional[AbstractEventLoop] = None,
            debug_win: bool = False
    ) -> None:
        self._current_view: Optional[discord.ui.View] = view
        self._message: discord.Message = message
        self._bot: bots.BOT_TYPES = bot
        self._invoker: Optional[discord.abc.User] = invoker
        self._scratch_channel: discord.TextChannel = scratch_channel
        self._game_state: GameState = game_state
        self.loop: AbstractEventLoop = loop or get_event_loop()
        self._debug_win: bool = debug_win

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

    async def new_view(self, interaction: Optional[discord.Interaction] = None) -> Optional[discord.ui.View]:
        target_view_type: Type = CameraSelectionView if self.game_state.camera_state.camera_up else OfficeGUI
        if self._current_view is None or not isinstance(self._current_view, target_view_type):
            return target_view_type(self)
        else:
            return None

    async def render(self) -> BytesIO:
        partial: functools.partial = functools.partial(fully_render, self.game_state)
        return await self.loop.run_in_executor(None, partial)

    async def on_update(self, interaction: Optional[discord.Interaction] = None) -> None:
        if self.game_state.power_left <= 0:
            self.game_state = self.game_state.process_input_changes(
                camera_state=self.game_state.camera_state.change_position(False),
                light_state=LightState.empty(),
                door_state=DoorState.empty(),
            )
            await self.stop()

        message: discord.Message = self.message_of(interaction.message if interaction is not None else None)
        if self.game_state.won or self._debug_win:
            await message.edit(
                content="You win! It is 6AM!",
                view=None,
                file=discord.File("resources/images/fnaf/end/Clock_6AM.gif")
            )
            await self.stop(delete_view=False)
        elif self.game_state.lost:
            animatronics: list[Animatronic] = self.game_state.animatronics_in(Room.OFFICE)
            killer: Animatronic = animatronics[-1]
            match killer:
                case Animatronic.FOXY:
                    file_name: str = "resources/images/fnaf/end/foxy.gif"
                case Animatronic.FREDDY:
                    file_name: str = "resources/images/fnaf/end/freddy.gif" \
                                     if self.game_state.power_left <= 0 \
                                     else "resources/images/fnaf/end/freddy1.gif"
                case Animatronic.CHICA:
                    file_name: str = "resources/images/fnaf/end/chica.gif"
                case Animatronic.BONNIE:
                    file_name: str = "resources/images/fnaf/end/bonnie.gif"
                case _:
                    file_name: str = "resources/fnaf/end/gfred.png"
            await message.edit(
                content=f"You lose! You were killed by {killer.friendly_name}!",
                view=None,
                file=discord.File(file_name)
            )
            await self.stop(delete_view=False)
        else:
            possible_view: discord.ui.View = await self.new_view(interaction) \
                if self.game_state.power_left > 0 \
                else None
            with await self.render() as fp:
                # Behaves very weirdly when this isn't sent via a webhook.
                await message.edit(
                    content="__**Five Nights At Freddy's**__",
                    view=possible_view if possible_view is not None else discord.utils.MISSING,
                    file=discord.File(fp, filename="game.png")
                )


class OfficeGUI(discord.ui.View):
    def __init__(self, game_state_holder: GameStateHolder) -> None:
        assert not game_state_holder.game_state.camera_state.camera_up

        self._game_state_holder: GameStateHolder = game_state_holder

        super().__init__()

    @discord.ui.button(emoji="🟥")
    async def left_door_close(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            door_state=self._game_state_holder.game_state.door_state.change_left()
        )
        await self._game_state_holder.on_update(interaction)

    @discord.ui.button(emoji="⬜")
    async def left_door_light(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            light_state=self._game_state_holder.game_state.light_state.change_left()
        )
        await self._game_state_holder.on_update(interaction)

    @discord.ui.button(emoji="⏬", label="Open Cameras")
    async def open_cams(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            camera_state=self._game_state_holder.game_state.camera_state.change_position(True)
        )
        await self._game_state_holder.on_update(interaction)
        self.stop()

    @discord.ui.button(emoji="⬜")
    async def right_door_light(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            light_state=self._game_state_holder.game_state.light_state.change_right()
        )
        await self._game_state_holder.on_update(interaction)

    @discord.ui.button(emoji="🟥")
    async def right_door_close(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            door_state=self._game_state_holder.game_state.door_state.change_right()
        )
        await self._game_state_holder.on_update(interaction)


class CameraSelectionMenu(discord.ui.Select):
    def __init__(self, game_state_holder: GameStateHolder) -> None:
        assert game_state_holder.game_state.camera_state.camera_up

        options: list[discord.SelectOption] = [
            discord.SelectOption(
                label=room.simple_name,
                description=room.room_name,
                emoji=room.emoji
            ) for
            room in
            Room.cameras()
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
    async def on_exit(self, button: discord.ui.Button, interaction: discord.Interaction):
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            camera_state=self._game_state_holder.game_state.camera_state.change_position(False)
        )
        await self._game_state_holder.on_update(interaction)
        self.stop()


class FiveNightsAtFreddys(commands.Cog):
    """Play Five Night's At Freddys in Discord"""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot: bots.BOT_TYPES = bot
        self.games: list[GameStateHolder] = []
        self.update_games.start()

    def get_game(self, model: discord.abc.User | discord.Message) \
            -> Optional[GameStateHolder]:
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

    @commands.command()
    @commands.cooldown(1, 60, commands.BucketType.channel)
    async def fnaf(
            self,
            ctx: bots.CustomContext,
            night: Optional[int] = commands.Option(
                description="The night to simulate. Overrides all other options. The default is 7, for custom night.",
                default=7,
            ),
            freddy: Optional[int] = commands.Option(
                description="The difficulty for Freddy.",
                default=Animatronic.FREDDY.default_diff
            ),
            bonnie: Optional[int] = commands.Option(
                description="The difficulty for Bonnie.",
                default=Animatronic.BONNIE.default_diff
            ),
            chica: Optional[int] = commands.Option(
                description="The difficulty for Chica.",
                default=Animatronic.CHICA.default_diff
            ),
            foxy: Optional[int] = commands.Option(
                description="The difficulty for Foxy.",
                default=Animatronic.FOXY.default_diff
            ),
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
                    Animatronic.FOXY: foxy
                }
            ),
            night != 7,
        )
        initial_state: GameState = GameState.initialize(difficulty)
        response_message: discord.abc.Message = await ctx.send(
            f"Freddy: {freddy}"
            f"\nBonnie: {bonnie}"
            f"\nChica: {chica}"
            f"\nFoxy: {foxy}"
        )
        holder: GameStateHolder = GameStateHolder(
            response_message,
            ctx.bot.scratch_channel,
            ctx.bot,
            game_state=initial_state,
            loop=ctx.bot.loop
        )
        self.games.append(holder)
        await holder.on_update()


def setup(bot: bots.BOT_TYPES) -> None:
    bot.add_cog(FiveNightsAtFreddys(bot))


__all__: list[str] = [
    "FiveNightsAtFreddys",
    "setup"
]
