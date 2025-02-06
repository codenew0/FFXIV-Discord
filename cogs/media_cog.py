# cogs/media_cog.py
import discord
from discord.ext import commands
from cogs.base_cog import BaseCog
from playwright.async_api import async_playwright


class MediaCog(BaseCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="send_photo")
    async def send_photo(self, ctx: commands.Context):
        async with ctx.typing():
            photo = await self.capture_screenshot('43656940', 'trunks-vegeta')
            await ctx.reply(file=discord.File(photo))


async def setup(bot: commands.Bot):
    await bot.add_cog(MediaCog(bot))
    print("MediaCog loaded.")
