from discord import Member, VoiceState
from discord.ext.commands import Cog

from utils.bots import BOT_TYPES


class AudioCore(Cog):
    """Tasks that assist the core of the bot's audio handling logic."""

    def __init__(self, bot: BOT_TYPES) -> None:
        self.bot: BOT_TYPES = bot

    @Cog.listener("on_voice_state_update")
    async def on_left_alone(
        self, member: Member, before: VoiceState, after: VoiceState
    ) -> None:
        if (
            member.guild.voice_client is not None
            and member.guild.voice_client.channel == before.channel
        ):
            if len(before.channel.members) == 1:
                await member.guild.voice_client.disconnect(force=False)


async def setup(bot: BOT_TYPES) -> None:
    await bot.add_cog(AudioCore(bot))
