import copy
import typing
from io import BytesIO

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont


class Images(commands.Cog, name="Images", description="Image editing funnies."):
    def __init__(self, bot):
        self.bot = bot

        self.arial_narrow_bold_font = ImageFont.truetype("resources/arial-narrow-bold.ttf", 72)
        self.impact_font = ImageFont.truetype("resources/impact.ttf")

        self.majora_image = Image.open("resources/blank.png")
        self.jarvis_image = Image.open("resources/jarvis.gif")
    
    @commands.command(name="pinsleft", description="Shows the amount of pins left, in a rather flashy way.", brief="Shows the amount of pins left.", usage="[Channel]")
    @commands.cooldown(1, 40, commands.BucketType.channel)
    async def pinsleft(self, ctx: commands.Context, *, channel: typing.Optional[discord.TextChannel]):
        async with ctx.typing():
            channel = channel or ctx.channel
            pins_left = 50 - len(await channel.pins())
            buffer = BytesIO()
            save_image = copy.deepcopy(self.majora_image)
            idraw = ImageDraw.Draw(save_image)
            idraw.text(xy=(650, 490), text=f"-{pins_left} Pins Remain-", stroke_fill="#FFFFFF", font=self.majora_font, anchor="ms")
            save_image.save(buffer, "PNG")
            buffer.seek(0)
            file = discord.File(buffer, "majora.png")
            await ctx.send(file=file)
    
def setup(bot):
    bot.add_cog(Images(bot))
