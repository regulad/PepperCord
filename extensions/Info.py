import platform
from sys import version
from typing import Union, Optional

import discord
import psutil
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
        watching_string = f"in {len(self.bot.guilds)} guild(s) " \
                          f"| {self.bot.config.get('PEPPERCORD_WEB', 'https://www.regulad.xyz/PepperCord')}"
        await self.bot.change_presence(activity=discord.Game(name=watching_string))

    @activity_update.before_loop
    async def before_activity_update(self) -> None:
        await self.bot.wait_until_ready()

    @commands.command(
        name="status",
        aliases=["setstatus"],
        brief="Sets bot's status.",
        description="Sets the bot's status. When no status is passed, go back to the default.",
    )
    @commands.is_owner()
    async def status(self, ctx: bots.CustomContext, *, activity: Optional[str]) -> None:
        task_is_running = self.activity_update.is_running()

        if activity is None and not task_is_running:
            self.activity_update.start()
        else:
            self.activity_update.cancel()
            watching_string = f"{activity} " \
                              f"| {ctx.bot.config.get('PEPPERCORD_WEB', 'https://www.regulad.xyz/PepperCord')}"
            await ctx.bot.change_presence(activity=discord.Game(name=watching_string))

    @commands.command(
        name="whois",
        aliases=["user", "member", "userInfo", "memberInfo", "pfp"],
        description="Displays information about a user.",
        brief="Get user info.",
        usage="[User (ID/Mention/Name)]",
    )
    async def whois(self, ctx: bots.CustomContext, *, user: Optional[Union[discord.Member, discord.User]]) -> None:
        if not user:
            user = ctx.author
        try:
            embed = (
                discord.Embed(
                    colour=user.colour,
                    title=f"All about {user.name}#{user.discriminator}\n({user.id})",
                )
                    .set_thumbnail(url=user.avatar_url)
                    .add_field(name="Account creation date:", value=f"{user.created_at} UTC")
            )
            if isinstance(user, discord.Member):
                embed = embed.insert_field_at(0, name="Status:", value=f"{user.status}")
                if user.name != user.display_name:
                    embed = embed.insert_field_at(0, name="Nickname:", value=user.display_name)
                embed = embed.add_field(name="Server join date:", value=f"{user.joined_at} UTC")
                if user.premium_since:
                    embed = embed.add_field(name="Server boosting since:", value=f"{user.premium_since} UTC")
        except discord.NotFound:
            await ctx.send("Couldn't find information on the user.")
        else:
            await ctx.send(embed=embed)

    @commands.command(
        name="serverInfo",
        aliases=["guildInfo", "server", "guild"],
        description="Displays information about the server the bot is in.",
        brief="Get server info.",
        usage="[Guild ID]",
    )
    @commands.guild_only()
    async def server_info(self, ctx: bots.CustomContext, *, guild: Optional[discord.Guild]) -> None:
        if not guild:
            guild = ctx.guild
        guild_owner = guild.owner
        try:
            embed = (
                discord.Embed(
                    colour=discord.Colour.random(),
                    title=f"Info for {guild.name}\n({guild.id})",
                )
                    .set_thumbnail(url=guild.icon_url)
                    .add_field(name="Server Owner:", value=guild_owner.display_name)
                    .add_field(name="Created at:", value=f"{guild.created_at} UTC")
                    .add_field(name="Roles:", value=len(guild.roles))
                    .add_field(name="Emojis:", value=f"{len(guild.emojis)}/{guild.emoji_limit}")
                    .add_field(
                    name="Total channels:",
                    value=f"{len(guild.channels)} channels, {len(guild.categories)} categories.",
                )
                    .add_field(name="Total members:", value=guild.member_count)
            )
        except discord.NotFound:
            await ctx.send("Couldn't find information on your guild.")
        else:
            await ctx.send(embed=embed)
            await ctx.invoke(self.whois, user=guild_owner)

    @commands.command(
        name="botinfo",
        aliases=["bot", "invite", "donate", "bug", "support", "owner"],
        description="Displays information about the bot",
        brief="Get bot info.",
    )
    async def invite(self, ctx: bots.CustomContext) -> None:
        async with ctx.typing():
            try:
                base = ctx.bot.config.get('PEPPERCORD_WEB', 'https://www.regulad.xyz/PepperCord')
                embed = discord.Embed(
                    colour=discord.Colour.orange(),
                    title=f"Hi, I'm {ctx.bot.user.name}! Nice to meet you!",
                    description=f"**Important Links**: "
                                f"[Website]({base}) | [Donate]({base}/donate) | [Discord]({base}/discord)"
                                f"\n**{'Owner' if ctx.bot.owner_id is not None else 'Owners'}**: "
                                f"{str(ctx.bot.owner_id) if ctx.bot.owner_id is not None else ', '.join(str(owner_id) for owner_id in ctx.bot.owner_ids)}"
                ).set_thumbnail(
                    url=ctx.bot.user.avatar_url
                ).add_field(
                    name="Invite:",
                    value=discord.utils.oauth_url(
                        client_id=str(ctx.bot.user.id),
                        permissions=discord.Permissions(permissions=3157650678),
                        guild=ctx.guild,
                        scopes=("bot", "applications.commands"),
                    ),
                    inline=False,
                ).add_field(
                    name="Bot status:",
                    value=f"Online, servicing {len(ctx.bot.users)} users in {len(ctx.bot.guilds)} servers",
                ).add_field(
                    name="System resources:",
                    value=f"Memory: "
                          f"{round(psutil.virtual_memory().used / 1073741824, 1)}GB/"
                          f"{round(psutil.virtual_memory().total / 1073741824, 1)}GB "
                          f"({psutil.virtual_memory().percent}%)"
                          f"\nCPU: {platform.processor()} running at "
                          f"{round(psutil.cpu_freq().current) / 1000}GHz, "
                          f"{psutil.cpu_percent(interval=None)}% utilized ({psutil.cpu_count()} logical cores, "
                          f"{psutil.cpu_count(logical=False)} physcial cores",
                ).add_field(
                    name="Versions:",
                    value=f"OS: {platform.system()} (`{platform.release()}`)"
                          f"\nPython: `{version}`"
                          f"\ndiscord.py: `{discord.__version__}`",
                    inline=False,
                )
            except psutil.Error:
                await ctx.send("Had trouble fetching information about the bot. Try again later.")
            else:
                await ctx.send(embed=embed)
                await ctx.invoke(self.whois, user=ctx.bot.user)


def setup(bot: bots.BOT_TYPES) -> None:
    bot.add_cog(DiscordInfo(bot))
