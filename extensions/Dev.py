import typing

import discord
from discord.ext import commands, menus
from utils import errors
from utils.database import Document


class ShardMenu(menus.Menu):
    def __init__(
        self,
        shard_info,
        *,
        timeout=180.0,
        delete_message_after=False,
        clear_reactions_after=False,
        check_embeds=False,
        message=None,
    ):
        self.shard_info = shard_info

        super().__init__(
            timeout=timeout,
            delete_message_after=delete_message_after,
            clear_reactions_after=clear_reactions_after,
            check_embeds=check_embeds,
            message=message,
        )

    async def send_initial_message(self, ctx, channel):
        embed = discord.Embed(
            title=f"Info for shard {self.shard_info.id}",
        ).add_field(name="Online:", value=not self.shard_info.is_closed())
        return await channel.send(embed=embed)

    @menus.button("🔄")
    async def reconnect(self, payload):
        return await self.shard_info.reconnect()


class Dev(
    commands.Cog,
    name="Developer",
    description="Commands for the bot's developer used to operate the bot.",
):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.command(
        name="blacklist",
        description="Tools to blacklist entity from using the bot.",
        brief="Blacklists declared entity.",
        usage="<Value> <Entity>",
    )
    async def blacklist(
        self,
        ctx,
        value: typing.Optional[bool],
        *,
        entity: typing.Optional[typing.Union[discord.User, discord.Member, discord.Guild]],
    ):
        value = value or True
        entity = entity or ctx.guild
        if isinstance(entity, discord.Guild):
            document = await Document.get_from_id(self.bot.database["guild"], entity.id)
        elif isinstance(entity, (discord.Member, discord.User)):
            document = await Document.get_from_id(self.bot.database["guild"], entity.id)
        document["blacklisted"] = True
        await document.replace_db()

    @commands.command(
        name="nick",
        aliases=["nickname"],
        brief="Change nickname.",
        description="Change the bot's nickname, for situations where you do not have privleges to.",
    )
    @commands.guild_only()
    async def nick(self, ctx, *, name: str):
        await ctx.guild.me.edit(nick=name)

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="shard",
        brief="Tools for managing shards.",
        description="Tools for managing shards like getting & restarting.",
    )
    async def shard(self, ctx):
        raise errors.SubcommandNotFound()

    @shard.command(
        name="get",
        brief="Get guild's shard ID.",
        description="Get the shard ID for a given guild. Will raise NotSharded if the bot is not sharded.",
        usage="[Guild|Current Guild]",
    )
    async def guild(self, ctx, *, guild: typing.Optional[discord.Guild]):
        guild = guild or ctx.guild
        try:
            shard = guild.shard_id
        except:
            raise errors.NotSharded()
        else:
            if shard is None:
                raise errors.NotSharded()
        await ctx.send(f"{guild.name} uses shard {shard}")

    @shard.command(
        name="info",
        brief="Gets info on a shard.",
        description="Gets info on a shard and presents a menu which can be used to manage the shard.",
    )
    async def reconnect(self, ctx, *, shard_id: int):
        try:
            shard_info_instance = self.bot.get_shard(shard_id)
        except:
            raise errors.NotSharded()
        else:
            if shard_info_instance is None:
                raise errors.NotSharded()
        await ShardMenu(shard_info_instance).start(ctx)


def setup(bot):
    bot.add_cog(Dev(bot))
