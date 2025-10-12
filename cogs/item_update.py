# cogs/item_update_cog.py
import discord
from discord.ext import commands
import requests
from bs4 import BeautifulSoup
import json
import re
import os
import asyncio
import aiohttp

BASE_URL = "https://universalis.app"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
JSON_FILE = os.path.join(BASE_DIR, "tradable_items.json")


class ItemUpdateCog(commands.Cog):
    """
    アイテムデータベースを更新するためのCogクラス。
    サイトから新しいアイテムを取得し、JSONファイルに追加する。
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_item_links(self):
        """
        https://universalis.app/items にアクセスし、
        全てのアイテムリンクを取得する
        """
        url = BASE_URL + "/items"
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = {}
        for li in soup.find_all("li"):
            a_tag = li.find("a", href=True)
            if a_tag:
                href = a_tag['href']
                match = re.match(r"^/market/(.+)$", href)
                if match:
                    item_n = match.group(1)
                    full_link = BASE_URL + href
                    links[item_n] = full_link
        return links

    def load_existing_items(self):
        """
        既存のJSONファイルからアイテムデータを読み込む
        """
        if os.path.exists(JSON_FILE):
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def extract_title(self, text):
        """
        タイトル文字列から " - Universalis" の前の部分を抽出する
        """
        return text.split(" - Universalis")[0].strip()

    async def get_item_en(self, session, url):
        """
        非同期でページを取得し、titleタグから item_en を抽出する
        """
        async with session.get(url) as response:
            text = await response.text()
            soup = BeautifulSoup(text, 'html.parser')
            title_tag = soup.find("title")
            if title_tag:
                return self.extract_title(title_tag.text)
            return ""

    async def get_item_jp(self, session, url):
        """
        日本語Cookieを設定してページを取得し、titleタグから item_jp を抽出する
        """
        cookies = {'mogboard_language': 'ja', 'mogboard_last_selected_server': 'Japan'}
        async with session.get(url, cookies=cookies) as response:
            text = await response.text()
            soup = BeautifulSoup(text, 'html.parser')
            title_tag = soup.find("title")
            if title_tag:
                return self.extract_title(title_tag.text)
            return ""

    async def process_new_item(self, session, item_n, url, progress_msg, current, total):
        """
        新しいアイテムを処理し、英語・日本語のタイトルを取得
        """
        try:
            item_en = await self.get_item_en(session, url)
            item_jp = await self.get_item_jp(session, url)
            
            # 進捗を更新（5件ごと）
            if current % 5 == 0:
                await progress_msg.edit(content=f"🔄 アイテム更新中... ({current}/{total})")
            
            return {
                "link": url,
                "item_en": item_en,
                "item_jp": item_jp
            }
        except Exception as e:
            print(f"Error processing {item_n}: {e}")
            return None

    @commands.command(name="item_update")
    @commands.has_permissions(administrator=True)  # 管理者のみ実行可能
    async def item_update(self, ctx: commands.Context):
        """
        アイテムデータベースを更新する
        Usage: !item_update
        """
        # 初期メッセージを送信
        status_msg = await ctx.reply("🔍 アイテム情報を確認中...", mention_author=False)

        try:
            # 既存のアイテムを読み込み
            existing_items = self.load_existing_items()
            existing_count = len(existing_items)

            # サイトから全アイテムリンクを取得
            await status_msg.edit(content="🌐 サイトからアイテムリストを取得中...")
            item_links = self.get_item_links()
            site_count = len(item_links)

            # 新しいアイテムを特定
            new_items = {k: v for k, v in item_links.items() if k not in existing_items}
            new_count = len(new_items)

            # 結果を報告
            embed = discord.Embed(
                title="📊 アイテムデータベース状況",
                color=discord.Color.blue()
            )
            embed.add_field(name="現在のアイテム数", value=f"{existing_count}件", inline=True)
            embed.add_field(name="サイトのアイテム数", value=f"{site_count}件", inline=True)
            embed.add_field(name="新規アイテム数", value=f"{new_count}件", inline=True)

            if new_count == 0:
                embed.description = "✅ データベースは最新です！"
                embed.color = discord.Color.green()
                await status_msg.edit(content=None, embed=embed)
                return

            # 新しいアイテムを追加
            embed.description = "🔄 新しいアイテムを追加します..."
            embed.color = discord.Color.orange()
            await status_msg.edit(content=None, embed=embed)

            # 非同期セッションで処理
            async with aiohttp.ClientSession() as session:
                progress_msg = await ctx.send(f"🔄 アイテム更新中... (0/{new_count})")
                
                tasks = []
                current = 0
                
                # 新しいアイテムを処理（同時に10件まで）
                semaphore = asyncio.Semaphore(10)
                
                async def process_with_semaphore(item_n, url, idx):
                    async with semaphore:
                        return item_n, await self.process_new_item(
                            session, item_n, url, progress_msg, idx + 1, new_count
                        )
                
                # 全タスクを作成
                tasks = [
                    process_with_semaphore(item_n, url, idx)
                    for idx, (item_n, url) in enumerate(new_items.items())
                ]
                
                # 全タスクを実行
                results = await asyncio.gather(*tasks)
                
                # 結果を統合
                for item_n, item_data in results:
                    if item_data:
                        existing_items[item_n] = item_data

            # JSONファイルを保存（item_n順にソート）
            sorted_items = dict(sorted(existing_items.items(), key=lambda x: int(x[0])))
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(sorted_items, f, ensure_ascii=False, indent=4)

            # 完了メッセージ
            final_embed = discord.Embed(
                title="✅ アイテムデータベース更新完了",
                description=f"{new_count}件の新しいアイテムを追加しました！",
                color=discord.Color.green()
            )
            final_embed.add_field(name="更新後のアイテム数", value=f"{len(sorted_items)}件", inline=True)
            
            await progress_msg.delete()
            await status_msg.edit(content=None, embed=final_embed)

        except requests.exceptions.RequestException as e:
            await status_msg.edit(content=f"❌ リクエストエラーが発生しました: {e}")
        except Exception as e:
            await status_msg.edit(content=f"❌ エラーが発生しました: {e}")

    @item_update.error
    async def item_update_error(self, ctx: commands.Context, error):
        """
        エラーハンドリング
        """
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("❌ このコマンドは管理者のみ実行できます。", mention_author=False)
        else:
            await ctx.reply(f"❌ エラーが発生しました: {error}", mention_author=False)


async def setup(bot: commands.Bot):
    """
    このCogをBotに登録するためのセットアップ関数
    """
    await bot.add_cog(ItemUpdateCog(bot))
    print("ItemUpdateCog loaded.")