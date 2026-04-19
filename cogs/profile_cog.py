# cogs/profile_cog.py
import os
import json
from pathlib import Path
from typing import Dict, Optional
from discord.ext import commands
import discord
from cogs.base_cog import BaseCog


class ProfileManager:
    """ユーザープロフィールの管理クラス"""
    
    def __init__(self, profiles_file: str = "usernames.json"):
        base_dir = Path(__file__).parent.parent
        self.profiles_file = base_dir / profiles_file
        self._profiles: Dict = {}
        self.load()
    
    def load(self) -> Dict:
        """プロフィールを読み込む"""
        try:
            if self.profiles_file.exists():
                with open(self.profiles_file, "r", encoding="utf-8") as f:
                    self._profiles = json.load(f)
                print(f"✅ プロフィール読み込み完了: {len(self._profiles)}件")
            else:
                print("⚠️ プロフィールファイルが存在しません。新規作成します。")
                self._profiles = {}
        except json.JSONDecodeError as e:
            print(f"❌ プロフィール読み込みエラー: {e}")
            self._profiles = {}
        return self._profiles
    
    def save(self) -> bool:
        """プロフィールを保存"""
        try:
            self.profiles_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.profiles_file, "w", encoding="utf-8") as f:
                json.dump(self._profiles, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ プロフィール保存エラー: {e}")
            return False
    
    def get(self, user_id: str) -> Optional[Dict]:
        """プロフィールを取得"""
        return self._profiles.get(user_id)
    
    def set(self, user_id: str, profile: Dict) -> bool:
        """プロフィールを設定"""
        self._profiles[user_id] = profile
        return self.save()
    
    def delete(self, user_id: str) -> bool:
        """プロフィールを削除"""
        if user_id in self._profiles:
            del self._profiles[user_id]
            return self.save()
        return False


class ProfileCog(BaseCog):
    """ユーザーのFF14キャラクタープロフィールを管理するCog"""
    
    def __init__(self, bot: commands.Bot):
        """
        ProfileCogのコンストラクタ
        
        Args:
            bot: Botのインスタンス
        """
        super().__init__()
        self.bot = bot
        self.profile_manager = ProfileManager()
    
    @commands.command(name="iam", aliases=["register", "登録"])
    async def iam(
        self, 
        ctx: commands.Context, 
        server: Optional[str] = None, 
        first: Optional[str] = None, 
        last: Optional[str] = None
    ):
        """
        🔖 自分のFF14キャラクタープロフィールを登録
        
        使い方: !iam <サーバー> <名> <姓>
        例: !iam Atomos Trunks Vegeta
        """
        # 入力チェック
        if not all([server, first, last]):
            embed = discord.Embed(
                title="❌ 入力が不足しています",
                description="**使い方:**\n`!iam <サーバー> <名> <姓>`\n\n**例:**\n`!iam Atomos Trunks Vegeta`",
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
            character_id = await self.lodestone_search(full_name, server)

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
            
            # プロフィールを保存
            profile = {
                "server": server,
                "first": first,
                "last": last,
                "character_id": character_id
            }
            
            success = self.profile_manager.set(str(ctx.author.id), profile)
            
            if success:
                lodestone_url = self.get_lodestone_url(character_id)
                embed = discord.Embed(
                    title="✅ プロフィールを登録しました",
                    description=f"**サーバー:** {server}\n**名前:** {full_name}",
                    color=discord.Color.green(),
                    url=lodestone_url
                )
                embed.add_field(
                    name="Lodestone",
                    value=f"[キャラクターページを見る]({lodestone_url})",
                    inline=False
                )
                embed.set_footer(text="!whoami で確認できます")
            else:
                embed = discord.Embed(
                    title="❌ 保存エラー",
                    description="プロフィールの保存に失敗しました。",
                    color=discord.Color.red()
                )
            
            await ctx.reply(embed=embed, mention_author=False)
    
    @commands.command(name="whoami", aliases=["myprofile", "自分"])
    async def whoami(self, ctx: commands.Context):
        """
        👤 自分のプロフィールを確認
        
        使い方: !whoami
        """
        profile = self.profile_manager.get(str(ctx.author.id))
        
        if not profile:
            embed = discord.Embed(
                title="❌ プロフィール未登録",
                description="まだプロフィールが登録されていません。\n`!iam <サーバー> <名> <姓>` で登録してください。",
                color=discord.Color.orange()
            )
            await ctx.reply(embed=embed, mention_author=False)
            return
        
        server = profile["server"]
        first = profile["first"]
        last = profile["last"]
        full_name = f"{first} {last}"
        
        # キャラクターIDを確認（古いデータ対応）
        character_id = profile.get("character_id")
        if not character_id:
            async with ctx.typing():
                character_id = await self.lodestone_search(full_name, server)
                if character_id:
                    profile["character_id"] = character_id
                    self.profile_manager.set(str(ctx.author.id), profile)
        
        if not character_id:
            embed = discord.Embed(
                title="❌ キャラクターが見つかりません",
                description="Lodestoneでキャラクターを確認できませんでした。\nプロフィールを再登録してください。",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed, mention_author=False)
            return
        
        lodestone_url = self.get_lodestone_url(character_id)
        
        embed = discord.Embed(
            title="👤 あなたのプロフィール",
            description=f"**サーバー:** {server}\n**名前:** {full_name}",
            color=discord.Color.blue(),
            url=lodestone_url
        )
        embed.add_field(
            name="🔗 Lodestone",
            value=f"[キャラクターページを見る]({lodestone_url})",
            inline=False
        )
        embed.set_footer(text=f"キャラクターID: {character_id}")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @commands.command(name="forget", aliases=["unregister", "削除"], hidden=True)
    async def forget(self, ctx: commands.Context):
        """
        🗑️ 自分のプロフィールを削除
        
        使い方: !forget
        """
        profile = self.profile_manager.get(str(ctx.author.id))
        
        if not profile:
            embed = discord.Embed(
                title="❌ プロフィール未登録",
                description="削除するプロフィールがありません。",
                color=discord.Color.orange()
            )
            await ctx.reply(embed=embed, mention_author=False)
            return
        
        success = self.profile_manager.delete(str(ctx.author.id))
        
        if success:
            embed = discord.Embed(
                title="✅ プロフィールを削除しました",
                description="プロフィール情報を削除しました。",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ 削除エラー",
                description="プロフィールの削除に失敗しました。",
                color=discord.Color.red()
            )
        
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    """このCogをBotに登録"""
    try:
        await bot.add_cog(ProfileCog(bot))
        print("✅ ProfileCog loaded.")
    except Exception as e:
        print(f"❌ ProfileCog の読み込みに失敗: {e}")
        raise