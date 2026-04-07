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

    def reload_items(self):
        """
        アイテムデータを再読み込みする関数。
        他のCogから呼び出されることを想定。
        """
        self.items = self.load_items()
        return len(self.items)

    @commands.command(name="item_reload")
    @commands.has_permissions(administrator=True)
    async def reload_items_command(self, ctx: commands.Context):
        """
        アイテムデータを再読み込みします
        Usage: !item_reload
        Aliases: !reload
        """
        try:
            count = self.reload_items()
            embed = discord.Embed(
                title="✅ アイテムデータ再読み込み完了",
                description=f"合計 **{count}件** のアイテムを読み込みました。",
                color=discord.Color.green()
            )
            await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            await ctx.reply(f"❌ 再読み込み中にエラーが発生しました: {e}", mention_author=False)

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

    def get_display_width(self, text):
        """文字列の表示幅を計算（日本語は2、英数字は1としてカウント）"""
        width = 0
        for char in text:
            if ord(char) > 127:  # 日本語などの全角文字
                width += 2
            else:  # 英数字などの半角文字
                width += 1
        return width

    def pad_text(self, text, width):
        """テキストを指定した表示幅にパディング"""
        current_width = self.get_display_width(text)
        padding = width - current_width
        return text + " " * padding

    def shorten_text(self, text, max_length=4):
        """
        テキストを指定した長さに短縮する

        Parameters:
            text (str): 短縮するテキスト
            max_length (int): 最大文字数

        Returns:
            str: 短縮されたテキスト
        """
        if len(text) <= max_length:
            return text
        return text[:max_length]

    def shorten_update_time(self, time_str):
        """
        更新時間を短縮形式に変換
        例: "3 hours ago" -> "3h", "2 days ago" -> "2d", "last week" -> "1w"

        Parameters:
            time_str (str): 更新時間の文字列

        Returns:
            str: 短縮された更新時間
        """
        time_str = time_str.lower().strip()

        # 「ago」を削除
        time_str = time_str.replace(" ago", "")

        # 各単位に対応
        if "hour" in time_str:
            # "3 hours" -> "3h"
            if "an " in time_str:
                return "1h"
            num = time_str.split()[0]
            return f"{num}h"
        elif "day" in time_str:
            # "2 days" -> "2d"
            if "yesterday" in time_str:
                return "1d"
            num = time_str.split()[0]
            return f"{num}d"
        elif "week" in time_str:
            # "last week" or "1 week" -> "1w"
            if "last" in time_str or "one" in time_str:
                return "1w"
            num = time_str.split()[0]
            return f"{num}w"
        elif "month" in time_str:
            # "1 month" -> "1mo"
            if "last" in time_str or "one" in time_str:
                return "1mo"
            num = time_str.split()[0]
            return f"{num}mo"
        elif "year" in time_str:
            # "last year" or "one year" -> "1y"
            if "last" in time_str or "one" in time_str:
                return "1y"
            num = time_str.split()[0]
            return f"{num}y"
        elif "minute" in time_str:
            # "30 minutes" -> "30m"
            num = time_str.split()[0]
            return f"{num}m"
        else:
            return time_str[:4]  # デフォルトは4文字

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

            # region_update_timesからサーバごとの更新時間を取得
            update_times_dict = {}
            update_times_container = soup.find('div', class_='region_update_times')
            if update_times_container:
                # h4タグ（サーバ名）を探す
                for h4 in update_times_container.find_all('h4'):
                    server_name = h4.text.strip()
                    # h4の親divから次のdivを取得
                    parent_div = h4.parent
                    time_div = parent_div.find('div')
                    if time_div:
                        update_time = time_div.text.strip()
                        # 更新時間を短縮形式に変換
                        update_time = self.shorten_update_time(update_time)
                        update_times_dict[server_name] = update_time

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
                    server_full = cells[1].text.strip()  # サーバー名（フル）
                    server = self.shorten_text(server_full, 4)  # サーバー名（4文字）
                    dc_full = cells[2].text.strip()  # DC名（フル）
                    dc = self.shorten_text(dc_full, 4)  # DC名（4文字）
                    price = self.format_number(cells[5].text.strip())  # 価格
                    quantity = cells[6].text.strip()  # 数量
                    total = self.format_number(cells[7].text.strip())  # 合計金額

                    # 更新時間を取得
                    update_time = update_times_dict.get(server_full, "")

                    table_rows.append({
                        "server": server,
                        "dc": dc,
                        "price": price,
                        "quantity": quantity,
                        "total": total,
                        "update_time": update_time
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
            # 各列の最大幅を計算（日本語文字を考慮）
            max_widths = {
                "server": max(self.get_display_width(row["server"]) for row in table_rows),
                "dc": max(self.get_display_width(row["dc"]) for row in table_rows),
                "price": max(self.get_display_width(row["price"]) for row in table_rows),
                "quantity": max(self.get_display_width(row["quantity"]) for row in table_rows),
                "total": max(self.get_display_width(row["total"]) for row in table_rows),
                "update_time": max((self.get_display_width(row["update_time"]) for row in table_rows), default=0)
            }

            # ヘッダーの幅も考慮
            headers_dict = {"server": "鯖", "dc": "DC", "price": "価格", "quantity": "量", "total": "合計", "update_time": "更新"}
            for key in max_widths:
                max_widths[key] = max(max_widths[key], self.get_display_width(headers_dict[key]))

            # テーブルを構築
            table_lines = []

            # ヘッダー行（日本語の表示幅を考慮してパディング）
            header_line = (
                f"{self.pad_text(headers_dict['server'], max_widths['server'])} | "
                f"{self.pad_text(headers_dict['dc'], max_widths['dc'])} | "
                f"{self.pad_text(headers_dict['price'], max_widths['price'])} | "
                f"{self.pad_text(headers_dict['quantity'], max_widths['quantity'])} | "
                f"{self.pad_text(headers_dict['total'], max_widths['total'])} | "
                f"{self.pad_text(headers_dict['update_time'], max_widths['update_time'])}"
            )
            table_lines.append(header_line)
            table_lines.append("-" * self.get_display_width(header_line))

            # データ行
            for row in table_rows:
                line = (
                    f"{self.pad_text(row['server'], max_widths['server'])} | "
                    f"{self.pad_text(row['dc'], max_widths['dc'])} | "
                    f"{self.pad_text(row['price'], max_widths['price'])} | "
                    f"{self.pad_text(row['quantity'], max_widths['quantity'])} | "
                    f"{self.pad_text(row['total'], max_widths['total'])} | "
                    f"{self.pad_text(row['update_time'], max_widths['update_time'])}"
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
            # 候補が1つだけの場合は自動的に表示
            if len(results) == 1:
                item_id, item_jp, item_en = results[0]
                # 部分一致で見つかったことを示すメッセージを送信
                info_msg = await ctx.send(f"🔍 「{item}」→「**{item_jp}**」の価格情報を取得中...")
                async with ctx.typing():
                    await self.show_price_info(ctx, item_id, item_jp, item_en)
                # 情報メッセージを削除
                try:
                    await info_msg.delete()
                except:
                    pass
                return

            # 候補が複数ある場合はリスト表示
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
                field_name = f"候補アイテム ({i + 1}～{min(i + chunk_size, len(candidate_list))})"
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