# cogs/freetalk_cog.py
import json
from discord.ext import commands
from google import genai
from google.genai import types

def load_api():
    """
    config.jsonからAI関連のAPIキーとURLを読み込み、
    それらを返す関数。
    """
    with open("config.json", "r") as f:
        config = json.load(f)
        api_key = config["AI_API_KEY"]
        api_url = config["AI_API_URL"]

    return api_key, api_url

class FreeTalkCog(commands.Cog):
    """
    フリートークを行うためのCogクラス。
    AI(GenAI)を利用してユーザーからのメッセージに
    ヤンキーの口調で返信する。
    """
    def __init__(self, bot: commands.Bot):
        """
        FreeTalkCogのコンストラクタ。
        config.jsonからAPIキーとURLを読み込み、
        gemini-2.0-flashモデルでチャットを初期化する。
        """
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
        """
        ユーザーからのメッセージ(user_message)を
        AIに送り、返信テキストを返す関数。
        """
        # AIチャットモデルにメッセージを送信し、返信を受け取る
        response = self.chat.send_message(user_message)
        return response.text

    @commands.command(name="ft")
    async def freetalk(self, ctx: commands.Context, *, message):
        """
        このおれと話してみよう！！
        Usage: !ft <メッセージ>
        """
        if not message:
            await ctx.reply("何か話したいのある？！")

        # 「 typing() 」で思考中のステータスを表示
        async with ctx.typing():
            ai_reply = self.auto_chat(message)
            if not ai_reply:
                # 応答が得られなかった場合
                await ctx.reply("503 Server Error: Service Unavailable")
            else:
                # AIの返信をユーザーへ返信
                await ctx.reply(ai_reply)

# 非同期のセットアップ関数
async def setup(bot: commands.Bot):
    """
    このCogをBotに登録するための関数。
    Botの拡張機能としてロードされる。
    """
    await bot.add_cog(FreeTalkCog(bot))
    print("FreeTalkCog loaded.")
