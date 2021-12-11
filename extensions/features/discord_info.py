import platform
from sys import version
from typing import Union, Optional

import discord
import psutil
import git
from discord.ext import commands, tasks

from utils import bots


class DiscordInfo(commands.Cog):
    """Get information about things here on Discord."""

    def __init__(self, bot: bots.BOT_TYPES) -> None:
        self.bot = bot

        self.activity_update.start()

    def cog_unload(self) -> None:
        self.activity_update.stop()

    @tasks.loop(seconds=600)
    async def activity_update(self) -> None:
        watching_string = (
            f"in {len(self.bot.guilds)} guild(s) "
            f"| {self.bot.config.get('PEPPERCORD_WEB', 'https://www.regulad.xyz/PepperCord')}"
        )
        await self.bot.change_presence(activity=discord.Game(name=watching_string))

    @activity_update.before_loop
    async def before_activity_update(self) -> None:
        await self.bot.wait_until_ready()

    @commands.command()
    @commands.is_owner()
    async def status(
        self,
        ctx: bots.CustomContext,
        *,
        activity: Optional[str] = commands.Option(
            description="The status that the bot will change to."
        ),
    ) -> None:
        """Sets the bot's status. If no status is specified, it will go back to the default."""
        task_is_running = self.activity_update.is_running()

        if activity is None and not task_is_running:
            self.activity_update.start()
        else:
            self.activity_update.cancel()
            watching_string = (
                f"{activity} "
                f"| {ctx.bot.config.get('PEPPERCORD_WEB', 'https://www.regulad.xyz/PepperCord')}"
            )
            await ctx.bot.change_presence(activity=discord.Game(name=watching_string))
        await ctx.send("Status updated.", ephemeral=True)

    @commands.command()
    async def whois(
        self,
        ctx: bots.CustomContext,
        *,
        user: Optional[Union[discord.Member, discord.User]] = commands.Option(
            description="The user that will have their info displayed. This can be any user, in or outside this server."
        ),
    ) -> None:
        """Get information on you, a Member of this server, or any User of Discord."""
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
            embed = embed.insert_field_at(0, name="Status:", value=f"{user.status}")
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

    @commands.command()
    @commands.guild_only()
    async def serverinfo(
        self,
        ctx: bots.CustomContext,
        *,
        guild: Optional[discord.Guild] = commands.Option(
            description="The server that will have it's data displayed. Defaults to the current server."
        ),
    ) -> None:
        """Gets info on a server."""
        guild = guild or ctx.guild
        embed = (
            discord.Embed(
                colour=discord.Colour.random(),
                title=f"Info for {guild.name}\n({guild.id})",
            )
            .set_thumbnail(url=guild.icon.url)
            .add_field(name="Icon URL:", value=f"[Click Here]({guild.icon.url})")
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
        await ctx.send(embed=embed)
        await ctx.invoke(self.whois, user=guild.owner)

    @commands.command()
    async def botinfo(self, ctx: bots.CustomContext) -> None:
        """Displays information about the bot and the machine it's running on, as well as an invitation link."""
        await ctx.defer(ephemeral=True)

        try:
            base = ctx.bot.config.get(
                "PEPPERCORD_WEB", "https://www.regulad.xyz/PepperCord"
            )
            embed = (
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
                    value=f"[Click Here]({discord.utils.oauth_url(client_id=str(ctx.bot.user.id), permissions=discord.Permissions(permissions=3157650678), guild=ctx.guild, scopes=('bot', 'applications.commands'))})",
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
                    f"{psutil.cpu_count(logical=False)} physcial cores",
                )
                .add_field(
                    name="Versions:",
                    value=f"OS: {platform.system()} (`{platform.release()}`)"
                    f"\nPython: `{version}`"
                    f"\ndiscord.py: `{discord.__version__}`"
                    f"\nPepperCord: `{git.Repo().tags[-1].name if len(git.Repo().tags) > 0 else '?'}` (`{git.Repo().head.commit}`)",
                    inline=False,
                )
            )
        except psutil.Error:
            await ctx.send(
                "Had trouble fetching information about the bot. Try again later."
            )
        else:
            await ctx.send(embed=embed, ephemeral=True)
            await ctx.invoke(self.whois, user=ctx.bot.user)


def setup(bot: bots.BOT_TYPES) -> None:
    bot.add_cog(DiscordInfo(bot))
