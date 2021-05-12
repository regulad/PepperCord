import platform
import sys
import typing

import discord
import psutil
from discord.ext import commands, tasks


class discordInfo(
    commands.Cog,
    name="Discord Info",
    description="Shows information about things on Discord.",
):
    def __init__(self, bot):
        self.bot = bot

        self.activityUpdate.start()

    def cog_unload(self):
        self.activityUpdate.stop()

    @tasks.loop(seconds=60)
    async def activityUpdate(self):
        watchingString = f"with {len(self.bot.users)} users in {len(self.bot.guilds)} servers"
        await self.bot.change_presence(activity=discord.Game(name=watchingString))

    @activityUpdate.before_loop
    async def beforeActivyUpdate(self):
        await self.bot.wait_until_ready()

    @commands.command(
        name="whoIs",
        aliases=["user", "member", "userInfo", "memberInfo", "pfp"],
        description="Displays information about a user.",
        brief="Get user info.",
        usage="[User (ID/Mention/Name)]",
    )
    async def whoIs(self, ctx, *, user: typing.Union[discord.Member, discord.User] = None):
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
                    embed = embed.insert_field_at(0, name="Also known as:", value=user.display_name)
                embed = embed.add_field(name="Server join date:", value=f"{user.joined_at} UTC")
                if user.premium_since:
                    embed = embed.add_field(name="Server boosting since:", value=f"{user.premium_since} UTC")
        except:
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
    async def serverInfo(self, ctx, *, guild: discord.Guild = None):
        if not guild:
            guild = ctx.guild
        guildOwner = guild.owner
        try:
            embed = (
                discord.Embed(
                    colour=discord.Colour.random(),
                    title=f"Info for {guild.name}\n({guild.id})",
                )
                .set_thumbnail(url=guild.icon_url)
                .add_field(name="Server Owner:", value=guildOwner.display_name)
                .add_field(name="Created at:", value=f"{guild.created_at} UTC")
                .add_field(name="Roles:", value=len(guild.roles))
                .add_field(name="Emojis:", value=f"{len(guild.emojis)}/{guild.emoji_limit}")
                .add_field(
                    name="Total channels:",
                    value=f"{len(guild.channels)} channels, {len(guild.categories)} categories.",
                )
                .add_field(name="Total members:", value=guild.member_count)
            )
        except:
            await ctx.send("Couldn't find information on your guild.")
        else:
            await ctx.send(embed=embed)
        await ctx.invoke(self.whoIs, **{"user": guildOwner})

    @commands.command(
        name="botInfo",
        aliases=["bot", "invite", "donate", "bug", "bugreport", "support"],
        description="Displays information about the bot",
        brief="Get bot info.",
    )
    async def botInfo(self, ctx):
        try:
            embed = (
                discord.Embed(
                    colour=discord.Colour.orange(),
                    title=f"Hi, I'm {self.bot.user.name}! Nice to meet you!",
                    description="**Important Links**: [Website](https://www.regulad.xyz/PepperCord) | [Invite](https://www.regulad.xyz/PepperCord/invite) | [Server](https://www.regulad.xyz/discord) | [Donate](https://www.regulad.xyz/donate)\n **GitHub**: [Repository](https://github.com/regulad/PepperCord) | [Issues](https://github.com/regulad/PepperCord/issues) | [Pull Requests](https://github.com/regulad/PepperCord/pulls)\n*For support, please make a GitHub issue. The server isn't for support!*",
                )
                .set_thumbnail(url=self.bot.user.avatar_url)
                .add_field(
                    name="Bot status:",
                    value=f"Online, servicing {len(self.bot.users)} users in {len(self.bot.guilds)} servers",
                )
                .add_field(
                    name="System resources:",
                    value=f"Memory: {round(psutil.virtual_memory().used / 1073741824, 1)}GB/{round(psutil.virtual_memory().total / 1073741824, 1)}GB ({psutil.virtual_memory().percent}%)\nCPU: {platform.processor()} running at {round(psutil.cpu_freq().current) / 1000}GHz, {psutil.cpu_percent(interval=None)}% utilized ({psutil.cpu_count()} logical cores, {psutil.cpu_count(logical=False)} physcial cores",
                )
                .add_field(
                    name="Versions:",
                    value=f"OS: {platform.system()} (`{platform.release()}`)\nPython: `{sys.version}`\nDiscord.py: `{discord.__version__}`",
                    inline=False,
                )
            )
        except:
            await ctx.send("Had trouble fetching information about the bot. Try again later.")
        else:
            await ctx.send(embed=embed)

    @commands.command(
        name="snowflakeLookup",
        aliases=["snowflake", "snowflakeTime"],
        description="Returns the exact time in UTC when a snowflake is/was created.",
        brief="Get time snowflake is/was created.",
        usage="<Snowflake>",
    )
    async def snowflakeLookup(self, ctx, *, snowflake: int):
        snowflakeTime = discord.utils.snowflake_time(snowflake)
        await ctx.send(f"Snowflake was created at {snowflakeTime} UTC.")


def setup(bot):
    bot.add_cog(discordInfo(bot))
