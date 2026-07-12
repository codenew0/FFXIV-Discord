# cogs/item_price_cog.py
import asyncio
import time
import discord
from discord.ext import commands
import os
import json
import aiohttp

BASE_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
ITEMS_FILE = os.path.join(BASE_DIR, "tradable_items.json")
WORLDS_FILE = os.path.join(BASE_DIR, "worlds_jp.json")

UNIVERSALIS_API = "https://universalis.app/api/v2"

# JP ワールド → DC マッピング
WORLD_DC: dict[str, str] = {
    # Elemental
    "Aegis": "Elem", "Atomos": "Elem", "Carbuncle": "Elem", "Garuda": "Elem",
    "Gungnir": "Elem", "Kujata": "Elem", "Tonberry": "Elem", "Typhon": "Elem",
    # Gaia
    "Alexander": "Gaia", "Bahamut": "Gaia", "Durandal": "Gaia", "Fenrir": "Gaia",
    "Ifrit": "Gaia", "Ridill": "Gaia", "Tiamat": "Gaia", "Ultima": "Gaia",
    # Mana
    "Anima": "Mana", "Asura": "Mana", "Chocobo": "Mana", "Hades": "Mana",
    "Ixion": "Mana", "Masamune": "Mana", "Pandaemonium": "Mana", "Titan": "Mana",
    # Meteor
    "Belias": "Mete", "Mandragora": "Mete", "Ramuh": "Mete", "Shinryu": "Mete",
    "Unicorn": "Mete", "Valefor": "Mete", "Yojimbo": "Mete", "Zeromus": "Mete",
}

DC_ALIASES: dict[str, str] = {
    "elem": "Elemental",
    "elemental": "Elemental",
    "gaia": "Gaia",
    "mana": "Mana",
    "mete": "Meteor",
    "meteor": "Meteor",
}


class ItemCog(commands.Cog):
    """アイテムの価格情報を Universalis API から取得するCog。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.items = self._load_items()
        self.worlds = self._load_worlds()

    def _load_items(self):
        try:
            with open(ITEMS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _load_worlds(self):
        try:
            with open(WORLDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def reload_items(self):
        self.items = self._load_items()
        return len(self.items)

    @commands.command(name="item_reload")
    @commands.has_permissions(administrator=True)
    async def reload_items_command(self, ctx: commands.Context):
        """アイテムデータを再読み込みします\nUsage: !item_reload"""
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

    # ------------------------------------------------------------------ helpers

    def _normalize_world(self, name: str) -> str | None:
        """大文字小文字を無視してワールド名を正規化。無効な場合は None。"""
        lower = name.lower()
        for w in self.worlds:
            if w.lower() == lower:
                return w
        return None

    def _normalize_dc(self, name: str) -> str | None:
        """DC名/略称をUniversalis APIで使う正式名に正規化。"""
        return DC_ALIASES.get(name.lower())

    def _parse_args(self, args: str) -> tuple[str | None, str, bool]:
        """
        '!i [server|dc] item' を (location, item, is_world) に分割する。
        先頭のトークンが有効なワールド名またはDC名であれば検索対象として扱う。
        """
        parts = args.split(None, 1)
        if len(parts) == 2:
            world = self._normalize_world(parts[0])
            if world:
                return world, parts[1], True
            dc = self._normalize_dc(parts[0])
            if dc:
                return dc, parts[1], False
        return None, args, False

    def _find_item(self, query: str):
        """アイテム名（日本語/英語）で検索。exact / partial / none を返す。"""
        if not self.items:
            return "none", None
        lower = query.lower()
        for item_id, details in self.items.items():
            jp = details.get("item_jp", "")
            en = details.get("item_en", "")
            if jp == query or en.lower() == lower:
                return "exact", (item_id, jp, en)
        matches = [
            (iid, d.get("item_jp", ""), d.get("item_en", ""))
            for iid, d in self.items.items()
            if query in d.get("item_jp", "") or lower in d.get("item_en", "").lower()
        ]
        return ("partial", matches) if matches else ("none", None)

    async def _fetch_listings(self, item_id: str, server: str) -> list[dict]:
        """Universalis API からリスト（最大15件）を非同期取得。失敗時は2回までリトライ。"""
        url = f"{UNIVERSALIS_API}/{server}/{item_id}?listings=15&entries=0"
        timeout = aiohttp.ClientTimeout(total=15)
        last_exc = None

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as resp:
                        resp.raise_for_status()
                        data = await resp.json()
                        return data.get("listings", [])
            except asyncio.TimeoutError as e:
                last_exc = e
                print(f"[item] タイムアウト (試行 {attempt + 1}/3): {url}")
                if attempt < 2:
                    await asyncio.sleep(2)
            except aiohttp.ClientError as e:
                last_exc = e
                print(f"[item] ネットワークエラー (試行 {attempt + 1}/3): {e}")
                if attempt < 2:
                    await asyncio.sleep(2)

        raise last_exc

    @staticmethod
    def _fmt_elapsed(unix_ts: int) -> str:
        """Unix タイムスタンプを '3h' '2d' '1w' などに変換。"""
        elapsed = int(time.time()) - unix_ts
        if elapsed < 3600:
            return f"{elapsed // 60}m"
        if elapsed < 86400:
            return f"{elapsed // 3600}h"
        if elapsed < 604800:
            return f"{elapsed // 86400}d"
        return f"{elapsed // 604800}w"

    @staticmethod
    def _display_width(text: str) -> int:
        return sum(2 if ord(c) > 127 else 1 for c in text)

    def _pad(self, text: str, width: int) -> str:
        return text + " " * (width - self._display_width(text))

    # ------------------------------------------------------------------ display

    async def _show_price(
        self,
        ctx: commands.Context,
        item_id: str,
        item_jp: str,
        item_en: str,
        server: str | None,
        is_world: bool = False,
    ):
        region = server or "Japan"
        item_page = f"https://universalis.app/market/{item_id}"
        item_img = f"https://universalis-ffxiv.github.io/universalis-assets/icon2x/{item_id}.png"

        try:
            listings = await self._fetch_listings(item_id, region)
        except asyncio.TimeoutError:
            await ctx.reply("⏱️ 3回試しましたがタイムアウトしました。しばらく待ってから再試行してください。", mention_author=False)
            return
        except aiohttp.ClientError as e:
            await ctx.reply(f"❌ ネットワークエラー: {e}", mention_author=False)
            return

        if not listings:
            embed = discord.Embed(
                title=f"📊 {item_jp}",
                description="マーケットボードに出品されていないようです。",
                color=discord.Color.orange(),
                url=item_page,
            )
            embed.set_thumbnail(url=item_img)
            await ctx.reply(embed=embed, mention_author=False)
            return

        single_world = server is not None and is_world  # ワールド指定の場合は鯖・DC列不要

        rows = []
        for li in listings:
            price = li.get("pricePerUnit", 0)
            qty = li.get("quantity", 0)
            total = li.get("total", price * qty)
            ts = li.get("lastReviewTime", 0)
            hq = "HQ" if li.get("hq") else "NQ"
            world_full = li.get("worldName") or server or "?"
            world = world_full[:4]
            dc = WORLD_DC.get(world_full, "?")
            rows.append({
                "world": world,
                "dc": dc,
                "hq": hq,
                "price": f"{price:,}",
                "qty": str(qty),
                "total": f"{total:,}",
                "upd": self._fmt_elapsed(ts) if ts else "-",
            })

        # テーブル構築
        if single_world:
            cols = ["hq", "price", "qty", "total", "upd"]
            headers = {"hq": "品質", "price": "価格", "qty": "量", "total": "合計", "upd": "更新"}
        else:
            cols = ["world", "dc", "price", "qty", "total", "upd"]
            headers = {"world": "鯖", "dc": "DC", "price": "価格", "qty": "量", "total": "合計", "upd": "更新"}

        widths = {
            col: max(self._display_width(headers[col]), max(self._display_width(r[col]) for r in rows))
            for col in cols
        }

        def build_line(row_or_header):
            return " | ".join(self._pad(row_or_header[c], widths[c]) for c in cols)

        header_line = build_line(headers)
        lines = [header_line, "-" * self._display_width(header_line)]
        lines += [build_line(r) for r in rows]
        table_text = "\n".join(lines)

        title_server = f" [{server}]" if server else " [Japan]"
        embed = discord.Embed(
            title=f"💰 {item_jp}{title_server}",
            description=f"*{item_en}*",
            color=discord.Color.gold(),
            url=item_page,
        )
        embed.set_thumbnail(url=item_img)
        embed.add_field(
            name="📈 マーケット価格（最安値順）",
            value=f"```\n{table_text}\n```",
            inline=False,
        )

        lowest = rows[0]
        embed.add_field(
            name="🏆 最安値",
            value=f"**{lowest['price']}** Gil",
            inline=True,
        )

        top5 = [int(r["price"].replace(",", "")) for r in rows[:5]]
        embed.add_field(
            name="📊 平均（上位5件）",
            value=f"**{sum(top5) // len(top5):,}** Gil",
            inline=True,
        )
        embed.set_footer(text="データ提供: Universalis")

        await ctx.reply(embed=embed, mention_author=False)

    # ------------------------------------------------------------------ command

    @commands.command(name="item", aliases=["i", "価格"])
    async def item_price(self, ctx: commands.Context, *, args: str = None):
        """
        アイテムの価格情報を取得します
        Usage: !item <アイテム名>
               !i <サーバー> <アイテム名>  ← サーバー指定
               !i <DC> <アイテム名>        ← DC指定
        例:    !i アイスシャード
               !i atomos オーケストリオン譜:鬼の棲む島
               !i elem アイスシャード
        """
        if not args:
            embed = discord.Embed(
                title="❓ 使い方",
                description="アイテムの価格を調べます",
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="コマンド形式",
                value=(
                    "`!item <アイテム名>`\n"
                    "`!i <アイテム名>`\n"
                    "`!i <サーバー> <アイテム名>`\n"
                    "`!i <DC> <アイテム名>`"
                ),
                inline=False,
            )
            embed.add_field(
                name="例",
                value=(
                    "`!i アイスシャード`\n"
                    "`!i Ice Shard`\n"
                    "`!i atomos オーケストリオン譜:鬼の棲む島`\n"
                    "`!i Elem アイスシャード`\n"
                    "`!i Elemental アイスシャード`"
                ),
                inline=False,
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        server, query, is_world = self._parse_args(args)
        match_type, results = self._find_item(query)

        if match_type == "exact":
            item_id, item_jp, item_en = results
            async with ctx.typing():
                await self._show_price(ctx, item_id, item_jp, item_en, server, is_world)

        elif match_type == "partial":
            if len(results) == 1:
                item_id, item_jp, item_en = results[0]
                msg = await ctx.send(f"🔍 「{query}」→「**{item_jp}**」の価格情報を取得中...")
                async with ctx.typing():
                    await self._show_price(ctx, item_id, item_jp, item_en, server, is_world)
                try:
                    await msg.delete()
                except Exception:
                    pass
            else:
                max_display = 20
                display = results[:max_display]
                embed = discord.Embed(
                    title="🔍 複数のアイテムが見つかりました",
                    description=f"「{query}」に一致するアイテムが **{len(results)}件** あります。",
                    color=discord.Color.blue(),
                )
                candidates = []
                for i, (_, jp, en) in enumerate(display, 1):
                    if jp and en and jp != en:
                        candidates.append(f"`{i}.` **{jp}** ({en})")
                    else:
                        candidates.append(f"`{i}.` **{jp or en}**")
                chunk = 10
                for i in range(0, len(candidates), chunk):
                    embed.add_field(
                        name=f"候補 ({i+1}～{min(i+chunk, len(candidates))})",
                        value="\n".join(candidates[i:i+chunk]),
                        inline=False,
                    )
                if len(results) > max_display:
                    embed.add_field(
                        name="ℹ️ 注意",
                        value=f"上位 {max_display} 件のみ表示。より具体的な名前で検索してください。",
                        inline=False,
                    )
                embed.add_field(
                    name="💡 ヒント",
                    value="完全なアイテム名で再検索してください。\n例: `!i アイスシャード`",
                    inline=False,
                )
                embed.set_footer(text=f"検索ワード: {query}")
                await ctx.reply(embed=embed, mention_author=False)

        else:
            embed = discord.Embed(
                title="❌ アイテムが見つかりません",
                description=f"「{query}」というアイテムは見つかりませんでした。",
                color=discord.Color.red(),
            )
            embed.add_field(
                name="ヒント",
                value=(
                    "• 取引可能なアイテムのみ検索できます\n"
                    "• 日本語または英語で検索できます\n"
                    "• 部分一致でも検索できます"
                ),
                inline=False,
            )
            await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(ItemCog(bot))
    print("ItemCog loaded.")
