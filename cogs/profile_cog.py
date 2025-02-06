# cogs/profile_cog.py
import os
import json
from discord.ext import commands
import discord
from cogs.base_cog import BaseCog

# Resolve the file path relative to your project root.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
USER_PROFILES_FILE = os.path.join(BASE_DIR, "usernames.json")


def load_profiles():
    try:
        with open(USER_PROFILES_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_profiles(profiles):
    with open(USER_PROFILES_FILE, "w") as f:
        json.dump(profiles, f, indent=4)


class ProfileCog(BaseCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Profile format: { user_id: {"server": server, "first": first, "last": last} }
        self.profiles = load_profiles()

    @commands.command(name="iam")
    async def iam(self, ctx: commands.Context, server: str = None, first: str = None, last: str = None):
        """
                Set your profile.
                Expected format: !iam server first last
        """
        if not server or not first or not last:
            await ctx.reply("Error: Incorrect input format. Use `!iam server first last`", mention_author=False)
            return

        profile = {
            "server": server,
            "first": first,
            "last": last
        }

        self.profiles[str(ctx.author.id)] = profile
        worldname = f"{first} {last}"
        async with ctx.typing():
            ids = self.lodestone_search(server, worldname)
            if len(ids) == 0:
                await ctx.reply("No profile found.", mention_author=False)
                return

            save_profiles(self.profiles)
            await ctx.reply(f"Profile stored: Server: {server}, Name: {first} {last}")

    @commands.command(name="whoami")
    async def whoami(self, ctx: commands.Context):
        """
        Use the stored profile to search Lodestone and capture a screenshot.
        """
        profile = self.profiles.get(str(ctx.author.id))
        if not profile:
            await ctx.reply("No profile found. Use `!iam server first last` to set your profile.", mention_author=False)
            return

        server = profile["server"]
        first = profile["first"]
        last = profile["last"]
        full_name = f"{first} {last}"
        # Convert first and last into a slug, e.g. "first-last"
        name_slug = f"{first}-{last}".lower()

        # Search Lodestone for the user's character using full name and server
        async with ctx.typing():
            character_ids = self.lodestone_search(full_name, server)
            if not character_ids:
                await ctx.send("No character found on Lodestone.")
                return
            char_id = character_ids[0]

            # Capture screenshot from URL: https://jp.tomestone.gg/character/{char_id}/{name_slug}
            screenshot_path = await self.capture_screenshot(char_id, name_slug)
            await ctx.reply(file=discord.File(screenshot_path))


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
    print("ProfileCog loaded.")
