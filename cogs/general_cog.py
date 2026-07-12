# cogs/general_cog.py
import discord
from discord.ext import commands


ANNOUNCE_TEXT = """📢 **FF14 Bot アップデートのお知らせ**

🆕 **価格検索がDC指定に対応しました**
`!i` コマンドで、ワールド名だけでなくDC名でもマーケット価格を調べられるようになりました。
```
!i <DC> <アイテム名>
例: !i Elem アイスシャード
例: !i Elemental オーケストリオン譜:鬼の棲む島
```
もちろん、これまで通りワールド指定や指定なし検索も使えます。
```
!i Atomos アイスシャード
!i アイスシャード
```

🔧 **X通知・取得まわりを改善しました**
X側の表示遅延で古い投稿しか取れないことがあったため、取得ルートを見直しました。
`!X 5` のように件数を指定した時も、指定数に届きやすいように調整しています。

🧰 **Bot内部を整理しました**
`announce` / `ping` / `info` / `hello` を通常コマンド用モジュールへ移しました。
今後は多くの修正をBot全体の再起動なしで反映しやすくなります。"""


class GeneralCog(commands.Cog):
    """通常利用向けの基本コマンド。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="hello")
    async def hello(self, ctx: commands.Context, *params: str):
        """挨拶を返します"""
        if params:
            formatted_params = " and ".join(params)
            response = f"Hi, {formatted_params}! 👋"
        else:
            response = "どうも！👋"

        await ctx.reply(response, mention_author=False)

    @commands.command(name="announce", hidden=True)
    @commands.is_owner()
    async def announce(self, ctx: commands.Context):
        """アップデートお知らせを送信（Bot所有者のみ）"""
        await ctx.send(ANNOUNCE_TEXT)

    @commands.command(name="ping", aliases=["p"])
    async def ping(self, ctx: commands.Context):
        """
        🏓 Botの応答速度を確認

        使い方: !ping
        """
        latency_ms = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"レイテンシ: **{latency_ms}ms**",
            color=discord.Color.green() if latency_ms < 200 else discord.Color.orange()
        )

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="info", aliases=["botinfo", "about"])
    async def info(self, ctx: commands.Context):
        """
        ℹ️ Botの情報を表示

        使い方: !info
        """
        embed = discord.Embed(
            title="🤖 Bot情報",
            color=discord.Color.blue()
        )

        embed.add_field(name="Bot名", value=self.bot.user.name, inline=True)
        embed.add_field(name="レイテンシ", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="サーバー数", value=f"{len(self.bot.guilds)}", inline=True)
        embed.add_field(
            name="コマンド数",
            value=f"{len([c for c in self.bot.commands if not c.hidden])}",
            inline=True
        )
        embed.add_field(name="discord.py", value=discord.__version__, inline=True)
        embed.set_footer(text="!help でコマンド一覧を確認")

        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCog(bot))
    print("✅ GeneralCog loaded.")
