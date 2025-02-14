# cogs/help_cog.py
import discord
from discord.ext import commands


class HelpCog(commands.Cog):
    """
    ヘルプコマンドを管理するためのCogクラス。
    """
    def __init__(self, bot: commands.Bot):
        """
        HelpCogのコンストラクタ。
        Botのインスタンスを受け取り、クラスのメンバに保持する。
        """
        self.bot = bot

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context):
        """
            どうも～
        """
        # ヘルプメッセージをEmbedで作成
        embed = discord.Embed(
            title="ヘルプ",
            description="利用可能なコマンド一覧:",
            color=discord.Color.blue()
        )
        # 画像ファイルを読み込み（添付ファイルとして送信するために必要）
        file = discord.File("icon.png", filename="icon.png")

        # Embedの作者部分に設定
        embed.set_author(name="FF14 bot", icon_url="attachment://icon.png")
        # Embedのサムネイル画像を設定
        embed.set_thumbnail(url="attachment://icon.png")
        # フィールドの追加（例としてコマンドプレフィックスなどを表示）
        embed.add_field(name="Prefix", value="!", inline=True)
        embed.add_field(name="Value", value="command", inline=True)

        # Botに登録されている全コマンドを、名前順にソートしてフィールドとして追加
        commands_sorted = sorted(self.bot.commands, key=lambda cmd: cmd.name)
        for command in commands_sorted:
            # 隠しコマンド(command.hiddenがTrue)は表示しないようにすることも可能
            if not command.hidden:
                embed.add_field(
                    name=command.name,
                    value=command.help or "説明が設定されていません",
                    inline=False
                )

        # フッターの設定
        embed.set_footer(text="by Trunks Vegeta@Atomos", icon_url="attachment://icon.png")
        # Embedとファイルを同時に送信
        await ctx.send(embed=embed, file=file)


async def setup(bot: commands.Bot):
    """
    このCogをBotに登録するためのセットアップ関数。
    Botの拡張機能としてロードされる。
    """
    await bot.add_cog(HelpCog(bot))
    print("HelpCog loaded.")
