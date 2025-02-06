# cogs/search_cog.py
import discord
from discord.ext import commands
from cogs.base_cog import BaseCog


class SearchCog(BaseCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="lodestone")
    async def lodestone(self, ctx: commands.Context, server: str = None, first: str = None, last: str = None):
        if not server or not first or not last:
            await ctx.reply("Error: Incorrect input format. Use `!lodestone server first last`", mention_author=False)
            return
        full_name = f"{first} {last}"
        # Convert first and last into a slug, e.g. "first-last"
        name_slug = f"{first}-{last}".lower()

        # Search Lodestone for the user's character using full name and server
        async with ctx.typing():
            character_ids = self.lodestone_search(full_name, server)
            print(character_ids)
            if not character_ids:
                await ctx.reply("No character found on Lodestone.")
                return
            char_id = character_ids[0]

            # Capture screenshot from URL: https://jp.tomestone.gg/character/{char_id}/{name_slug}
            screenshot_path = await self.capture_screenshot(char_id, name_slug)
            await ctx.reply(file=discord.File(screenshot_path))

async def setup(bot: commands.Bot):
    await bot.add_cog(SearchCog(bot))
    print("SearchCog loaded.")
