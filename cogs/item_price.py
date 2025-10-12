# cogs/items_price_cog.py
import discord
from discord.ext import commands
import os
import json
import requests
from bs4 import BeautifulSoup


# プロジェクトルートに対する相対パスからファイルパスを解決する
BASE_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
ITEMS_FILE = os.path.join(BASE_DIR, "tradable_items.json")


class ItemCog(commands.Cog):
    """
    アイテムの価格情報を取得するためのCogクラス。
    JSONファイルからアイテム情報を読み込み、該当するアイテムのリンクを取得し、
    価格情報をDiscordに送信する。
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

    def find_item_by_name(self, search_value):
        """
        指定されたアイテム名（日本語または英語）と一致するアイテムを検索する。
        完全一致を優先し、見つからない場合は部分一致を返す。

        Parameters:
            search_value (str): 検索対象のアイテム名。

        Returns:
            tuple: (match_type, results)
                - match_type: "exact" (完全一致), "partial" (部分一致), "none" (見つからない)
                - results: 
                    - exact: (item_id, item_name_jp, item_name_en)
                    - partial: [(item_id, item_name_jp, item_name_en), ...]
                    - none: None
        """
        if not self.items:
            return "none", None

        search_lower = search_value.lower()
        
        # 完全一致を優先
        for item_id, details in self.items.items():
            item_jp = details.get("item_jp", "")
            item_en = details.get("item_en", "")
            
            if item_jp == search_value or item_en.lower() == search_lower:
                return "exact", (item_id, item_jp, item_en)
        
        # 部分一致を検索
        matches = []
        for item_id, details in self.items.items():
            item_jp = details.get("item_jp", "")
            item_en = details.get("item_en", "")
            
            if search_value in item_jp or search_lower in item_en.lower():
                matches.append((item_id, item_jp, item_en))
        
        if matches:
            return "partial", matches
        
        return "none", None

    def format_number(self, num_str):
        """
        数字文字列にカンマ区切りを追加する

        Parameters:
            num_str (str): 数字の文字列

        Returns:
            str: カンマ区切りされた数字文字列
        """
        try:
            # カンマを削除して数値に変換
            num = int(num_str.replace(",", ""))
            # カンマ区切りで返す
            return f"{num:,}"
        except:
            return num_str

    async def show_price_info(self, ctx, item_id, item_jp, item_en):
        """
        アイテムの価格情報を取得して表示する

        Parameters:
            ctx: コマンドコンテキスト
            item_id: アイテムID
            item_jp: アイテム名（日本語）
            item_en: アイテム名（英語）
        """
        item_page = f"https://universalis.app/market/{item_id}"
        item_img = f"https://universalis-ffxiv.github.io/universalis-assets/icon2x/{item_id}.png"

        try:
            # リクエストの設定
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

            cookies = {
                "mogboard_last_selected_server": "Japan",
                "mogboard_language": "ja",
                "includeGst": "no",
                "mogboard_homeworld": "no",
                "mogboard_server": "Atomos",
                "mogboard_timezone": "Asia%2FTokyo"
            }

            # ページのHTMLを取得
            response = requests.get(item_page, headers=headers, cookies=cookies, timeout=10)
            response.raise_for_status()

            # BeautifulSoupでHTMLを解析
            soup = BeautifulSoup(response.content, "html.parser")

            # "Mat"列を含むテーブルを探す
            target_table = None
            for table in soup.find_all('table'):
                for cell in table.find_all('th'):
                    if cell.text.strip() == "Mat":
                        target_table = table
                        break
                if target_table:
                    break

            if not target_table:
                embed = discord.Embed(
                    title=f"📊 {item_jp}",
                    description="このアイテムの価格情報が見つかりませんでした。",
                    color=discord.Color.orange(),
                    url=item_page
                )
                embed.set_thumbnail(url=item_img)
                embed.add_field(
                    name="ℹ️ 情報",
                    value="マーケットボードに出品されていない可能性があります。",
                    inline=False
                )
                await ctx.reply(embed=embed, mention_author=False)
                return

            # テーブルの内容を抽出（最初の15行）
            table_rows = []
            for i, row in enumerate(target_table.find_all('tr')[1:]):  # ヘッダー行をスキップ
                if i >= 15:
                    break
                
                cells = row.find_all('td')
                if len(cells) < 8:
                    continue
                
                # 必要なデータを抽出
                try:
                    server = cells[1].text.strip()[:5]  # サーバー名（最大5文字）
                    dc = cells[2].text.strip()[:5]  # DC名（最大5文字）
                    price = self.format_number(cells[5].text.strip())  # 価格
                    quantity = cells[6].text.strip()  # 数量
                    total = self.format_number(cells[7].text.strip())  # 合計金額
                    
                    table_rows.append({
                        "server": server,
                        "dc": dc,
                        "price": price,
                        "quantity": quantity,
                        "total": total
                    })
                except (IndexError, AttributeError):
                    continue

            if not table_rows:
                embed = discord.Embed(
                    title=f"📊 {item_jp}",
                    description="価格データが見つかりませんでした。",
                    color=discord.Color.orange(),
                    url=item_page
                )
                embed.set_thumbnail(url=item_img)
                await ctx.reply(embed=embed, mention_author=False)
                return

            # Embedを作成
            embed = discord.Embed(
                title=f"💰 {item_jp}",
                description=f"*{item_en}*",
                color=discord.Color.gold(),
                url=item_page
            )
            embed.set_thumbnail(url=item_img)

            # テーブルを整形
            # 各列の最大幅を計算
            max_widths = {
                "server": max(len(row["server"]) for row in table_rows),
                "dc": max(len(row["dc"]) for row in table_rows),
                "price": max(len(row["price"]) for row in table_rows),
                "quantity": max(len(row["quantity"]) for row in table_rows),
                "total": max(len(row["total"]) for row in table_rows)
            }
            
            # ヘッダーの幅も考慮
            headers = {"server": "鯖", "dc": "DC", "price": "価格", "quantity": "量", "total": "合計"}
            for key in max_widths:
                max_widths[key] = max(max_widths[key], len(headers[key]))

            # テーブルを構築
            table_lines = []
            
            # ヘッダー行
            header_line = (
                f"{headers['server']:<{max_widths['server']}} | "
                f"{headers['dc']:<{max_widths['dc']}} | "
                f"{headers['price']:>{max_widths['price']}} | "
                f"{headers['quantity']:>{max_widths['quantity']}} | "
                f"{headers['total']:>{max_widths['total']}}"
            )
            table_lines.append(header_line)
            table_lines.append("-" * len(header_line))
            
            # データ行
            for row in table_rows:
                line = (
                    f"{row['server']:<{max_widths['server']}} | "
                    f"{row['dc']:<{max_widths['dc']}} | "
                    f"{row['price']:>{max_widths['price']}} | "
                    f"{row['quantity']:>{max_widths['quantity']}} | "
                    f"{row['total']:>{max_widths['total']}}"
                )
                table_lines.append(line)

            table_text = "\n".join(table_lines)
            
            embed.add_field(
                name="📈 マーケット価格（最安値順）",
                value=f"```\n{table_text}\n```",
                inline=False
            )
            
            # 最安値情報を追加
            lowest = table_rows[0]
            embed.add_field(
                name="🏆 最安値",
                value=f"**{lowest['price']}** Gil ({lowest['server']})",
                inline=True
            )
            
            # 統計情報を追加（上位5件の平均）
            top5_prices = [int(row['price'].replace(',', '')) for row in table_rows[:5]]
            avg_price = sum(top5_prices) // len(top5_prices)
            embed.add_field(
                name="📊 平均価格（上位5件）",
                value=f"**{avg_price:,}** Gil",
                inline=True
            )

            embed.set_footer(text="データ提供: Universalis")

            await ctx.reply(embed=embed, mention_author=False)

        except requests.exceptions.Timeout:
            await ctx.reply("⏱️ リクエストがタイムアウトしました。もう一度お試しください。", mention_author=False)
        except requests.exceptions.RequestException as e:
            await ctx.reply(f"❌ ネットワークエラーが発生しました: {e}", mention_author=False)
        except Exception as e:
            await ctx.reply(f"❌ エラーが発生しました: {e}", mention_author=False)
            print(f"Error in show_price_info: {e}")

    @commands.command(name="item", aliases=["i", "価格"])
    async def item_price(self, ctx: commands.Context, *, item: str = None):
        """
        アイテムの価格情報を取得します
        Usage: !item <アイテム名>
        Aliases: !i, !価格
        """
        # アイテム名が指定されていない場合
        if not item:
            embed = discord.Embed(
                title="❓ 使い方",
                description="アイテムの価格を調べます",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="コマンド形式",
                value="`!item <アイテム名>`\n`!i <アイテム名>`\n`!価格 <アイテム名>`",
                inline=False
            )
            embed.add_field(
                name="例",
                value="`!item アイスシャード`\n`!i Ice Shard`\n`!i アイス` (部分一致)",
                inline=False
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        # 指定されたアイテム名から検索
        match_type, results = self.find_item_by_name(item)
        
        # 完全一致の場合
        if match_type == "exact":
            item_id, item_jp, item_en = results
            async with ctx.typing():
                await self.show_price_info(ctx, item_id, item_jp, item_en)
            return
        
        # 部分一致の場合
        elif match_type == "partial":
            # 候補が多すぎる場合は上位20件のみ表示
            max_display = 20
            display_results = results[:max_display]
            
            embed = discord.Embed(
                title="🔍 複数のアイテムが見つかりました",
                description=f"「{item}」に一致するアイテムが**{len(results)}件**見つかりました。\n以下から選択してください。",
                color=discord.Color.blue()
            )
            
            # 候補をリストアップ
            candidate_list = []
            for i, (item_id, item_jp, item_en) in enumerate(display_results, 1):
                # 日本語名と英語名の両方を表示
                if item_jp and item_en and item_jp != item_en:
                    candidate_list.append(f"`{i}.` **{item_jp}** ({item_en})")
                elif item_jp:
                    candidate_list.append(f"`{i}.` **{item_jp}**")
                else:
                    candidate_list.append(f"`{i}.` **{item_en}**")
            
            # 候補リストを分割して表示（Embedのフィールド制限対策）
            chunk_size = 10
            for i in range(0, len(candidate_list), chunk_size):
                chunk = candidate_list[i:i + chunk_size]
                field_name = f"候補アイテム ({i+1}～{min(i+chunk_size, len(candidate_list))})"
                embed.add_field(
                    name=field_name,
                    value="\n".join(chunk),
                    inline=False
                )
            
            if len(results) > max_display:
                embed.add_field(
                    name="ℹ️ 注意",
                    value=f"候補が多いため、上位{max_display}件のみ表示しています。\nより具体的な名前で検索してください。",
                    inline=False
                )
            
            embed.add_field(
                name="💡 ヒント",
                value="完全なアイテム名で再度検索してください。\n例: `!item アイスシャード`",
                inline=False
            )
            
            embed.set_footer(text=f"検索ワード: {item}")
            
            await ctx.reply(embed=embed, mention_author=False)
            return
        
        # 見つからない場合
        else:
            embed = discord.Embed(
                title="❌ アイテムが見つかりません",
                description=f"「{item}」というアイテムは見つかりませんでした。",
                color=discord.Color.red()
            )
            embed.add_field(
                name="ヒント",
                value="• 取引可能なアイテムのみ検索できます\n• 日本語または英語で検索できます\n• スペルミスがないか確認してください\n• 部分一致でも検索できます（例: `!i アイス`）",
                inline=False
            )
            await ctx.reply(embed=embed, mention_author=False)
            return


async def setup(bot: commands.Bot):
    """
    このCogをBotに登録するためのセットアップ関数。
    Botの拡張機能としてこのItemCogを追加する。
    """
    await bot.add_cog(ItemCog(bot))
    print("ItemCog loaded.")