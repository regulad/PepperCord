import functools
from asyncio import get_event_loop, AbstractEventLoop
from io import BytesIO
from typing import Optional, Type

import discord
from PIL import Image
from discord.ext import commands, tasks

from utils import bots, misc
from .abstract import *
from .render import *


def fully_render(game_state: GameState) -> BytesIO:
    image: Image = render(game_state)
    return save_buffer(image, "PNG")


class GameStateHolder:
    def __init__(
            self,
            message: discord.Message,
            view: Optional[discord.ui.View] = None,
            game_state: GameState = GameState.initialize(),
            *,
            loop: Optional[AbstractEventLoop] = None
    ) -> None:
        self._current_view: Optional[discord.ui.View] = view
        self._message: discord.Message = message
        self._game_state: GameState = game_state
        self.loop: AbstractEventLoop = loop or get_event_loop()

    @property
    def game_state(self) -> GameState:
        return self._game_state

    @game_state.setter
    def game_state(self, game_state: GameState) -> None:
        self._game_state = game_state

    def message_of(self, message: Optional[discord.Message] = None) -> discord.Message:
        return message or self._message

    def stop(self) -> None:
        self._current_view.stop()

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
        """Override this method."""
        message: discord.Message = self.message_of(interaction.message if interaction is not None else None)
        if self.game_state.won:
            await message.edit(
                content="You win! It is 6AM!",
                view=None,
            )
            self.stop()
        elif self.game_state.lost:
            await message.edit(
                content=f"You lose! You were killed by "
                        f"{', '.join([animatronic.name.title() for animatronic in self.game_state.animatronics_in(Room.OFFICE)])}!",
                view=None,
            )
            self.stop()
        else:
            possible_view: discord.ui.View = await self.new_view(interaction)
            with await self.render() as fp:
                content: str = "__**Five Nights At Freddy's**__"
                await message.edit(
                    content=content,
                    view=possible_view if possible_view is not None else discord.utils.MISSING,
                    files=[discord.File(fp, filename="FNAF.png")],
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

    @discord.ui.button(emoji="⏬")
    async def open_cams(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            camera_state=self._game_state_holder.game_state.camera_state.change_position(True)
        )
        await self._game_state_holder.on_update(interaction)
        self.stop()

    @discord.ui.button(emoji="🟥")
    async def right_door_close(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            door_state=self._game_state_holder.game_state.door_state.change_right()
        )
        await self._game_state_holder.on_update(interaction)

    @discord.ui.button(emoji="⬜")
    async def right_door_light(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        self._game_state_holder.game_state = self._game_state_holder.game_state.process_input_changes(
            light_state=self._game_state_holder.game_state.light_state.change_right()
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

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.grey)
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
        self.games: dict[discord.Message, GameStateHolder] = {}

    async def get_game(self, model: discord.abc.User | discord.Message) \
            -> Optional[tuple[discord.Message, GameStateHolder]]:
        if isinstance(model, discord.Message):
            return self.games.get(model)
        else:
            for message, game in self.games.items():
                if message.author == model:
                    return message, game

    @tasks.loop(seconds=4)  # Determines how many minutes the game will last
    async def update_games(self):
        for message, game in self.games.items():
            game.game_state = game.game_state.full_tick()
            await game.on_update()

    @commands.command()
    async def fnaf(
            self,
            ctx: bots.CustomContext,
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
        result = await self.get_game(ctx.author)
        if result is not None:
            message, holder = result
            if holder.game_state.done:
                del self.games[message]
            else:
                await ctx.send("You have a game ongoing!", ephemeral=True)
                return
        await ctx.defer()
        difficulty: AnimatronicDifficulty = AnimatronicDifficulty(
            misc.FrozenDict(
                {
                    Animatronic.FREDDY: freddy,
                    Animatronic.BONNIE: bonnie,
                    Animatronic.CHICA: chica,
                    Animatronic.FOXY: foxy
                }
            )
        )
        initial_state: GameState = GameState.initialize(difficulty)
        response_message: discord.abc.Message = await ctx.send("Staring...")
        holder: GameStateHolder = GameStateHolder(response_message, game_state=initial_state, loop=ctx.bot.loop)
        self.games[response_message] = holder
        await holder.on_update()


def setup(bot: bots.BOT_TYPES) -> None:
    bot.add_cog(FiveNightsAtFreddys(bot))


__all__: list[str] = [
    "FiveNightsAtFreddys",
    "setup"
]
