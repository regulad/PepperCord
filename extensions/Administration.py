import discord
from discord.ext import commands, menus

from utils import checks


class DeleteMenu(menus.Menu):
    """Confirmation menu for deleting server information."""

    async def send_initial_message(self, ctx, channel):
        return await ctx.send(
            "**Warning:** This action is destructive. *Please* only continue if you know what you are doing."
        )

    @menus.button("✅")
    async def confirm(self, payload):
        await self.message.edit(content="Deleting guild information...")
        await self.ctx.guild_document.delete_db()
        await self.ctx.guild.leave()
        self.stop()

    @menus.button("❌")
    async def reject(self, payload):
        await self.message.edit(content="Operation cancelled.")
        self.stop()

    async def prompt(self, ctx):
        await self.start(ctx)


class Administration(commands.Cog):
    """Tools for administrating and configuring guilds."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return await checks.is_admin(ctx)

    @commands.command(
        name="message",
        brief="Send a message as the bot.",
        description="Send a message as the bots in any channel that you want.",
        usage="<Channel> <Message>",
    )
    async def do_message(self, ctx, channel: discord.TextChannel, *, text: str):
        channel = ctx.bot.get_channel(channel.id)
        await channel.send(text)

    @commands.group(
        invoke_without_command=True,
        case_insensitive=True,
        name="configuration",
        aliases=["config"],
        brief="Configures bots.",
        description="Configures bots in the scope of this server.",
    )
    async def config(self, ctx):
        pass

    @config.command(
        name="mute",
        brief="Sets role used to mute people.",
        description="Sets the role that is given to people who are muted. It must already be configured.",
    )
    async def mute(self, ctx, *, role: discord.Role):
        await ctx.guild_document.update_db({"$set": {"mute_role": role.id}})

    @commands.command(
        name="delete",
        aliases=["leave"],
        brief="Deletes all data on the server, then leaves.",
        description="Deletes all the data the bots has collected and stored on this server, then leaves. Be careful!",
    )
    async def delete(self, ctx):
        await DeleteMenu().start(ctx)


def setup(bot):
    bot.add_cog(Administration(bot))
