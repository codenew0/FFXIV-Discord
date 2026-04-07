# cogs/help_cog.py
import discord
from discord.ext import commands
from typing import Optional


class HelpCog(commands.Cog):
    """ヘルプコマンドを管理するためのCogクラス"""
    
    def __init__(self, bot: commands.Bot):
        """
        HelpCogのコンストラクタ
        
        Args:
            bot: Botのインスタンス
        """
        self.bot = bot
        self.icon_path = "icon.png"
        self.bot_name = "FF14 bot"
        self.footer_text = "by Trunks Vegeta@Atomos"
        self.prefix = "!"

    @commands.command(name="help", aliases=["h", "ヘルプ"])
    async def help_command(self, ctx: commands.Context, command_name: Optional[str] = None):
        """
        ヘルプメッセージを表示します
        
        使い方:
            !help - すべてのコマンドを表示
            !help <コマンド名> - 特定のコマンドの詳細を表示
        """
        if command_name:
            await self._send_command_help(ctx, command_name)
        else:
            await self._send_general_help(ctx)

    async def _send_general_help(self, ctx: commands.Context):
        """すべてのコマンドのヘルプを表示"""
        embed = discord.Embed(
            title="📚 ヘルプメニュー",
            description=f"利用可能なコマンド一覧\nプレフィックス: `{self.prefix}`",
            color=discord.Color.blue()
        )

        try:
            file = discord.File(self.icon_path, filename="icon.png")
            icon_url = "attachment://icon.png"
        except FileNotFoundError:
            file = None
            icon_url = None

        if icon_url:
            embed.set_author(name=self.bot_name, icon_url=icon_url)
            embed.set_thumbnail(url=icon_url)

        # Cogごとにコマンドをグループ化
        cog_commands = {}
        no_cog_commands = []

        for command in self.bot.commands:
            if command.hidden:
                continue
            
            if command.cog_name:
                if command.cog_name not in cog_commands:
                    cog_commands[command.cog_name] = []
                cog_commands[command.cog_name].append(command)
            else:
                no_cog_commands.append(command)

        # Cogごとにフィールドを追加
        for cog_name in sorted(cog_commands.keys()):
            commands_list = cog_commands[cog_name]
            commands_text = "\n".join([
                f"`{self.prefix}{cmd.name}` - {cmd.help or '説明なし'}"
                for cmd in sorted(commands_list, key=lambda c: c.name)
            ])
            embed.add_field(
                name=f"📁 {cog_name}",
                value=commands_text,
                inline=False
            )

        # Cogに属さないコマンド
        if no_cog_commands:
            commands_text = "\n".join([
                f"`{self.prefix}{cmd.name}` - {cmd.help or '説明なし'}"
                for cmd in sorted(no_cog_commands, key=lambda c: c.name)
            ])
            embed.add_field(
                name="📁 その他",
                value=commands_text,
                inline=False
            )

        embed.set_footer(
            text=f"{self.footer_text} | {self.prefix}help <コマンド名> で詳細表示",
            icon_url=icon_url if icon_url else None
        )

        if file:
            await ctx.send(embed=embed, file=file)
        else:
            await ctx.send(embed=embed)

    async def _send_command_help(self, ctx: commands.Context, command_name: str):
        """特定のコマンドの詳細ヘルプを表示"""
        command = self.bot.get_command(command_name)
        
        if not command or command.hidden:
            await ctx.send(f"❌ コマンド `{command_name}` が見つかりません。")
            return

        embed = discord.Embed(
            title=f"📖 コマンド: {command.name}",
            description=command.help or "説明が設定されていません",
            color=discord.Color.green()
        )

        # 使い方
        embed.add_field(
            name="使い方",
            value=f"`{self.prefix}{command.name} {command.signature}`",
            inline=False
        )

        # エイリアス
        if command.aliases:
            aliases = ", ".join([f"`{alias}`" for alias in command.aliases])
            embed.add_field(
                name="別名",
                value=aliases,
                inline=False
            )

        # Cog情報
        if command.cog_name:
            embed.add_field(
                name="カテゴリ",
                value=command.cog_name,
                inline=True
            )

        embed.set_footer(text=self.footer_text)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """このCogをBotに登録"""
    await bot.add_cog(HelpCog(bot))
    print("✅ HelpCog loaded.")