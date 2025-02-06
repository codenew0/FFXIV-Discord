# cogs/help_cog.py
import discord
from discord.ext import commands

class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Help",
            description="List of available commands:",
            color=discord.Color.blue()
        )
        for command in self.bot.commands:
            # You can skip hidden commands if desired:
            if not command.hidden:
                embed.add_field(
                    name=command.name,
                    value=command.help or "No description provided",
                    inline=False
                )
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
    print("HelpCog loaded.")
