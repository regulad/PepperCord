"""Scores, games, standings and news from ESPN, for every league it covers, and league watches that post each game in a
channel with its updates in a thread under it."""

from asyncio import Semaphore, TaskGroup
from datetime import date
from logging import getLogger
from operator import attrgetter
from time import monotonic
from typing import cast

from aioespn import ESPNClient, Event, League, Scoreboard, Sport, State, Summary
from aiohttp import ClientError, ClientResponseError
from discord import AllowedMentions, Embed, Interaction, Member, Role, TextChannel
from discord.app_commands import Choice, autocomplete, describe
from discord.ext import tasks
from discord.ext.commands import Cog, hybrid_group, parameter

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext
from utils.commands import UserFacingError
from utils.sports import (
    CREDIT_EMOJI,
    RESULT_SPORTS,
    Directory,
    credit,
    event_choice,
    game_embed,
    news_embed,
    parse_key,
    scoreboard_embed,
    standings_embed,
)
from utils.sports_watch import LeagueWatcher

logger = getLogger(__name__)

USER_AGENT = "PepperCord/10.0 (+https://github.com/regulad/PepperCord)"

CACHE_SECONDS = 30
"""How long a scoreboard fetched for a command is reused, as when autocompleting a game. ESPN caches its own for 10."""

EVERY_LEAGUE = "all"


class Sports(Cog):
    """
    Scores, games, standings and news from ESPN, and watches that post each of a league's games in a channel.
    Data from ESPN.
    """

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot
        self.client = ESPNClient(user_agent=USER_AGENT)
        self.directory: Directory | None = None
        self.watcher = LeagueWatcher(bot, self.client, lambda: self.directory)
        self._boards: dict[str, tuple[float, Scoreboard]] = {}

    @tasks.loop(hours=24)
    async def refresh_directory(self) -> None:
        # Each sport is fetched on its own, and one that fails keeps its leagues from before.
        semaphore = Semaphore(4)
        old = self.directory.leagues if self.directory is not None else {}

        async def fetch(sport: Sport) -> dict[str, League]:
            async with semaphore:
                try:
                    leagues = await self.client.leagues(sport)
                except Exception:
                    logger.warning(
                        f"Couldn't fetch ESPN's {sport} leagues.", exc_info=True
                    )
                    return {
                        key: league
                        for key, league in old.items()
                        if key.startswith(f"{sport}/")
                    }
            return {f"{sport.value}/{league.slug}": league for league in leagues}

        async with TaskGroup() as group:
            tasks_by_sport = [group.create_task(fetch(sport)) for sport in Sport]
        leagues: dict[str, League] = {}
        for task in tasks_by_sport:
            leagues |= task.result()
        if leagues:
            self.directory = Directory(leagues)

    @Cog.listener()
    async def on_ready(self) -> None:
        # on_ready fires again after every new gateway session, and starting a running loop raises.
        if not self.refresh_directory.is_running():
            self.refresh_directory.start()
        self.watcher.start()

    async def cog_unload(self) -> None:
        if self.refresh_directory.is_running():
            self.refresh_directory.cancel()
        self.watcher.stop()
        await self.client.close()

    # Arguments.

    def league_key(self, text: str) -> str:
        """The key of the league ``text`` names, such as ``football/nfl``."""
        if self.directory is not None:
            return self.directory.resolve(text)
        if "/" in text:
            try:
                sport, slug = parse_key(text.casefold().strip())
            except ValueError:
                pass
            else:
                return f"{sport.value}/{slug}"
        raise UserFacingError(
            "I'm still loading ESPN's leagues. Try again in a minute, or name the league by its sport and slug, such as "
            "`football/nfl`."
        )

    def credited(self, embed: Embed) -> Embed:
        """The embed, with ESPN's icon beside its credit."""
        emoji = self.bot.get_custom_emoji(CREDIT_EMOJI)
        return credit(embed, emoji.url if emoji is not None else None)

    def league(self, key: str) -> League | None:
        return self.directory.league(key) if self.directory is not None else None

    async def scoreboard(self, key: str, day: date | None = None) -> Scoreboard:
        """The league's scoreboard, reusing one fetched in the last half minute."""
        cached = self._boards.get(key) if day is None else None
        if cached is not None and monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]
        sport, slug = parse_key(key)
        try:
            board = await self.client.scoreboard(sport, slug, dates=day)
        except ClientResponseError as error:
            if error.status in (400, 404):
                raise UserFacingError(f"ESPN has no scoreboard for `{key}`.")
            raise UserFacingError(
                "ESPN isn't answering right now. Try again in a minute."
            )
        except (ClientError, TimeoutError):
            raise UserFacingError(
                "ESPN isn't answering right now. Try again in a minute."
            )
        if day is None:
            self._boards[key] = (monotonic(), board)
        return board

    async def summary(self, key: str, event: Event) -> Summary | None:
        """The game's summary, or None where ESPN has none, as for golf, racing, MMA and tennis."""
        sport, slug = parse_key(key)
        status = event.current_status
        if (
            sport in RESULT_SPORTS
            or sport is Sport.GOLF
            or status is None
            or status.state is State.PRE
        ):
            return None
        try:
            return await self.client.summary(sport, slug, event.id)
        except (ClientError, TimeoutError):
            logger.warning(
                f"Couldn't fetch ESPN's summary of {key} game {event.id}.",
                exc_info=True,
            )
            return None

    @staticmethod
    def find_event(board: Scoreboard, text: str) -> Event:
        if (event := board.event(text.strip())) is not None:
            return event
        wanted = text.casefold().strip()
        matches = [
            e for e in board.events if wanted in f"{e.name} {e.short_name}".casefold()
        ]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise UserFacingError(f"No game on the scoreboard matches `{text}`.")
        options = ", ".join(f"`{e.short_name}`" for e in matches[:5])
        raise UserFacingError(f"Which game? `{text}` could be {options}.")

    async def league_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[Choice[str]]:
        if self.directory is None:
            return []
        return [
            Choice(name=self.directory.label(key), value=key)
            for key in self.directory.search(current)
        ]

    async def watched_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[Choice[str]]:
        choices = [Choice(name="Every league", value=EVERY_LEAGUE)]
        if interaction.guild is not None:
            document = await self.bot.get_guild_document(interaction.guild)
            watched = sorted(
                {
                    key
                    for w in await self.watcher.store.in_document(document)
                    for key in w.leagues
                }
            )
            for key in watched:
                name = self.directory.label(key) if self.directory is not None else key
                choices.append(Choice(name=name, value=key))
        wanted = current.casefold().strip()
        return [
            choice
            for choice in choices
            if wanted in choice.name.casefold() or wanted in choice.value
        ][:25]

    async def game_autocomplete(
        self, interaction: Interaction, current: str
    ) -> list[Choice[str]]:
        league = getattr(interaction.namespace, "league", None)
        if not isinstance(league, str) or not league:
            return []
        try:
            board = await self.scoreboard(self.league_key(league))
        except UserFacingError:
            return []
        wanted = current.casefold().strip()
        return [
            Choice(name=event_choice(event), value=event.id)
            for event in board.events
            if wanted in f"{event.name} {event.short_name}".casefold()
        ][:25]

    # Commands.

    @hybrid_group(aliases=["espn"], fallback="scores")  # type: ignore[arg-type]  # bad d.py export
    @describe(
        league="The league, such as NFL or Premier League.",
        day="A day, as YYYY-MM-DD. Without one, ESPN's current day or week.",
    )
    @autocomplete(league=league_autocomplete)
    async def sports(
        self, ctx: CustomContext, league: str, day: str | None = None
    ) -> None:
        """
        Get a league's games and scores.
        Data from ESPN.
        """
        key = self.league_key(league)
        when = None
        if day is not None:
            try:
                when = date.fromisoformat(day.strip())
            except ValueError:
                raise UserFacingError(
                    f"`{day}` isn't a day. Give one as YYYY-MM-DD, such as `2026-11-16`."
                )
        async with ctx.typing():
            board = await self.scoreboard(key, when)
            await ctx.send(
                embed=self.credited(
                    scoreboard_embed(parse_key(key)[0], board, self.league(key), key)
                )
            )

    @sports.command()  # type: ignore[arg-type]  # bad d.py export
    @describe(
        league="The league, such as NFL or Premier League.",
        game="The game, from the league's current scoreboard.",
    )
    @autocomplete(league=league_autocomplete, game=game_autocomplete)
    async def game(self, ctx: CustomContext, league: str, *, game: str) -> None:
        """
        Get a game's score, line score and scoring plays, or a tournament's results.
        Data from ESPN.
        """
        key = self.league_key(league)
        async with ctx.typing():
            board = await self.scoreboard(key)
            event = self.find_event(board, game)
            summary = await self.summary(key, event)
            sport, slug = parse_key(key)
            await ctx.send(
                embed=self.credited(
                    game_embed(sport, slug, event, summary, self.league(key))
                )
            )

    @sports.command()  # type: ignore[arg-type]  # bad d.py export
    @describe(league="The league, such as NFL or Premier League.")
    @autocomplete(league=league_autocomplete)
    async def standings(self, ctx: CustomContext, *, league: str) -> None:
        """
        Get a league's standings.
        Data from ESPN.
        """
        key = self.league_key(league)
        sport, slug = parse_key(key)
        async with ctx.typing():
            try:
                standings = await self.client.standings(sport, slug)
            except ClientResponseError as error:
                if error.status in (400, 404):
                    raise UserFacingError(f"ESPN has no standings for `{key}`.")
                raise UserFacingError(
                    "ESPN isn't answering right now. Try again in a minute."
                )
            except (ClientError, TimeoutError):
                raise UserFacingError(
                    "ESPN isn't answering right now. Try again in a minute."
                )
            await ctx.send(
                embed=self.credited(standings_embed(standings, self.league(key), key))
            )

    @sports.command()  # type: ignore[arg-type]  # bad d.py export
    @describe(league="The league, such as NFL or Premier League.")
    @autocomplete(league=league_autocomplete)
    async def news(self, ctx: CustomContext, *, league: str) -> None:
        """
        Get a league's latest news.
        Data from ESPN.
        """
        key = self.league_key(league)
        sport, slug = parse_key(key)
        async with ctx.typing():
            try:
                news = await self.client.news(sport, slug)
            except ClientResponseError as error:
                if error.status in (400, 404):
                    raise UserFacingError(f"ESPN has no news for `{key}`.")
                raise UserFacingError(
                    "ESPN isn't answering right now. Try again in a minute."
                )
            except (ClientError, TimeoutError):
                raise UserFacingError(
                    "ESPN isn't answering right now. Try again in a minute."
                )
            await ctx.send(embed=self.credited(news_embed(news, self.league(key), key)))

    # Watches.

    @staticmethod
    def watched_channel(ctx: CustomContext, channel: TextChannel) -> TextChannel:
        """The channel to change the watch of, if the author may."""
        if ctx.guild is None:
            raise UserFacingError(
                "League watches post each game's updates in a thread under it, which only a server's channels have."
            )
        if not isinstance(channel, TextChannel) or channel.guild != ctx.guild:
            raise UserFacingError("Pick a text channel in this server.")
        if not channel.permissions_for(cast(Member, ctx.author)).manage_channels:
            raise UserFacingError(
                f"You need the Manage Channels permission in {channel.mention} to change what it watches."
            )
        return channel

    @sports.group(name="watch")  # type: ignore[arg-type]  # bad d.py export
    async def watch(self, ctx: CustomContext) -> None:
        """
        Post each of a league's games in a channel, with its updates in a thread under it.
        Data from ESPN.
        """
        if ctx.invoked_subcommand is None:
            await self.list_watches(ctx)

    @watch.command(name="add")  # type: ignore[arg-type]  # bad d.py export
    @describe(
        league="The league, such as NFL or Premier League.",
        channel="The channel to post in, if not this one.",
        role="A role to mention with each game.",
    )
    @autocomplete(league=league_autocomplete)
    async def watch_add(
        self,
        ctx: CustomContext,
        league: str,
        channel: TextChannel = parameter(
            default=attrgetter("channel"), displayed_default="this channel"
        ),
        role: Role | None = None,
    ) -> None:
        """Post each of a league's games in a channel, with its score updates in a thread under it."""
        channel = self.watched_channel(ctx, channel)
        key = self.league_key(league)
        mine = channel.permissions_for(channel.guild.me)
        missing = [
            name
            for name, allowed in (
                ("Send Messages", mine.send_messages),
                ("Embed Links", mine.embed_links),
                ("Create Public Threads", mine.create_public_threads),
                ("Send Messages in Threads", mine.send_messages_in_threads),
            )
            if not allowed
        ]
        if missing:
            raise UserFacingError(
                f"I need {', '.join(missing)} in {channel.mention} to post there."
            )
        if role is not None and not (role.mentionable or mine.mention_everyone):
            raise UserFacingError(
                f"I can't mention {role.mention} in {channel.mention}: make the role mentionable, or let me mention "
                "everyone there."
            )
        # A league that ESPN has no scoreboard for would never post anything.
        await self.scoreboard(key)
        await self.watcher.store.add(
            ctx["guild_document"],
            channel.id,
            key,
            role.id if role is not None else None,
        )
        name = self.directory.name(key) if self.directory is not None else key
        await ctx.send(
            f"Posting each {name} game in {channel.mention} an hour before it starts, with its score updates in a "
            "thread under it.",
            ephemeral=True,
        )

    @watch.command(name="remove")  # type: ignore[arg-type]  # bad d.py export
    @describe(
        league="The league to stop posting, or every league.",
        channel="The channel to stop posting in, if not this one.",
    )
    @autocomplete(league=watched_autocomplete)
    async def watch_remove(
        self,
        ctx: CustomContext,
        league: str,
        channel: TextChannel = parameter(
            default=attrgetter("channel"), displayed_default="this channel"
        ),
    ) -> None:
        """Stop posting a league's games in a channel."""
        channel = self.watched_channel(ctx, channel)
        key = (
            None
            if league.casefold().strip() in (EVERY_LEAGUE, "every league")
            else self.league_key(league)
        )
        if not await self.watcher.store.remove(ctx["guild_document"], channel.id, key):
            raise UserFacingError(
                f"Nothing to stop: {channel.mention} isn't watching that."
            )
        what = (
            "any league's"
            if key is None
            else (self.directory.name(key) if self.directory else key)
        )
        await ctx.send(
            f"Stopped posting {what} games in {channel.mention}.", ephemeral=True
        )

    @watch.command(name="list")  # type: ignore[arg-type]  # bad d.py export
    async def watch_list(self, ctx: CustomContext) -> None:
        """List the leagues this server's channels watch."""
        await self.list_watches(ctx)

    async def list_watches(self, ctx: CustomContext) -> None:
        if ctx.guild is None:
            raise UserFacingError(
                "League watches are kept per server: list them in one."
            )
        lines = []
        for watch in sorted(
            await self.watcher.store.in_document(ctx["guild_document"]),
            key=attrgetter("channel_id"),
        ):
            channel = ctx.guild.get_channel(watch.channel_id)
            names = sorted(
                self.directory.name(key) if self.directory else key
                for key in watch.leagues
            )
            line = f"{channel.mention if channel else 'A deleted channel'}: {', '.join(names)}"
            role = (
                ctx.guild.get_role(watch.role_id) if watch.role_id is not None else None
            )
            if role is not None:
                line += f", mentioning {role.mention}"
            if watch.paused:
                line += ". **Paused**: I wasn't allowed to post or open threads there. Add a league again to resume."
            lines.append(line)
        embed = Embed(
            title="League watches",
            description="\n".join(lines) or "Nothing is watched here.",
        )
        embed.set_footer(
            text="Each game is posted an hour before it starts, and its updates go in a thread under it."
        )
        await ctx.send(
            embed=embed, ephemeral=True, allowed_mentions=AllowedMentions.none()
        )


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Sports(bot))
