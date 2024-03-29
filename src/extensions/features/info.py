import platform
from asyncio import sleep
from sys import version
from typing import Union, Optional, cast

import discord
import psutil
from discord import Guild, Interaction, Member, User, AppCommandType
from discord.app_commands import describe, context_menu
from discord.app_commands import guild_only as ac_guild_only
from discord.ext import commands, tasks
from discord.ext.commands import hybrid_command

from utils import bots, checks
from utils.bots import CustomContext
from utils.misc import status_breakdown
from utils.version import get_version

WHOIS_CM_NAME: str = "Get User Information"


@context_menu(name=WHOIS_CM_NAME)
async def whois_cm(interaction: Interaction, user: Member | User) -> None:
    ctx = await CustomContext.from_interaction(interaction)
    info = cast(Info, ctx.bot.get_cog("Info"))
    await info.whois(ctx, user=user)


class Info(commands.Cog):
    """Get information about things here on Discord."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

    def cog_unload(self) -> None:
        if self.activity_update.is_running():
            self.activity_update.stop()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await sleep(10)
        self.activity_update.start()

    async def cog_load(self) -> None:
        self.bot.tree.add_command(whois_cm)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(WHOIS_CM_NAME, type=AppCommandType.user)

    @tasks.loop(seconds=600)
    async def activity_update(self) -> None:
        watching_string = f"with {self.bot.perceivable_users:n} {'user' if self.bot.perceivable_users == 1 else 'users'} in {len(self.bot.guilds):n} {'server' if len(self.bot.guilds) == 1 else 'servers'}"
        await self.bot.change_presence(activity=discord.Game(name=watching_string))

    @activity_update.before_loop
    async def before_activity_update(self) -> None:
        await self.bot.wait_until_ready()
        await sleep(10)  # Avoid disconnecting right away

    @hybrid_command()
    @commands.is_owner()
    @describe(activity="The status that the bot will change to.")
    async def status(
        self,
        ctx: bots.CustomContext,
        *,
        activity: Optional[str],
    ) -> None:
        """Sets the bot's status. If no status is specified, it will go back to the default."""
        task_is_running = self.activity_update.is_running()

        if activity is None and not task_is_running:
            self.activity_update.start()
        else:
            self.activity_update.cancel()
            watching_string = f"{activity}"
            await ctx.bot.change_presence(activity=discord.Game(name=watching_string))
        await ctx.send("Status updated.", ephemeral=True)

    @hybrid_command()
    @describe(
        user="The user that will have their info displayed. This can be any user, in or outside this server."
    )
    @checks.check_members_enabled
    @checks.check_presences_enabled
    async def whois(
        self,
        ctx: bots.CustomContext,
        *,
        user: Optional[Union[discord.Member, discord.User]],
    ) -> None:
        """Get information on you, a Member of this server, or any User of Discord."""
        async with ctx.typing(ephemeral=True):
            if not user:
                user = ctx.author
            embed = (
                discord.Embed(
                    colour=user.colour,
                    title=f"All about {user.name}#{user.discriminator}\n({user.id})",
                )
                .set_thumbnail(url=user.avatar.url)
                .add_field(name="Avatar URL:", value=f"[Click Here]({user.avatar.url})")
                .add_field(
                    name="Account creation date:",
                    value=f"<t:{user.created_at.timestamp():.0f}:R>",
                )
            )
            if isinstance(user, discord.Member):
                after_breakdown: str = status_breakdown(
                    user.desktop_status, user.mobile_status, user.web_status
                )
                embed = embed.insert_field_at(
                    0,
                    name="Status:",
                    value=f"{user.status}{f' ({after_breakdown})' if after_breakdown else ''}",
                )
                if user.name != user.display_name:
                    embed = embed.insert_field_at(
                        0, name="Nickname:", value=user.display_name
                    )
                embed = embed.add_field(
                    name="Server join date:",
                    value=f"<t:{user.joined_at.timestamp():.0f}:R>",
                )
                if user.premium_since:
                    embed = embed.add_field(
                        name="Server boosting since:",
                        value=f"<t:{user.premium_since.timestamp():.0f}:R>",
                    )
            await ctx.send(embed=embed, ephemeral=True)

    @hybrid_command()
    @commands.guild_only()
    @ac_guild_only()
    @checks.check_members_enabled
    @checks.check_presences_enabled
    async def serverinfo(
        self,
        ctx: bots.CustomContext,
    ) -> None:
        """Gets info on a server."""
        guild: Guild = ctx.guild
        embed = (
            discord.Embed(
                colour=discord.Colour.random(),
                title=f"Info for {guild.name}\n({guild.id})",
            )
            .add_field(
                name="Server Owner:",
                value=f"{guild.owner.display_name}#{guild.owner.discriminator} ({guild.owner.id})",
            )
            .add_field(
                name="Created at:",
                value=f"<t:{guild.created_at.timestamp():.0f}:R>",
            )
            .add_field(name="Roles:", value=len(guild.roles))
            .add_field(name="Emojis:", value=f"{len(guild.emojis)}/{guild.emoji_limit}")
            .add_field(
                name="Total channels:",
                value=f"{len(guild.channels)} channels, {len(guild.categories)} categories.",
            )
            .add_field(name="Total members:", value=guild.member_count)
        )
        if guild.icon is not None:
            embed.set_thumbnail(url=guild.icon.url)

            embed.add_field(name="Icon URL:", value=f"[Click Here]({guild.icon.url})")
        await ctx.send(embed=embed)
        await ctx.invoke(self.whois, user=guild.owner)

    @hybrid_command()
    async def botinfo(self, ctx: bots.CustomContext) -> None:
        """Displays information about the bot and the machine it's running on, as well as an invitation link."""

        async with ctx.typing(ephemeral=True):
            try:
                peppercord_version, peppercord_commit = get_version()

                base = ctx.bot.config.get(
                    "PEPPERCORD_WEB", "https://www.regulad.xyz/PepperCord"
                )
                embed: discord.Embed = (
                    discord.Embed(
                        colour=discord.Colour.orange(),
                        title=f"Hi, I'm {ctx.bot.user.name}! Nice to meet you!",
                        description=f"**Important Links**: "
                        f"[Website]({base}) | [Donate]({base}/donate) | [Discord]({base}/discord)"
                        f"\n**{'Owner' if ctx.bot.owner_id is not None else 'Owners'}**: "
                        f"{str(ctx.bot.owner_id) if ctx.bot.owner_id is not None else ', '.join(str(owner_id) for owner_id in ctx.bot.owner_ids)}",
                    )
                    .set_thumbnail(url=ctx.bot.user.avatar.url)
                    .add_field(
                        name="Invite:",
                        value=f"[Click Here]({discord.utils.oauth_url(client_id=str(ctx.bot.user.id), permissions=discord.Permissions(permissions=3157650678), scopes=('bot', 'applications.commands'))})",
                        inline=False,
                    )
                    .add_field(
                        name="Bot status:",
                        value=f"Online, servicing {len(ctx.bot.users)} users in {len(ctx.bot.guilds)} servers",
                    )
                    .add_field(
                        name="System resources:",
                        value=f"Memory: "
                        f"{round(psutil.virtual_memory().used / 1073741824, 1)}GB/"
                        f"{round(psutil.virtual_memory().total / 1073741824, 1)}GB "
                        f"({psutil.virtual_memory().percent}%)"
                        f"\nCPU: {platform.processor()} running at "
                        f"{round(psutil.cpu_freq().current) / 1000}GHz, "
                        f"{psutil.cpu_percent(interval=None)}% utilized ({psutil.cpu_count()} logical cores, "
                        f"{psutil.cpu_count(logical=False)} physical cores",
                    )
                    .add_field(
                        name="Versions:",
                        value=f"OS: {platform.system()} (`{platform.release()}`)"
                        f"\nPython: `{version}`"
                        f"\ndiscord.py: `{discord.__version__}`"
                        f"\nBot Version: `{peppercord_version}` (`{peppercord_commit}`)",
                        inline=False,
                    )
                )
            except psutil.Error:
                await ctx.send(
                    "Had trouble fetching information about the bot. Try again later."
                )
            else:
                await ctx.send(embed=embed, ephemeral=True)
                if ctx.guild is not None:
                    await ctx.invoke(self.whois, user=ctx.guild.me)


async def setup(bot: bots.BOT_TYPES) -> None:
    await bot.add_cog(Info(bot))
