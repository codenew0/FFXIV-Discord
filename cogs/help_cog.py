# cogs/help_cog.py
import discord
from discord.ext import commands

class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context):
        """
                Yes, it's me!!!!!!!
        """
        embed = discord.Embed(
            title="Help",
            description="List of available commands:",
            color=discord.Color.blue()
        )
        file = discord.File("icon.png", filename="icon.png")

        embed.set_author(name="FF14 bot", icon_url="attachment://icon.png")
        embed.set_thumbnail(url="attachment://icon.png")
        embed.add_field(name="Command Prefix", value="!", inline=True)
        embed.add_field(name="Inline Field 2", value="Value 2", inline=True)

        for command in self.bot.commands:
            # You can skip hidden commands if desired:
            if not command.hidden:
                embed.add_field(
                    name=command.name,
                    value=command.help or "No description provided",
                    inline=False
                )
        embed.set_footer(text="Footer text here", icon_url="attachment://icon.png")
        await ctx.send(embed=embed, file=file)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
    print("HelpCog loaded.")
