import platform
from asyncio import sleep
from sys import version
from typing import Union, Optional, cast

import discord
import psutil
from discord import ClientUser, Interaction, Member, User, AppCommandType
from discord.app_commands import describe, context_menu
from discord.app_commands import guild_only as ac_guild_only
from discord.ext import commands, tasks
from discord.ext.commands import hybrid_command
from discord.utils import format_dt

from utils.bots.bot import CustomBot
from utils.bots.context import CustomContext
from utils.misc import status_breakdown
from utils.version import get_version

WHOIS_CM_NAME: str = "Get User Information"

# PepperCord's privacy policy and terms of service, as the repository's main branch holds them.
PRIVACY_POLICY_URL: str = "https://github.com/regulad/PepperCord/blob/main/PRIVACY.md"
TERMS_OF_SERVICE_URL: str = "https://github.com/regulad/PepperCord/blob/main/TOS.md"


@context_menu(name=WHOIS_CM_NAME)
async def whois_cm(interaction: Interaction[CustomBot], user: Member | User) -> None:
    ctx = await CustomContext.from_interaction(interaction)
    info = cast(Info, ctx.bot.get_cog("Info"))
    await info.whois(ctx, user=user)  # type: ignore[arg-type]  # weird type conflict


class Info(commands.Cog):
    """Get information about things here on Discord."""

    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot

    def cog_load(self) -> None:  # type: ignore[override]  # bad d.py type export
        self.bot.tree.add_command(whois_cm)

    def cog_unload(self) -> None:  # type: ignore[override]  # bad d.py type export
        self.bot.tree.remove_command(WHOIS_CM_NAME, type=AppCommandType.user)
        if self.activity_update.is_running():
            self.activity_update.stop()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await sleep(10)
        # on_ready fires again after every new gateway session, and starting a running loop raises.
        if not self.activity_update.is_running():
            self.activity_update.start()

    @tasks.loop(seconds=600)
    async def activity_update(self) -> None:
        watching_string = f"with {self.bot.perceivable_users:n} {'user' if self.bot.perceivable_users == 1 else 'users'} in {len(self.bot.guilds):n} {'server' if len(self.bot.guilds) == 1 else 'servers'}"
        await self.bot.change_presence(activity=discord.Game(name=watching_string))

    @activity_update.before_loop
    async def before_activity_update(self) -> None:
        await self.bot.wait_until_ready()
        # Changing the status of the bot immediately can prompt a disconnect. We need to wait!
        await sleep(10)

    @hybrid_command()  # type: ignore[arg-type]  # bad d.py export
    @commands.is_owner()
    @describe(activity="The status that the bot will change to.")
    async def status(
        self,
        ctx: CustomContext,
        *,
        activity: Optional[str],
    ) -> None:
        """Sets the bot's status. If no status is specified, it will go back to the default."""
        if activity is None:
            if not self.activity_update.is_running():
                self.activity_update.start()
        else:
            self.activity_update.cancel()
            await ctx.bot.change_presence(activity=discord.Game(name=activity))
        await ctx.send("Status updated.", ephemeral=True)

    @hybrid_command()  # type: ignore[arg-type]  # bad d.py export
    @describe(
        user="The user that will have their info displayed. This can be any user, in or outside this server."
    )
    async def whois(
        self,
        ctx: CustomContext,
        *,
        user: Optional[Union[discord.Member, discord.User]],
    ) -> None:
        """Get information on you, a Member of this server, or any User of Discord."""
        async with ctx.typing(ephemeral=True):
            if not user:
                user = ctx.author
            embed = discord.Embed(
                colour=user.colour,
                title=f"All about {user}\n({user.id})",
            )
            if user.avatar is not None:
                embed = embed.set_thumbnail(url=user.avatar).add_field(
                    name="Avatar URL:", value=f"[Click Here]({user.avatar.url})"
                )
            embed = embed.add_field(
                name="Account creation date:",
                value=format_dt(user.created_at, "R"),
            )
            if isinstance(user, discord.Member):
                after_breakdown = status_breakdown(
                    user.desktop_status, user.mobile_status, user.web_status
                )
                embed = embed.insert_field_at(
                    0,
                    name="Status:",
                    value=f"{user.status}{f' ({after_breakdown})' if after_breakdown is not None else ''}",
                )
                if user.name != user.display_name:
                    embed = embed.insert_field_at(
                        0, name="Nickname:", value=user.display_name
                    )
                if user.joined_at is not None:
                    embed = embed.add_field(
                        name="Server join date:",
                        value=format_dt(user.joined_at, "R"),
                    )
                if user.premium_since:
                    embed = embed.add_field(
                        name="Server boosting since:",
                        value=format_dt(user.premium_since, "R"),
                    )
            await ctx.send(embed=embed, ephemeral=True)

    @hybrid_command()  # type: ignore[arg-type]  # bad d.py export
    @commands.guild_only()
    @ac_guild_only()
    async def serverinfo(
        self,
        ctx: CustomContext,
    ) -> None:
        """Gets info on a server."""
        assert ctx.guild is not None  # guaranteed at runtime by check
        embed = discord.Embed(
            colour=discord.Colour.random(),
            title=f"Info for {ctx.guild.name}\n({ctx.guild.id})",
        )
        if ctx.guild.owner is not None:
            embed = embed.add_field(
                name="Server Owner:",
                value=f"{ctx.guild.owner.display_name} ({ctx.guild.owner.id})",
            )
        embed = (
            embed.add_field(
                name="Created at:",
                value=format_dt(ctx.guild.created_at, "R"),
            )
            .add_field(name="Roles:", value=len(ctx.guild.roles))
            .add_field(
                name="Emojis:", value=f"{len(ctx.guild.emojis)}/{ctx.guild.emoji_limit}"
            )
            .add_field(
                name="Total channels:",
                value=f"{len(ctx.guild.channels)} channels, {len(ctx.guild.categories)} categories.",
            )
            .add_field(name="Total members:", value=ctx.guild.member_count)
        )
        if ctx.guild.icon is not None:
            embed.set_thumbnail(url=ctx.guild.icon.url)

            embed.add_field(
                name="Icon URL:", value=f"[Click Here]({ctx.guild.icon.url})"
            )
        await ctx.send(embed=embed)
        await ctx.invoke(self.whois, user=ctx.guild.owner)

    @hybrid_command()  # type: ignore[arg-type]  # bad d.py export
    async def botinfo(self, ctx: CustomContext) -> None:
        """Displays information about the bot and the machine it's running on, as well as an invitation link."""

        async with ctx.typing(ephemeral=True):
            try:
                peppercord_version, peppercord_commit = get_version()

                embed = discord.Embed(
                    colour=discord.Colour.orange(),
                    title=f"Hi, I'm {cast(ClientUser, ctx.bot.user).name}! Nice to meet you!",
                    description=f"**Important Links**: "
                    f"[Privacy Policy]({PRIVACY_POLICY_URL}) | [Terms of Service]({TERMS_OF_SERVICE_URL})"
                    f"\n**{'Owner' if ctx.bot.owner_id is not None else 'Owners'}**: "
                    f"{
                            str(ctx.bot.owner_id)
                            if ctx.bot.owner_id is not None
                            else (
                                ', '.join(str(owner_id) for owner_id in ctx.bot.owner_ids)
                                if ctx.bot.owner_ids is not None
                                else "Currently unavailable, please check later!"
                            )
                        }",
                )
                if cast(ClientUser, ctx.bot.user).avatar is not None:
                    embed = embed.set_thumbnail(
                        url=cast(ClientUser, ctx.bot.user).avatar.url  # type: ignore[union-attr]  # guaranteed
                    )
                embed = (
                    embed.add_field(
                        name="Invite:",
                        value=f"[Click Here]({discord.utils.oauth_url(client_id=str(cast(ClientUser, ctx.bot.user).id), permissions=discord.Permissions(permissions=3157650678), scopes=('bot', 'applications.commands'))})",
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
                        # cpu_freq() is None where the kernel exposes no frequency, as on many ARM hosts.
                        f"\nCPU: {platform.processor()} running at "
                        f"{f'{round(freq.current) / 1000}GHz' if (freq := psutil.cpu_freq()) is not None else 'an unknown speed'}, "
                        f"{psutil.cpu_percent(interval=None)}% utilized ({psutil.cpu_count()} logical cores, "
                        f"{psutil.cpu_count(logical=False)} physical cores",
                    )
                    .add_field(
                        name="Versions:",
                        value=f"OS: {platform.system()} (`{platform.release()}`)"
                        f"\nPython: `{version}`"
                        f"\ndiscord.py: `{discord.__version__}`"
                        f"\nBot Version: `{peppercord_version}`"
                        + (
                            f" (`{peppercord_commit}`)"
                            if peppercord_commit is not None
                            else ""
                        ),
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


async def setup(bot: CustomBot) -> None:
    await bot.add_cog(Info(bot))
