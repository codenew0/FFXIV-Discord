# bot.py
import os
import discord
from discord.ext import commands
import json
import asyncio
import secrets

# config.jsonから設定を読み込む
with open("config.json", "r") as f:
    config = json.load(f)

# Discordのトークンと通知先チャンネルIDを取得
TOKEN = config["DISCORD_TOKEN"]
CHANNEL_ID = config["CHANNEL_ID"]

# DiscordのIntentsを設定。message_contentを有効にする
intents = discord.Intents.default()
intents.message_content = True

# ボット終了時に必要なランダムなハッシュ値を生成（終了コマンドの認証用）
random_hash = secrets.token_hex(16)

# ボットのインスタンスを作成。コマンドプレフィックスは "!" とする
bot = commands.Bot(command_prefix='!', intents=intents)

# カスタムヘルプコマンドを使用するため、デフォルトのhelpコマンドを削除する
bot.remove_command('help')


async def load_extensions():
    """
    cogsフォルダ内の拡張機能（Cog）をすべてロードする非同期関数。
    base_cog.pyおよびファイル名が"__"で始まるファイルは除外します。
    """
    cogs_folder = "./cogs"
    print("拡張機能をロード中:", cogs_folder)
    for filename in os.listdir(cogs_folder):
        if filename.endswith(".py") and filename != "base_cog.py" and not filename.startswith("__"):
            extension = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(extension)
                # 拡張機能のロード成功時のデバッグ出力（必要に応じてコメントアウト解除）
                # print(f"拡張機能 {extension} がロードされました")
            except Exception as e:
                print(f"拡張機能 {extension} のロードに失敗しました: {e}")


@bot.event
async def on_ready():
    """
    ボットが起動してDiscordに接続が完了した際に実行されるイベントハンドラ。
    指定のチャンネルにオンライン通知を送信し、登録されているコマンド一覧をデバッグ出力します。
    """
    print(f"{bot.user} としてログインしました")
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("botオンライン!")
    # 登録されているすべてのコマンドをデバッグ出力
    print("登録されているコマンド:")
    for cmd in bot.commands:
        print(f"- {cmd.name}")


@bot.event
async def on_message(message: discord.Message):
    """
    メッセージ受信時に実行されるイベントハンドラ。
    ボット自身のメッセージは無視し、特定のカスタムメッセージ（例: "!hello"）に対してレスポンスを返します。
    それ以外のメッセージは通常のコマンド処理に回します。

    Parameters:
        message (discord.Message): 受信したメッセージオブジェクト
    """
    # ボット自身のメッセージは処理しない
    if message.author == bot.user:
        return

    # "!hello" メッセージに対するカスタム処理
    if message.content.startswith("!hello"):
        params = message.content.split()[1:]
        if params:
            formatted_params = " and ".join(params)
            response = f"Hi, {formatted_params} was sent"
        else:
            response = "どうも!"

        # ユーザーに返信（メンションなし）
        await message.reply(response, mention_author=False)
        return

    # カスタム処理対象でない場合、他のコマンドを処理する
    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    """
    コマンド実行時にエラーが発生した場合のエラーハンドラ。
    CommandNotFoundエラーは無視し、それ以外のエラーはそのまま再スローします。

    Parameters:
        ctx (commands.Context): コマンド実行時のコンテキスト
        error (Exception): 発生したエラーオブジェクト
    """
    if isinstance(error, commands.CommandNotFound):
        return
    raise error


@bot.command(name="ping", hidden=True)
async def ping(ctx):
    await ctx.send(f'Pong! {round(bot.latency * 1000)}ms')


@bot.command(name="quit")
async def quit_bot(ctx: commands.Context, hash_str: str=None):
    """
    しゅーりょー！（機能異常時）
    """
    if not hash_str or hash_str != random_hash:
        await ctx.reply(f"なにかあったの？{random_hash}")
        return

    await ctx.send("さよおうなら～")
    await bot.close()


@bot.command(name="load", hidden=True)
@commands.is_owner()
async def load_extension(ctx: commands.Context, extension: str):
    """
    指定した拡張モジュール (Cog) のロードを行います。
    例: !load profile_cog
    """
    try:
        await ctx.bot.load_extension(f"cogs.{extension}")
        await ctx.send(f"Extension `{extension}` loaded successfully.")
    except Exception as e:
        await ctx.send(f"Failed to load extension `{extension}`.\nError: {e}")


@bot.command(name="reload", hidden=True)
@commands.is_owner()  # オーナーのみ実行できるようにする
async def reload_extension(ctx, extension: str):
    """
        指定した拡張モジュール (Cog) のリロードを行います。
        例: !reload profile_cog
        """
    try:
        await ctx.bot.reload_extension(f"cogs.{extension}")
        await ctx.send(f"Extension `{extension}` reloaded successfully.")
    except Exception as e:
        await ctx.send(f"Failed to reload extension `{extension}`.\nError: {e}")


@bot.command(name="unload", hidden=True)
@commands.is_owner()
async def unload_extension(ctx: commands.Context, extension: str):
    """
    指定した拡張モジュール (Cog) のアンロードを行います。
    例: !unload profile_cog
    """
    try:
        await ctx.bot.unload_extension(f"cogs.{extension}")
        await ctx.send(f"Extension `{extension}` unloaded successfully.")
    except Exception as e:
        await ctx.send(f"Failed to unload extension `{extension}`.\nError: {e}")


async def main():
    """
    ボットのメイン関数。
    拡張機能をロードし、Discordボットを起動します。
    """
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)


if __name__ == '__main__':
    asyncio.run(main())
