"""
Utilities for working with self bots.
"""
from discord import Message, Webhook, Embed
from discord.utils import format_dt

from utils.bots import SendHandler, CustomContext
from utils.webhook import get_or_create_namespaced_webhook


class EmbedSendHandler(SendHandler):
    def __init__(self, ctx: CustomContext):
        self.ctx: CustomContext = ctx

    async def send(self, *args, **kwargs) -> Message:
        if kwargs.get("ephemeral") is not None:
            del kwargs["ephemeral"]
        if kwargs.get("return_message") is not None:
            del kwargs["return_message"]
        if kwargs.get("reference") is None:
            kwargs["reference"] = self.ctx.message
        if kwargs.get("embed") is not None:
            if self.ctx.guild is not None and self.ctx.guild.me.guild_permissions.manage_webhooks:
                embed_compat_webhook: Webhook = (
                    await get_or_create_namespaced_webhook(
                        "embed_compat",
                        self.ctx.bot,
                        self.ctx.channel,
                        avatar=await self.ctx.guild.me.avatar.read(),
                        name=self.ctx.guild.me.display_name,
                    )
                )
                del kwargs["reference"]
                return await embed_compat_webhook.send(*args, **kwargs)
            else:
                embed: Embed = kwargs["embed"]

                if len(args) > 0:
                    maybe_content: str = args[0]
                elif kwargs.get("content") is not None:
                    maybe_content: str = kwargs["content"]
                else:
                    maybe_content: str = ""

                if len(maybe_content) > 0:
                    maybe_content += "\n\n===\n\n"

                # title

                if embed.title is not None:
                    maybe_content += f"**{embed.title}**" + "\n"

                if embed.description is not None:
                    maybe_content += embed.description + "\n"

                # fields

                if len(embed.fields) > 0:
                    maybe_content += "\n"
                    maybe_content += "---\n"
                    maybe_content += "\n"

                    for field in embed.fields:
                        maybe_content += f"**{field.name}**" + "\n"
                        maybe_content += field.value + "\n"
                        maybe_content += "\n"

                # footer

                if embed.footer is not None \
                        and hasattr(embed.footer, "text") \
                        and embed.footer.text is not None:
                    maybe_content += "\n"
                    maybe_content += "---\n"
                    maybe_content += "\n"
                    maybe_content += embed.footer.text
                    maybe_content += "\n"

                # author

                if embed.author is not None \
                        and hasattr(embed.author, "name") \
                        and embed.author.name is not None:
                    maybe_content += "\n"
                    maybe_content += "---\n"
                    maybe_content += "\n"
                    maybe_content += embed.author.name
                    maybe_content += "\n"

                # timestamp

                if embed.timestamp is not None:
                    maybe_content += "\n"
                    maybe_content += "---\n"
                    maybe_content += "\n"
                    maybe_content += f"**Sent at {format_dt(embed.timestamp, 'R')}**"
                    maybe_content += "\n"

                # thumbnail

                if embed.thumbnail is not None \
                        and hasattr(embed.thumbnail, "url") \
                        and embed.thumbnail.url is not None \
                        and "attachment" not in embed.thumbnail.url:
                    maybe_content += "\n"
                    maybe_content += "---\n"
                    maybe_content += "\n"
                    maybe_content += f"Thumbnail: {embed.thumbnail.url}"
                    maybe_content += "\n"

                # image

                if embed.image is not None \
                        and hasattr(embed.image, "url") \
                        and embed.image.url is not None \
                        and "attachment" not in embed.image.url:
                    maybe_content += "\n"
                    maybe_content += "---\n"
                    maybe_content += "\n"
                    maybe_content += f"Image: {embed.image.url}"
                    maybe_content += "\n"

                # author icon

                if embed.author is not None \
                        and hasattr(embed.author, "icon_url") \
                        and embed.author.icon_url is not None \
                        and "attachment" not in embed.author.icon_url:
                    maybe_content += "\n"
                    maybe_content += "---\n"
                    maybe_content += "\n"
                    maybe_content += f"Author icon: {embed.author.icon_url}"
                    maybe_content += "\n"

                # footer icon

                if embed.footer is not None \
                        and hasattr(embed.footer, "icon_url") \
                        and embed.footer.icon_url is not None \
                        and "attachment" not in embed.footer.icon_url:
                    maybe_content += "\n"
                    maybe_content += "---\n"
                    maybe_content += "\n"
                    maybe_content += f"Footer icon: {embed.footer.icon_url}"
                    maybe_content += "\n"

                # send it

                del kwargs["embed"]

                if kwargs.get("content") is not None:
                    kwargs["content"] = maybe_content
                else:
                    args = (maybe_content, )

                return await self.ctx.send_bare(*args, **kwargs)
        else:
            return await self.ctx.send_bare(*args, **kwargs)
