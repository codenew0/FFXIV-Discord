# cogs/items_price_cog.py
import discord
from discord.ext import commands
import os
import json
from playwright.async_api import async_playwright
import requests
from bs4 import BeautifulSoup

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

        # 対象のアイテムページと画像URLを定義
        async with ctx.typing():
            item_page = f"https://universalis.app/market/{item_n}"
            item_img = f"https://universalis-ffxiv.github.io/universalis-assets/icon2x/{item_n}.png"

            try:
                # User-Agentを設定
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }

                # Cookieを設定 (指定されたCookieを使用)
                cookies = {
                    "mogboard_last_selected_server": "Japan",
                    "mogboard_language": "ja",
                    "includeGst": "no",
                    "mogboard_homeworld": "no",
                    "mogboard_server": "Atomos",
                    "mogboard_timezone": "Asia%2FTokyo"
                }

                # ページのHTMLを取得
                response = requests.get(item_page, headers=headers, cookies=cookies)
                response.raise_for_status()  # HTTPエラーをチェック

                # BeautifulSoupでHTMLを解析
                soup = BeautifulSoup(response.content, "html.parser")

                # "MAT"という文字列が含まれているテーブルを探す
                target_table = None
                for table in soup.find_all('table'):
                    # テーブル内のすべてのセルをチェックし、"MAT" が完全一致で含まれるか確認
                    for cell in table.find_all('th'):
                        if cell.text.strip() == "Mat":  # スペースを削除して比較
                            target_table = table
                            break
                    if target_table:
                        break  # テーブルが見つかったらループを抜ける

                if target_table:
                    # テーブルの内容を整形 (最初の20行のみ取得)
                    table_data = []
                    for i, row in enumerate(target_table.find_all('tr')):
                        if i >= 20:
                            break  # 最初の20行を超えたらループを抜ける
                        row_data = [cell.text.strip() for cell in row.find_all('td')]
                        table_data.append(row_data)

                    # table_dataが空か、すべての行が空の場合、処理をスキップ
                    if not table_data or all(not row for row in table_data):
                        await ctx.reply("MAT情報が見つかりましたが、内容は空です。", mention_author=False)
                        return

                    # DiscordのEmbedを作成
                    embed = discord.Embed(
                        title=f"{item} の価格情報",
                        color=discord.Color.blue(),
                        url=item_page  # アイテムページへのリンクを埋め込む
                    )

                    # アイテムの画像をサムネイルとして設定
                    embed.set_thumbnail(url=item_img)

                    # ヘッダーを定義
                    header = "鯖|ワールド|価格|量|全額"
                    # 各列の最大長を計算
                    column_widths = [len(word) for word in header.split("|")]  # 初期値としてヘッダーの長さを設定

                    table_string = ""
                    for row in table_data:
                        # 行が空の場合、または行のすべてのセルが空/空白の場合、スキップ
                        if not row or all(not cell.strip() for cell in row):
                            continue

                        # 指定された列のデータのみを抽出 (0始まりなので、+1必要)
                        selected_cells = []
                        try:
                            selected_cells.append(row[1])  # 2列目
                            selected_cells.append(row[2])  # 3列目
                            selected_cells.append(row[5])  # 6列目
                            selected_cells.append(row[6])  # 7列目
                            selected_cells.append(row[7])  # 8列目
                        except IndexError:
                            # 行の長さが足りない場合、スキップ
                            continue

                        # 各列の最大長を更新
                        for i, cell in enumerate(selected_cells):
                            column_widths[i] = max(column_widths[i], len(cell))

                        table_string += "|".join(selected_cells) + "\n"  # 各セルを | で区切り、行末に改行を追加

                    # フォーマットされたテーブルを作成
                    formatted_table = ""
                    formatted_header = ""
                    header_cells = header.split("|")
                    for i, width in enumerate(column_widths):
                        formatted_header += header_cells[i].ljust(width) + "|"
                    formatted_table += formatted_header[:-1] + "\n"  # ヘッダーを追加し、最後の "|" を削除

                    lines = table_string.splitlines()
                    for line in lines:
                        formatted_line = ""
                        cells = line.split("|")
                        for i, width in enumerate(column_widths):
                            formatted_line += cells[i].ljust(width) + " | "
                        formatted_table += formatted_line[:-1] + "\n"  # 各行を追加し、最後の "|" を削除
                    if not formatted_table:
                        await ctx.reply("MAT情報が見つかりましたが、内容は空です。", mention_author=False)
                        return

                    embed.add_field(name="情報", value=f"```{formatted_table}```", inline=False)

                    # 作成したEmbedを返信として送信
                    await ctx.reply(embed=embed, mention_author=False)

                else:
                    await ctx.reply("MAT情報が見つかりませんでした。", mention_author=False)

            except requests.exceptions.RequestException as e:
                await ctx.reply(f"リクエストエラーが発生しました: {e}", mention_author=False)
            except Exception as e:
                await ctx.reply(f"エラーが発生しました: {e}", mention_author=False)


async def setup(bot: commands.Bot):
    """
    このCogをBotに登録するためのセットアップ関数。
    Botの拡張機能としてこのItemCogを追加する。
    """
    await bot.add_cog(ItemCog(bot))
    print("ItemCog loaded.")
