# cogs/search_charac_cog.py
from typing import Optional
import discord
from discord.ext import commands
from cogs.base_cog import BaseCog


class SearchCog(BaseCog):
    """Lodestoneでキャラクター検索を行うCog"""
    
    def __init__(self, bot: commands.Bot):
        """
        SearchCogのコンストラクタ
        
        Args:
            bot: Botのインスタンス
        """
        super().__init__()
        self.bot = bot
    
    @staticmethod
    def normalize_input(text: str) -> str:
        """入力文字列を正規化"""
        return text.strip().capitalize()
    
    @commands.command(name="charac", aliases=["search", "検索", "キャラ"])
    async def charac(
        self, 
        ctx: commands.Context, 
        server: Optional[str] = None, 
        first: Optional[str] = None, 
        last: Optional[str] = None
    ):
        """
        🔍 FF14キャラクターを検索
        
        使い方: !charac <サーバー> <名> <姓>
        例: !charac Atomos Trunks Vegeta
        """
        # 入力チェック
        if not all([server, first, last]):
            embed = discord.Embed(
                title="❌ 入力が不足しています",
                description="**使い方:**\n`!charac <サーバー> <名> <姓>`\n\n**例:**\n`!charac Atomos Trunks Vegeta`",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed, mention_author=False)
            return
        
        # 入力を正規化
        server = self.normalize_input(server)
        first = self.normalize_input(first)
        last = self.normalize_input(last)
        full_name = f"{first} {last}"
        
        # Lodestoneで検索
        async with ctx.typing():
            character_id = self.lodestone_search(full_name, server)
            
            if not character_id:
                embed = discord.Embed(
                    title="❌ キャラクターが見つかりません",
                    description=(
                        f"**検索条件:**\n"
                        f"サーバー: {server}\n"
                        f"名前: {full_name}\n\n"
                        "入力内容に誤りがないか確認してください。"
                    ),
                    color=discord.Color.red()
                )
                await ctx.reply(embed=embed, mention_author=False)
                return
            
            # Lodestone URLを生成
            lodestone_url = self.get_lodestone_url(character_id)
            
            # 結果を表示
            embed = discord.Embed(
                title="✅ キャラクターが見つかりました",
                description=f"**サーバー:** {server}\n**名前:** {full_name}",
                color=discord.Color.green(),
                url=lodestone_url
            )
            
            embed.add_field(
                name="🔗 Lodestone",
                value=f"[キャラクターページを見る]({lodestone_url})",
                inline=False
            )
            
            embed.set_footer(text=f"キャラクターID: {character_id}")
            
            await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    """このCogをBotに登録"""
    try:
        await bot.add_cog(SearchCog(bot))
        print("✅ SearchCog loaded.")
    except Exception as e:
        print(f"❌ SearchCog の読み込みに失敗: {e}")
        raise