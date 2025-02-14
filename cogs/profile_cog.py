# cogs/profile_cog.py
import os
import json
from discord.ext import commands
import discord
from cogs.base_cog import BaseCog

# プロジェクトルートに対する相対パスからユーザープロフィールのJSONファイルのパスを解決する
BASE_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
USER_PROFILES_FILE = os.path.join(BASE_DIR, "usernames.json")


class ProfileCog(BaseCog):
    """
    ユーザーのプロフィールを管理するCogクラス。
    プロフィールは以下の形式で保存されます:
    { user_id: {"server": サーバー名, "first": 名, "last": 姓} }
    """

    def __init__(self, bot: commands.Bot):
        """
        コンストラクタ。
        Botのインスタンスを受け取り、ユーザープロフィールの読み込みを行います。
        """
        self.bot = bot
        self.profiles = self.load_profiles()

    def load_profiles(self):
        """
        ユーザープロフィールを保存したJSONファイル(USER_PROFILES_FILE)を読み込む関数。

        Returns:
            dict: 読み込んだプロフィールの辞書。ファイルが存在しないか、JSONの形式エラーの場合は空の辞書を返す。
        """
        try:
            with open(USER_PROFILES_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_profiles(self, profiles):
        """
        プロフィールの辞書をJSONファイル(USER_PROFILES_FILE)に保存する関数。

        Parameters:
            profiles (dict): 保存するプロフィールの辞書。
        """
        with open(USER_PROFILES_FILE, "w") as f:
            json.dump(profiles, f, indent=4)

    @commands.command(name="iam")
    async def iam(self, ctx: commands.Context, server: str = None, first: str = None, last: str = None):
        """
        私は・・（自分のプロフィールをリンク）
        Usage: !iam <server> <first> <last>
        """
        # 入力が不足している場合、エラーメッセージを送信
        if not server or not first or not last:
            embed = discord.Embed(
                title="てめぇ、フォーマットわからんの？ \n `!iam server first last`で入力してくれや！",
                color=discord.Color.blue()
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        server = server.capitalize()
        first = first.capitalize()
        last = last.capitalize()

        # プロフィール情報を辞書形式で作成
        profile = {
            "server": server,
            "first": first,
            "last": last
        }

        # ユーザーIDをキーとしてプロフィールを保存
        self.profiles[str(ctx.author.id)] = profile
        full_name = f"{first} {last}"

        # 入力された情報でLodestone上に該当するキャラクターが存在するか検索する
        async with ctx.typing():
            ids = self.lodestone_search(full_name, server)
            if not ids:
                embed = discord.Embed(
                    title="プロフィールがないよ～ふざけんな！",
                    color=discord.Color.blue()
                )
                await ctx.reply(embed=embed, mention_author=False)
                return

            # プロフィールをファイルに保存
            self.save_profiles(self.profiles)

            embed = discord.Embed(
                title="プロフィールが覚えたぞ☆彡",
                description=f"サーバー: {server}\n名前: {first} {last}",
                color=discord.Color.blue()
            )
            await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="whoami")
    async def whoami(self, ctx: commands.Context):
        """
            私はだれだああ～（自分のプロフィールを見る）
        """
        # ユーザーのプロフィールが保存されているか確認
        profile = self.profiles.get(str(ctx.author.id))
        if not profile:
            embed = discord.Embed(
                title="てめぇプロフィールまだ設定してないだろう！ \n`!iam server first last` で設定してくれ！",
                color=discord.Color.blue()
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        # プロフィールから各情報を取得
        server = profile["server"]
        first = profile["first"]
        last = profile["last"]
        full_name = f"{first} {last}"
        # 名前をスラッグ形式に変換（例: "first-last"）
        name_slug = f"{first}-{last}".lower()

        # Lodestoneでキャラクターを検索し、キャラクターIDを取得する
        async with ctx.typing():
            char_id = self.lodestone_search(full_name, server)
            if not char_id:
                embed = discord.Embed(
                    title="Lodestone上でキャラクターが見つかりませんでした！",
                    color=discord.Color.blue()
                )
                await ctx.reply(embed=embed, mention_author=False)
                return
            # キャラクターIDを用いてスクリーンショットを取得する
            screenshot_path = await self.capture_screenshot(char_id, name_slug)

        # 取得したスクリーンショットを含むEmbedメッセージを作成
        embed = discord.Embed(
            title="これてめぇだろ？",
            description=f"サーバー: {server}\n名前: {full_name}",
            color=discord.Color.blue()
        )

        # スクリーンショットファイルを添付
        file = discord.File(screenshot_path, filename="lodestone.png")

        # Embed内に画像を表示するために添付ファイルのURLを設定
        embed.set_image(url="attachment://lodestone.png")

        # Embedとファイルを送信
        await ctx.reply(embed=embed, file=file, mention_author=False)


async def setup(bot: commands.Bot):
    """
    このCogをBotに登録するためのセットアップ関数。
    """
    await bot.add_cog(ProfileCog(bot))
    print("ProfileCog loaded.")
