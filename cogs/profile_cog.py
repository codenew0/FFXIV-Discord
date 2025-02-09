# cogs/profile_cog.py
import os
import json
from discord.ext import commands
import discord
from cogs.base_cog import BaseCog

# Resolve the file path relative to your project root.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
USER_PROFILES_FILE = os.path.join(BASE_DIR, "usernames.json")


class ProfileCog(BaseCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Profile format: { user_id: {"server": server, "first": first, "last": last} }
        self.profiles = self.load_profiles()

    def load_profiles(self):
        try:
            with open(USER_PROFILES_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_profiles(self, profiles):
        with open(USER_PROFILES_FILE, "w") as f:
            json.dump(profiles, f, indent=4)

    @commands.command(name="iam")
    async def iam(self, ctx: commands.Context, server: str = None, first: str = None, last: str = None):
        """
                Set your profile.
                Expected format: !iam server first last
        """
        if not server or not first or not last:
            embed = discord.Embed(
                title="Error: Incorrect input format. Use `!iam server first last`",
                color=discord.Color.blue()
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        profile = {
            "server": server,
            "first": first,
            "last": last
        }

        self.profiles[str(ctx.author.id)] = profile
        full_name = f"{first} {last}"
        async with ctx.typing():
            ids = self.lodestone_search(full_name, server)
            if not ids:
                embed = discord.Embed(
                    title="No profile found.",
                    color=discord.Color.blue()
                )
                await ctx.reply(embed=embed, mention_author=False)
                return

            self.save_profiles(self.profiles)

            embed = discord.Embed(
                title="Profile stored",
                description=f"Server: {server}\n Name: {first} {last}",
                color=discord.Color.blue()
            )
            await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="whoami")
    async def whoami(self, ctx: commands.Context):
        """
        Use the stored profile to search Lodestone and capture a screenshot.
        """
        profile = self.profiles.get(str(ctx.author.id))
        if not profile:
            embed = discord.Embed(
                title="No profile found. Use `!iam server first last` to set your profile.",
                color=discord.Color.blue()
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        server = profile["server"]
        first = profile["first"]
        last = profile["last"]
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
            screenshot_path = await self.capture_screenshot(char_id, name_slug)

        # Create an Embed
        embed = discord.Embed(
            title="It's YOU!",
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
    await bot.add_cog(ProfileCog(bot))
    print("ProfileCog loaded.")
