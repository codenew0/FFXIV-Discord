# bot.py
import os
import json
import asyncio
import secrets
from pathlib import Path
from typing import Optional
import discord
from discord.ext import commands


class BotConfig:
    """ボットの設定を管理するクラス"""
    
    def __init__(self, config_file: str = "config.json"):
        self.base_dir = Path(__file__).parent
        self.config_path = self.base_dir / config_file
        self._config = None
    
    def load(self) -> dict:
        """設定ファイルを読み込む"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            print(f"✅ 設定ファイル読み込み完了: {self.config_path}")
            return self._config
        except FileNotFoundError:
            raise FileNotFoundError(f"設定ファイルが見つかりません: {self.config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"設定ファイルの形式が不正です: {e}")
    
    @property
    def config(self) -> dict:
        """設定を取得（キャッシュ付き）"""
        if self._config is None:
            self._config = self.load()
        return self._config
    
    @property
    def discord_token(self) -> str:
        """Discordトークンを取得"""
        return self.config.get("DISCORD_TOKEN", "")
    
    @property
    def channel_id(self) -> Optional[int]:
        """通知チャンネルIDを取得"""
        channel_id = self.config.get("CHANNEL_ID")
        return int(channel_id) if channel_id else None


class FF14Bot(commands.Bot):
    """FF14用カスタムBot"""
    
    def __init__(self, config: BotConfig, *args, **kwargs):
        """
        FF14Botのコンストラクタ
        
        Args:
            config: ボット設定
        """
        super().__init__(*args, **kwargs)
        self.config_manager = config
        self.shutdown_hash = secrets.token_hex(16)
        self.startup_complete = False
    
    async def setup_hook(self):
        """ボット起動時の初期セットアップ"""
        await self.load_all_extensions()
    
    async def load_all_extensions(self):
        """すべてのCog拡張機能をロード"""
        cogs_dir = Path(__file__).parent / "cogs"
        
        if not cogs_dir.exists():
            print(f"⚠️ cogsディレクトリが見つかりません: {cogs_dir}")
            return
        
        print(f"📦 拡張機能をロード中: {cogs_dir}")
        
        loaded_count = 0
        failed_count = 0
        
        for filepath in cogs_dir.glob("*.py"):
            # 除外するファイル
            if filepath.stem in ["base_cog", "__init__"] or filepath.stem.startswith("_"):
                continue
            
            extension_name = f"cogs.{filepath.stem}"
            
            try:
                await self.load_extension(extension_name)
                print(f"  ✅ {extension_name}")
                loaded_count += 1
            except Exception as e:
                print(f"  ❌ {extension_name}: {e}")
                failed_count += 1
        
        print(f"\n📊 拡張機能ロード結果: 成功 {loaded_count}件 / 失敗 {failed_count}件\n")
    
    async def on_ready(self):
        """ボット起動完了時の処理"""
        if self.startup_complete:
            return
        
        self.startup_complete = True
        
        print("=" * 50)
        print(f"🤖 {self.user} としてログイン完了")
        print(f"📝 ユーザーID: {self.user.id}")
        print(f"🔧 discord.py バージョン: {discord.__version__}")
        print(f"🌐 接続サーバー数: {len(self.guilds)}")
        print(f"📡 レイテンシ: {round(self.latency * 1000)}ms")
        print("=" * 50)
        
        # 登録コマンド一覧
        print("\n📋 登録されているコマンド:")
        for cmd in sorted(self.commands, key=lambda c: c.name):
            if not cmd.hidden:
                print(f"  • {cmd.name:<15} - {cmd.help or '説明なし'}")
        print()
        
        # 起動通知（オプション）
        channel_id = self.config_manager.channel_id
        if channel_id:
            channel = self.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title="🟢 Bot起動",
                    description="FF14 Botがオンラインになりました！",
                    color=discord.Color.green()
                )
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    print(f"⚠️ チャンネル {channel_id} への送信権限がありません")
    
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """コマンドエラーハンドラ"""
        # CommandNotFoundは無視
        if isinstance(error, commands.CommandNotFound):
            return
        
        # MissingRequiredArgumentエラー
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="❌ 引数が不足しています",
                description=f"必要な引数: `{error.param.name}`\n\n使い方は `!help {ctx.command.name}` で確認できます。",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed, mention_author=False)
            return
        
        # NotOwnerエラー
        if isinstance(error, commands.NotOwner):
            await ctx.reply("❌ このコマンドはBot所有者のみ実行できます。", mention_author=False)
            return
        
        # その他のエラー
        print(f"❌ コマンドエラー ({ctx.command}): {error}")
        
        embed = discord.Embed(
            title="❌ エラーが発生しました",
            description="コマンドの実行中にエラーが発生しました。",
            color=discord.Color.red()
        )
        await ctx.reply(embed=embed, mention_author=False)
        
        # エラーを再送出（デバッグ用）
        raise error


def create_bot() -> FF14Bot:
    """Botインスタンスを作成"""
    # 設定を読み込む
    config = BotConfig()
    
    # Intentsの設定
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.members = False  # 必要な場合はTrueに
    
    # Botインスタンスを作成
    bot = FF14Bot(
        config=config,
        command_prefix='!',
        intents=intents,
        help_command=None,  # カスタムヘルプを使用
        case_insensitive=True  # コマンド名の大文字小文字を区別しない
    )
    
    return bot


# Botインスタンスを作成
bot = create_bot()


# ==================== イベントハンドラ ====================

@bot.event
async def on_message(message: discord.Message):
    """メッセージ受信時の処理"""
    # Bot自身のメッセージは無視
    if message.author.bot:
        return
    
    # カスタムメッセージ処理
    if message.content.startswith("!hello"):
        params = message.content.split()[1:]
        
        if params:
            formatted_params = " and ".join(params)
            response = f"Hi, {formatted_params}! 👋"
        else:
            response = "どうも！👋"
        
        await message.reply(response, mention_author=False)
        return
    
    # 通常のコマンド処理
    await bot.process_commands(message)


# ==================== 基本コマンド ====================

@bot.command(name="ping", aliases=["p"])
async def ping(ctx: commands.Context):
    """
    🏓 Botの応答速度を確認
    
    使い方: !ping
    """
    latency_ms = round(bot.latency * 1000)
    
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"レイテンシ: **{latency_ms}ms**",
        color=discord.Color.green() if latency_ms < 200 else discord.Color.orange()
    )
    
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name="info", aliases=["botinfo", "about"])
async def bot_info(ctx: commands.Context):
    """
    ℹ️ Botの情報を表示
    
    使い方: !info
    """
    embed = discord.Embed(
        title="🤖 Bot情報",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Bot名",
        value=bot.user.name,
        inline=True
    )
    
    embed.add_field(
        name="レイテンシ",
        value=f"{round(bot.latency * 1000)}ms",
        inline=True
    )
    
    embed.add_field(
        name="サーバー数",
        value=f"{len(bot.guilds)}",
        inline=True
    )
    
    embed.add_field(
        name="コマンド数",
        value=f"{len([c for c in bot.commands if not c.hidden])}",
        inline=True
    )
    
    embed.add_field(
        name="discord.py",
        value=discord.__version__,
        inline=True
    )
    
    embed.set_footer(text="!help でコマンド一覧を確認")
    
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name="quit", aliases=["shutdown"], hidden=True)
async def quit_bot(ctx: commands.Context, hash_str: Optional[str] = None):
    """
    🛑 Botを終了（緊急時のみ）
    
    使い方: !quit <認証ハッシュ>
    """
    if not hash_str or hash_str != bot.shutdown_hash:
        await ctx.reply(
            f"⚠️ Bot終了には認証が必要です。\n認証ハッシュ: `{bot.shutdown_hash}`",
            mention_author=False
        )
        return
    
    embed = discord.Embed(
        title="👋 Bot終了",
        description="さようなら～",
        color=discord.Color.red()
    )
    
    await ctx.reply(embed=embed, mention_author=False)
    await bot.close()


# ==================== 拡張機能管理コマンド ====================

@bot.command(name="load", hidden=True)
@commands.is_owner()
async def load_extension(ctx: commands.Context, extension: str):
    """
    📦 拡張機能をロード
    
    使い方: !load <拡張機能名>
    例: !load profile_cog
    """
    try:
        await bot.load_extension(f"cogs.{extension}")
        await ctx.reply(f"✅ 拡張機能 `{extension}` をロードしました。", mention_author=False)
    except commands.ExtensionAlreadyLoaded:
        await ctx.reply(f"⚠️ 拡張機能 `{extension}` は既にロードされています。", mention_author=False)
    except commands.ExtensionNotFound:
        await ctx.reply(f"❌ 拡張機能 `{extension}` が見つかりません。", mention_author=False)
    except Exception as e:
        await ctx.reply(f"❌ ロードに失敗: {e}", mention_author=False)


@bot.command(name="reload", hidden=True)
@commands.is_owner()
async def reload_extension(ctx: commands.Context, extension: str):
    """
    🔄 拡張機能をリロード
    
    使い方: !reload <拡張機能名>
    例: !reload profile_cog
    """
    try:
        await bot.reload_extension(f"cogs.{extension}")
        await ctx.reply(f"✅ 拡張機能 `{extension}` をリロードしました。", mention_author=False)
    except commands.ExtensionNotLoaded:
        await ctx.reply(f"⚠️ 拡張機能 `{extension}` はロードされていません。", mention_author=False)
    except commands.ExtensionNotFound:
        await ctx.reply(f"❌ 拡張機能 `{extension}` が見つかりません。", mention_author=False)
    except Exception as e:
        await ctx.reply(f"❌ リロードに失敗: {e}", mention_author=False)


@bot.command(name="unload", hidden=True)
@commands.is_owner()
async def unload_extension(ctx: commands.Context, extension: str):
    """
    📤 拡張機能をアンロード
    
    使い方: !unload <拡張機能名>
    例: !unload profile_cog
    """
    try:
        await bot.unload_extension(f"cogs.{extension}")
        await ctx.reply(f"✅ 拡張機能 `{extension}` をアンロードしました。", mention_author=False)
    except commands.ExtensionNotLoaded:
        await ctx.reply(f"⚠️ 拡張機能 `{extension}` はロードされていません。", mention_author=False)
    except Exception as e:
        await ctx.reply(f"❌ アンロードに失敗: {e}", mention_author=False)


@bot.command(name="extensions", aliases=["exts", "cogs"], hidden=True)
@commands.is_owner()
async def list_extensions(ctx: commands.Context):
    """
    📋 ロード済みの拡張機能一覧を表示
    
    使い方: !extensions
    """
    extensions = list(bot.extensions.keys())
    
    if not extensions:
        await ctx.reply("⚠️ ロードされている拡張機能はありません。", mention_author=False)
        return
    
    embed = discord.Embed(
        title="📦 ロード済み拡張機能",
        description="\n".join([f"• `{ext}`" for ext in sorted(extensions)]),
        color=discord.Color.blue()
    )
    
    embed.set_footer(text=f"合計: {len(extensions)}個")
    
    await ctx.reply(embed=embed, mention_author=False)


# ==================== メイン処理 ====================

async def main():
    """メイン関数"""
    try:
        print("🚀 FF14 Bot起動中...\n")
        
        # Botを起動
        token = bot.config_manager.discord_token
        if not token:
            raise ValueError("DISCORD_TOKENが設定されていません")
        
        async with bot:
            await bot.start(token)
    
    except KeyboardInterrupt:
        print("\n⚠️ キーボード割り込みを受信しました")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        raise
    finally:
        print("\n👋 Bot終了")


if __name__ == '__main__':
    asyncio.run(main())