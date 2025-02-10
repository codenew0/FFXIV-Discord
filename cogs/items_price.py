# cogs/items_price_cog.py
import discord
from discord.ext import commands
import os
import json
from playwright.async_api import async_playwright

# プロジェクトルートに対する相対パスからファイルパスを解決する
BASE_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
ITEMS_FILE = os.path.join(BASE_DIR, "tradable_items.json")


class ItemCog(commands.Cog):
    """
    アイテムの価格情報を取得するためのCogクラス。
    JSONファイルからアイテム情報を読み込み、該当するアイテムのリンクを取得し、
    そのページのスクリーンショットをDiscordに送信する。
    """

    def __init__(self, bot: commands.Bot):
        """
        コンストラクタ。
        Botのインスタンスを受け取り、アイテム情報の読み込みを行う。
        """
        self.bot = bot
        self.items = self.load_items()

    def load_items(self):
        """
        tradable_items.jsonファイルからアイテム情報を読み込む関数。

        Returns:
            dict: 読み込んだアイテム情報。ファイルが存在しないか、JSONの形式に誤りがある場合は空の辞書を返す。
        """
        try:
            with open(ITEMS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def find_link_by_item_jp(self, search_value):
        """
        指定された日本語のアイテム名(search_value)と一致するアイテムのリンクを、
        読み込んだJSONファイルから検索して返す関数。

        Parameters:
            search_value (str): 検索対象の日本語のアイテム名（例："アイスシャード"）。

        Returns:
            str or None: 一致するアイテムのリンクを返す。見つからなければNoneを返す。
        """
        if not self.items:
            return None

        for item_n, details in self.items.items():
            if details.get("item_jp") == search_value:
                return item_n
        return None

    @commands.command(name="item")
    async def item_price(self, ctx: commands.Context, *, item):
        """
        いくらになったの？！（アイテムの価格情報を取る）
        Usage: !item <アイテム名>
        """
        # アイテム名が指定されていない場合はエラーメッセージを送信
        if not item:
            await ctx.reply("フォーマットがちがうよ！！ `!item アイテム名`にしてくれ", mention_author=False)
            return

        # 指定された日本語のアイテム名からリンクを取得
        item_n = self.find_link_by_item_jp(item)
        if not item_n:
            await ctx.reply("アイテム見つからないぞ！取引できるアイテムしか検索できない", mention_author=False)
            return

        # 対象のアイテムページと画像URL、スクリーンショットの保存先を定義
        async with ctx.typing():
            item_page = f"https://universalis.app/market/{item_n}"
            item_img = f"https://universalis-ffxiv.github.io/universalis-assets/icon2x/{item_n}.png"
            item_path = "item.png"

            # Playwrightを使用して対象ページのスクリーンショットを取得する
            async with async_playwright() as p:
                # ヘッドレスモードでChromiumブラウザを起動
                browser = await p.chromium.launch(headless=True)

                # 新しいブラウザコンテキストを作成
                context = await browser.new_context()

                # 対象サイト（universalis.app）に必要なCookieを定義して追加する
                cookies = [
                    {
                        "name": "mogboard_last_selected_server",
                        "value": "Japan",
                        "domain": "universalis.app",  # 対象ドメインに合わせる
                        "path": "/"  # 適用パス
                    },
                    {
                        "name": "mogboard_language",
                        "value": "ja",
                        "domain": "universalis.app",
                        "path": "/"
                    },
                    {
                        "name": "includeGst",
                        "value": "no",
                        "domain": "universalis.app",
                        "path": "/"
                    },
                    {
                        "name": "mogboard_homeworld",
                        "value": "no",
                        "domain": "universalis.app",
                        "path": "/"
                    },
                    {
                        "name": "mogboard_server",
                        "value": "Atomos",
                        "domain": "universalis.app",
                        "path": "/"
                    },
                    {
                        "name": "mogboard_timezone",
                        "value": "Asia%2FTokyo",
                        "domain": "universalis.app",
                        "path": "/"
                    }
                ]
                # Cookieをブラウザコンテキストに追加
                await context.add_cookies(cookies)

                # 新しいページ（タブ）を作成し、アイテムページにアクセス
                page = await context.new_page()
                await page.goto(item_page)

                # 'div'要素のうち、class属性が"tab"の部分を取得
                element = await page.query_selector('div[class="tab"]')

                # 指定した領域(element)のスクリーンショットを取得し、保存する
                await element.screenshot(path=item_path)

                # ブラウザを閉じる
                await browser.close()

        # DiscordのEmbedを作成
        embed = discord.Embed(
            title=f"{item}",
            color=discord.Color.blue()
        )

        # 取得したスクリーンショットファイルを添付
        file = discord.File(item_path, filename="item.png")
        # アイテムの画像をサムネイルとして設定
        embed.set_thumbnail(url=item_img)
        # 添付したスクリーンショットをEmbed内に表示
        embed.set_image(url="attachment://item.png")

        # 作成したEmbedとファイルを返信として送信
        await ctx.reply(embed=embed, file=file, mention_author=False)


async def setup(bot: commands.Bot):
    """
    このCogをBotに登録するためのセットアップ関数。
    Botの拡張機能としてこのItemCogを追加する。
    """
    await bot.add_cog(ItemCog(bot))
    print("ItemCog loaded.")
