# cogs/search_charac_cog.py
import discord
from discord.ext import commands
from cogs.base_cog import BaseCog


class SearchCog(BaseCog):
    """
    Lodestone上でキャラクターを検索し、スクリーンショットを取得してDiscordに送信するためのCogクラス。
    """
    def __init__(self, bot: commands.Bot):
        """
        コンストラクタ。
        Botのインスタンスを受け取り、クラス内で保持します。
        """
        self.bot = bot

    @commands.command(name="charac")
    async def charac(self, ctx: commands.Context, server: str = None, first: str = None, last: str = None):
        """
        そいつを覗いてみよう！（誰かのプロフィールを見る）
        Usage: !charac server first last
        """
        # 必要なパラメータが不足している場合、エラーメッセージを送信
        if not server or not first or not last:
            await ctx.reply("使い方わかる？！ `!charac server first last`", mention_author=False)
            return

        # フルネームを生成（例: "first last"）
        full_name = f"{first} {last}"
        # 名前をスラッグ形式に変換（例: "first-last"、すべて小文字に変換）
        name_slug = f"{first}-{last}".lower()

        # Lodestone上でキャラクターを検索
        async with ctx.typing():
            char_id = self.lodestone_search(full_name, server)
            if not char_id:
                # キャラクターが見つからなかった場合、Embedでエラーメッセージを送信
                embed = discord.Embed(
                    title="そんな人いないだぞ！！もしかして幽霊？！！('Д')",
                    color=discord.Color.blue()
                )
                await ctx.reply(embed=embed, mention_author=False)
                return

            # キャラクターIDを使用してスクリーンショットを取得
            # 対象URL: https://jp.tomestone.gg/character/{char_id}/{name_slug}
            screenshot_path = await self.capture_screenshot(char_id, name_slug)

        # Embedメッセージを作成し、キャラクター情報を表示
        embed = discord.Embed(
            title="こいつだろ～？！",
            description=f"サーバー: {server}\n名前: {full_name}",
            color=discord.Color.blue()
        )

        # スクリーンショットファイルを添付
        file = discord.File(screenshot_path, filename="lodestone.png")

        # Embed内で添付ファイルを画像として参照
        embed.set_image(url="attachment://lodestone.png")

        # Embedと添付ファイルを返信として送信
        await ctx.reply(embed=embed, file=file, mention_author=False)


async def setup(bot: commands.Bot):
    """
    このCogをBotに登録するためのセットアップ関数。
    """
    await bot.add_cog(SearchCog(bot))
    print("SearchCog loaded.")
