# cogs/help_cog.py
import discord
from discord.ext import commands


class HelpCog(commands.Cog):
    """シンプルなヘルプ表示を提供するCog。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.prefix = "!"
        self.footer_text = "困ったら !help <コマンド名>"

    @commands.command(name="help", aliases=["h", "ヘルプ"])
    async def help_command(self, ctx: commands.Context, topic: str | None = None):
        """
        ヘルプを表示します

        使い方: !help [コマンド名]
        """
        if topic:
            await self._send_topic_help(ctx, topic.lower())
            return

        await self._send_general_help(ctx)

    async def _send_general_help(self, ctx: commands.Context):
        embed = discord.Embed(
            title="📚 FF14 Bot ヘルプ",
            description="よく使うコマンドだけを用途別にまとめています。",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="💰 アイテム価格",
            value=(
                "`!i <アイテム名>` - Japan全体で価格検索\n"
                "`!i <ワールド> <アイテム名>` - ワールド指定\n"
                "`!i <DC> <アイテム名>` - DC指定\n"
                "例: `!i Elem アイスシャード`"
            ),
            inline=False
        )

        embed.add_field(
            name="💬 AIチャット",
            value=(
                "`!ft <内容>` - ヤンキー口調\n"
                "`!ftn <内容>` - 丁寧・FF14相談向け\n"
                "`!ftjk <内容>` - ツンデレJK口調"
            ),
            inline=False
        )

        embed.add_field(
            name="👤 キャラクター・プロフィール",
            value=(
                "`!charac <ワールド> <名> <姓>` - Lodestone検索\n"
                "`!iam <ワールド> <名> <姓>` - 自分のプロフィール登録\n"
                "`!whoami` - 登録プロフィール確認"
            ),
            inline=False
        )

        embed.add_field(
            name="🐦 X / Bot",
            value=(
                "`!X [件数]` - FF14公式Xの最新投稿\n"
                "`!ping` - Botの応答確認\n"
                "`!info` - Bot情報"
            ),
            inline=False
        )

        embed.add_field(
            name="🔎 詳細ヘルプ",
            value=(
                "`!help item` / `!help ft` / `!help charac` / `!help X`\n"
                "コマンドの別名でも見られます。例: `!help i`"
            ),
            inline=False
        )

        embed.set_footer(text=self.footer_text)
        await ctx.reply(embed=embed, mention_author=False)

    async def _send_topic_help(self, ctx: commands.Context, topic: str):
        topic_aliases = {
            "i": "item",
            "価格": "item",
            "item": "item",
            "ft": "ft",
            "freetalk": "ft",
            "ftn": "ft",
            "freetalk_normal": "ft",
            "ftjk": "ft",
            "freetalk_jk": "ft",
            "tsundere": "ft",
            "charac": "charac",
            "search": "charac",
            "検索": "charac",
            "キャラ": "charac",
            "iam": "profile",
            "register": "profile",
            "登録": "profile",
            "whoami": "profile",
            "myprofile": "profile",
            "自分": "profile",
            "x": "x",
            "ping": "bot",
            "p": "bot",
            "info": "bot",
            "botinfo": "bot",
            "about": "bot",
            "hello": "bot",
        }
        key = topic_aliases.get(topic)

        if key == "item":
            embed = self._topic_embed(
                "💰 アイテム価格",
                (
                    "`!i <アイテム名>`\n"
                    "`!i <ワールド> <アイテム名>`\n"
                    "`!i <DC> <アイテム名>`\n\n"
                    "例:\n"
                    "`!i アイスシャード`\n"
                    "`!i Atomos アイスシャード`\n"
                    "`!i Elem アイスシャード`\n"
                    "`!i Elemental オーケストリオン譜:鬼の棲む島`"
                )
            )
        elif key == "ft":
            embed = self._topic_embed(
                "💬 AIチャット",
                (
                    "`!ft <内容>` - ヤンキー口調\n"
                    "`!ftn <内容>` - 丁寧・FF14相談向け\n"
                    "`!ftjk <内容>` - ツンデレJK口調\n\n"
                    "例:\n"
                    "`!ftn 極ゴルベーザの攻略を教えて`\n"
                    "`!ftjk こんにちは`"
                )
            )
        elif key == "charac":
            embed = self._topic_embed(
                "👤 キャラクター検索",
                (
                    "`!charac <ワールド> <名> <姓>`\n"
                    "別名: `!search`, `!検索`, `!キャラ`\n\n"
                    "例: `!charac Atomos Trunks Vegeta`"
                )
            )
        elif key == "profile":
            embed = self._topic_embed(
                "🪪 プロフィール",
                (
                    "`!iam <ワールド> <名> <姓>` - 登録\n"
                    "`!whoami` - 確認\n\n"
                    "例: `!iam Atomos Trunks Vegeta`"
                )
            )
        elif key == "x":
            embed = self._topic_embed(
                "🐦 FF14公式X",
                (
                    "`!X [件数]`\n\n"
                    "例:\n"
                    "`!X`\n"
                    "`!X 5`"
                )
            )
        elif key == "bot":
            embed = self._topic_embed(
                "🤖 Bot基本",
                (
                    "`!ping` - 応答速度\n"
                    "`!info` - Bot情報\n"
                    "`!hello [名前]` - 挨拶"
                )
            )
        else:
            await ctx.reply(f"❌ `{topic}` のヘルプは見つかりません。`!help` で一覧を確認してください。", mention_author=False)
            return

        await ctx.reply(embed=embed, mention_author=False)

    def _topic_embed(self, title: str, description: str) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.green()
        )
        embed.set_footer(text=self.footer_text)
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
    print("✅ HelpCog loaded.")
