# cogs/search_charac_cog.py
import discord
from discord.ext import commands
from cogs.base_cog import BaseCog


class SearchCog(BaseCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="charac")
    async def charac(self, ctx: commands.Context, server: str = None, first: str = None, last: str = None):
        """
                Show the user's profile.
                Expected format: !lodestone server first last
        """
        if not server or not first or not last:
            await ctx.reply("Error: Incorrect input format. Use `!lodestone server first last`", mention_author=False)
            return
        full_name = f"{first} {last}"
        # Convert first and last into a slug, e.g. "first-last"
        name_slug = f"{first}-{last}".lower()

        # Search Lodestone for the user's character using full name and server
        async with ctx.typing():
            char_id = self.lodestone_search(full_name, server)
            if not char_id:
                embed = discord.Embed(
                    title="No character found on Lodestone!",
                    color=discord.Color.blue()
                )
                await ctx.reply(embed=embed, mention_author=False)
                return

            # Capture screenshot from URL: https://jp.tomestone.gg/character/{char_id}/{name_slug}
            screenshot_path = await self.capture_screenshot(char_id, name_slug)

        # Create an Embed
        embed = discord.Embed(
            title="Found it!",
            description=f"Server: {server}\nName: {full_name}",
            color=discord.Color.blue()
        )

        # Attach the screenshot file
        file = discord.File(screenshot_path, filename="lodestone.png")

        # Reference the attached file in the embed
        embed.set_image(url="attachment://lodestone.png")

        # Send the embed with the file
        await ctx.reply(embed=embed, file=file, mention_author=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(SearchCog(bot))
    print("SearchCog loaded.")
