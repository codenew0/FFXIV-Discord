# bot.py
import os
import discord
from discord.ext import commands
import json
import asyncio

# Load configuration from config.json
with open("config.json", "r") as f:
    config = json.load(f)

TOKEN = config["DISCORD_TOKEN"]
CHANNEL_ID = config["CHANNEL_ID"]

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Remove the default help command if you are using a custom one
bot.remove_command('help')

async def load_extensions():
    cogs_folder = "./cogs"
    print("Loading extensions from:", cogs_folder)
    for filename in os.listdir(cogs_folder):
        if filename.endswith(".py") and filename != "base_cog.py" and not filename.startswith("__"):
            extension = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(extension)
                # print(f"Loaded extension: {extension}")
            except Exception as e:
                print(f"Failed to load extension {extension}: {e}")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("Hello, I'm online!")
    # Debug: list all registered commands
    print("Registered commands:")
    for cmd in bot.commands:
        print(f"- {cmd.name}")


@bot.event
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


async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == '__main__':
    asyncio.run(main())
