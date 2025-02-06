# cogs/misc_cog.py
import discord
from discord.ext import commands

class MiscCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="reply")
    async def reply(self, ctx: commands.Context, user: discord.Member, *, message: str):
        print("Reply")
        await ctx.send(f"{user.mention}, {message}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return  # Ignore the bot's own messages

        if message.content.startswith("!hello"):
            params = message.content.split()[1:]  # Skip the command itself

            if params:
                formatted_params = " and ".join(params)  # Join words with "and"
                response = f"Hi, {formatted_params} was sent"
            else:
                response = "Hi, but you didn't send any parameters!"

            await message.reply(response, mention_author=False)  # Reply without @mention
            return  # Do not call process_commands if we've already handled this message

        await self.bot.process_commands(message)  # Allow other commands to run


async def setup(bot: commands.Bot):
    await bot.add_cog(MiscCog(bot))
    print("MiscCog loaded.")
