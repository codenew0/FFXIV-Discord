# cogs/items_price_cog.py
import discord
from discord.ext import commands
import os
import json
from playwright.async_api import async_playwright

# Resolve the file path relative to your project root.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
ITEMS_FILE = os.path.join(BASE_DIR, "tradable_items.json")

class ItemCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.items = self.load_items()

    def load_items(self):
        try:
            with open(ITEMS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def find_link_by_item_jp(self, search_value):
        """
        指定された JSON ファイルを読み込み、引数 search_value と一致する item_jp を持つアイテムのリンクを返す。
        見つからなければ None を返す。

        Parameters:
            search_value (str): 検索する日本語のアイテム名（例："アイスシャード"）。

        Returns:
            str or None: 一致する場合は対応するリンク、見つからなければ None。
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
                Search for the price of item
        """
        if not item:
            await ctx.reply("Error: Incorrect input format. Use `!itemp item's name`", mention_author=False)
            return

        item_n = self.find_link_by_item_jp(item)
        if not item_n:
            await ctx.reply("Cannot find the item", mention_author=False)
            return

        # Search Lodestone for the user's character using full name and server
        async with ctx.typing():
            item_page = f"https://universalis.app/market/{item_n}"
            item_img = f"https://universalis-ffxiv.github.io/universalis-assets/icon2x/{item_n}.png"
            item_path = "item.png"
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)

                # 新しいブラウザコンテキストを作成
                context = await browser.new_context()

                # 追加する cookie の定義（domain や path はアクセスするサイトに合わせる必要があります）
                cookies = [
                    {
                        "name": "mogboard_last_selected_server",
                        "value": "Japan",
                        "domain": "universalis.app",  # 対象ドメイン（実際にアクセスするサイトに合わせる）
                        "path": "/"  # 適用するパス
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
                        "domain": "universalis.app",  # 対象ドメイン（実際にアクセスするサイトに合わせる）
                        "path": "/"  # 適用するパス
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
                        "domain": "universalis.app",  # 対象ドメイン（実際にアクセスするサイトに合わせる）
                        "path": "/"  # 適用するパス
                    },
                    {
                        "name": "mogboard_timezone",
                        "value": "Asia%2FTokyo",
                        "domain": "universalis.app",
                        "path": "/"
                    }
                ]

                # cookie をコンテキストに追加
                await context.add_cookies(cookies)

                page = await context.new_page()
                # await page.set_viewport_size({"width": 1280, "height": 2300})
                await page.goto(item_page)

                html_content = await page.content()
                with open("ja.txt", "w", encoding="utf-8") as f:
                    f.write(html_content)

                element = await page.query_selector('div[class="tab"]')

                # union領域をclipパラメータとして指定し、スクリーンショットを取得
                await element.screenshot(path=item_path)

                await browser.close()

        # Create an Embed
        embed = discord.Embed(
            title=f"{item}",
            color=discord.Color.blue()
        )

        # Attach the screenshot file
        file = discord.File(item_path, filename="item.png")
        embed.set_thumbnail(url=item_img)

        # Reference the attached file in the embed
        embed.set_image(url="attachment://item.png")

        # Send the embed with the file
        await ctx.reply(embed=embed, file=file, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(ItemCog(bot))
    print("ItemCog loaded.")
