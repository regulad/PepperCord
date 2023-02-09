from __future__ import annotations

from discord.ext import commands

from utils.bots import CustomContext


@commands.check
async def check_message_content_enabled(ctx: CustomContext) -> bool:
    return ctx.bot.intents.message_content


@commands.check
async def check_presences_enabled(ctx: CustomContext) -> bool:
    return ctx.bot.intents.presences


@commands.check
async def check_members_enabled(ctx: CustomContext) -> bool:
    return ctx.bot.intents.members


__all__ = (
    "check_message_content_enabled",
    "check_presences_enabled",
    "check_members_enabled",
)
