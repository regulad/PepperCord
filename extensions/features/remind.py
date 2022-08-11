from asyncio import Semaphore
from datetime import datetime, timedelta
from typing import cast

from discord import Member, Status, Thread, CategoryChannel, TextChannel, ForumChannel, DiscordException
from discord.app_commands import describe
from discord.ext.commands import Cog, hybrid_command
from discord.ext.tasks import loop

from utils.bots import BOT_TYPES, CustomContext
from utils.converters import TimedeltaShorthand
from utils.database import Document


class Remind(Cog):
    """A simple reminder system that can remind you of things later in time or later when you come online."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot
        self.semaphore_acquisition_lock: Semaphore = Semaphore(1)
        self.user_semaphores: dict[int, Semaphore] = {}

    def cog_load(self) -> None:
        self.send_reminders.start()

    def cog_unload(self) -> None:
        self.send_reminders.stop()

    @loop(seconds=10)
    async def send_reminders(self) -> None:
        for user in self.bot.users:
            document: Document = await self.bot.get_user_document(user)
            for reminder in document.get("remind", []).copy():
                if reminder["time"] < datetime.utcnow():
                    try:
                        maybe_channel: None | Thread | ForumChannel | TextChannel | CategoryChannel = self.bot.get_channel(
                            reminder["channel"])
                        if maybe_channel is not None:
                            await user.send(f"Reminder from {maybe_channel.mention}:\n{reminder['message']}")
                    except DiscordException:
                        continue
                    finally:
                        await document.update_db({"$pull": {"remind": reminder}})


    @Cog.listener()
    async def on_presence_update(self, before: Member, after: Member) -> None:
        document: Document = await self.bot.get_user_document(after)
        async with self.semaphore_acquisition_lock:
            semaphore: Semaphore = self.user_semaphores.get(after.id) or Semaphore(1)
            # This is a little clunky, but it avoids weird edge cases in situations where the same user is in a shitload of mutual servers involving random DB writes and reads.
            if semaphore not in self.user_semaphores.values():
                self.user_semaphores[after.id] = semaphore
        async with semaphore:
            if after.status is not Status.offline and before.status is Status.offline:
                for reminder in document.get("remind_online", []).copy():
                    maybe_channel: None | Thread | ForumChannel | TextChannel | CategoryChannel = after.guild.get_channel_or_thread(reminder["channel"])
                    if maybe_channel is not None:
                        await after.send(f"Reminder from {maybe_channel.mention}:\n{reminder['message']}")
                        await document.update_db({"$pull": {"remind_online": reminder}})



    @hybrid_command()
    @describe(
        time="The time between now and when you want to be reminded. (ex. 1d, 1h, 1m, 1s)",
        message="The message you want to be reminded of. Use $this to replace the message with the message you are replying to. (if applicable)",
    )
    async def remind(self, ctx: CustomContext, time: TimedeltaShorthand, *, message: str = "$this") -> None:
        """
        Reminds you of something after a certain amount of time.
        """
        time: timedelta = cast(timedelta, time)
        if ctx.message.reference is not None:
            message = message.replace("$this", ctx.message.reference.jump_url)
        await ctx["author_document"].update_db({"$push": {"remind": {"message": message, "channel": ctx.channel.id, "time": datetime.utcnow() + time}}})
        await ctx.send(f"I will remind you in {time}. Leave your DMs open.", ephemeral=True)

    @hybrid_command()
    @describe(
        message="The message you want to be reminded of. Use $this to replace the message with the message you are replying to. (if applicable)",
    )
    async def remind_online(self, ctx: CustomContext, *, message: str = "$this") -> None:
        """
        Reminds you of something when you come online.
        """
        if ctx.message.reference is not None:
            message = message.replace("$this", ctx.message.reference.jump_url)
        await ctx["author_document"].update_db({"$push": {"remind_online": {"message": message, "channel": ctx.channel.id}}})
        await ctx.send(f"I will remind you when you come online next. Leave your DMs open.", ephemeral=True)


async def setup(bot: BOT_TYPES) -> None:
    """
    Sets up the Remind cog.
    """
    await bot.add_cog(Remind(bot))
