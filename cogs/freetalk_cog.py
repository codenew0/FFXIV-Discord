# cogs/freetalk_cog.py
import os
import json
from discord.ext import commands
from google import genai
from google.genai import types
import requests

# Resolve the file path relative to your project root.
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
# USER_PROFILES_FILE = os.path.join(BASE_DIR, "conversation_history.json")

def load_api():
    with open("config.json", "r") as f:
        config = json.load(f)
        api_key = config["AI_API_KEY"]
        api_url = config["AI_API_URL"]

    return api_key, api_url

class FreeTalkCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key, self.api_url = load_api()
        self.client = genai.Client(api_key=self.api_key)
        self.chat = self.client.chats.create(
            model='gemini-2.0-flash',
            config=types.GenerateContentConfig(
                system_instruction='君はヤンキーだ！ヤンキーの喋り方で',
                max_output_tokens=4000,
                top_k=2,
                top_p=0.5,
                temperature=0.5
            )
        )

    def auto_chat(self, user_message: str):
        # Endpoint URL (v1beta is a placeholder version and may change)

        response = self.chat.send_message(user_message)
        # print(response.text)
        return response.text


    @commands.command(name="ft")
    async def freetalk(self, ctx: commands.Context, *, message):
        """
                This is a freetalk
        """
        async with ctx.typing():
            ai_reply = self.auto_chat(message)
            if not ai_reply:
                await ctx.reply("503 Server Error: Service Unavailable")
            await ctx.reply(ai_reply)


# Note the async setup function
async def setup(bot: commands.Bot):
    await bot.add_cog(FreeTalkCog(bot))
    print("FreeTalkCog loaded.")
