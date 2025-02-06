# cogs/test_cog.py
from discord.ext import commands


class TestCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="hello")
    async def hello(self, ctx: commands.Context, *args):
        """
                Say hello guys!
        """
        response = " ".join(args) if args else "Hello!"
        await ctx.reply(response)


# Note the async setup function
async def setup(bot: commands.Bot):
    await bot.add_cog(TestCog(bot))
    print("TestCog has been loaded.")
