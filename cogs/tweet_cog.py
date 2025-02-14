# cogs/tweet_cog.py
import discord
import os
from discord.ext import commands, tasks
from playwright.async_api import async_playwright
import json

# プロジェクトルートに対する相対パスからファイルパスを解決する
BASE_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SENT_TWEETS_FILE = os.path.join(BASE_DIR, "sent_tweets.json")


class TweetCog(commands.Cog):
    """
    Twitter（X）の最新ツイートを取得し、Discordに送信するためのCogクラス。
    定期的にツイートをチェックし、新しいツイートがあれば通知を送信します。
    """

    def __init__(self, bot: commands.Bot):
        """
        コンストラクタ。
        Botのインスタンスを受け取り、必要な設定や送信済みツイート情報の読み込みを行います。
        また、定期タスク(fetch_tweets_task)を開始します。
        """
        self.bot = bot
        # config.jsonから必要な設定を読み込む
        with open("config.json", "r") as f:
            config = json.load(f)
        # 通知を送信するDiscordチャンネルのID
        self.channel_id = config["CHANNEL_ID"]
        # 固定のTwitterアカウント名
        self.x_user = "FF_XIV_JP"
        # ツイートIDのデータファイル名（configから取得、なければ"sent_tweets.json"を使用）
        self.data_file_tweets = config.get("DATA_FILE_TWEETS", "sent_tweets.json")
        # 送信済みのツイートIDを読み込む
        self.sent_tweets = self.load_sent_tweets()
        # 定期タスクを開始
        self.fetch_tweets_task.start()

    def load_sent_tweets(self):
        """
        送信済みツイートIDを保存しているJSONファイル(SENT_TWEETS_FILE)を読み込む関数。

        Returns:
            list: 送信済みツイートIDのリスト。ファイルが存在しないか、JSONの形式が不正な場合は空のリストを返す。
        """
        try:
            with open(SENT_TWEETS_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_sent_tweets(self, tweets_id):
        """
        ツイートIDのリストをJSONファイルに保存する関数。
        ※ファイルサイズを抑えるため、必要なツイートIDのみを保存します。

        Parameters:
            tweets_id (list): 保存するツイートIDのリスト。
        """
        with open(self.data_file_tweets, "w") as f:
            json.dump(tweets_id, f, indent=4)

    async def get_last_tweets_id(self):
        """
        Twitter（X）の指定アカウントの最新ツイートIDを取得する非同期関数。
        Playwrightを使用して、アカウントページにアクセスし、ツイートリンクからIDを抽出します。

        Returns:
            str or None: 最新ツイートのID。取得できなかった場合はNoneを返す。
        """
        async with async_playwright() as p:
            # Chromiumブラウザをヘッドレスモードで起動
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # 指定のTwitter（X）アカウントページにアクセス
            await page.goto("https://x.com/FF_XIV_JP", timeout=10000)

            # ツイートリンク（/FF_XIV_JP/status/で始まる）の読み込みを待つ
            await page.wait_for_selector("a[href^='/FF_XIV_JP/status/']")

            # 最初に見つかったツイートリンクを取得
            link = await page.query_selector("a[href^='/FF_XIV_JP/status/']")
            if link is None:
                print("指定のリンクが見つかりませんでした。")
                await browser.close()
                return None

            # リンクのhref属性を取得（例: "/FF_XIV_JP/status/IDNumberxxx"）
            href = await link.get_attribute("href")
            if not href:
                print("リンクのhref属性が取得できませんでした。")
                await browser.close()
                return None

            # hrefの末尾部分を抽出してツイートIDとする
            id_value = href.rsplit('/', 1)[-1]
            await browser.close()

            return id_value

    @commands.command(name="X")
    async def last_tweets(self, ctx: commands.Context):
        """
        公式Xを覗く！（FF_XIV_JPの最後のツイートを見る）
        """
        async with ctx.typing():
            # 最新ツイートIDを取得
            last_id = await self.get_last_tweets_id()
            # ツイートのURLを生成
            link = f"https://x.com/FF_XIV_JP/status/{last_id}"
            await ctx.reply(link)
            # async with async_playwright() as p:
            #     # Chromiumブラウザをヘッドレスモードで起動
            #     browser = await p.chromium.launch(headless=True)
            #     page = await browser.new_page()
            #     await page.goto(link, timeout=10000)
            #
            #     # ツイート記事部分 (article要素) の読み込みを待つ
            #     await page.wait_for_selector("article")
            #     article = await page.query_selector("article")
            #     if article is None:
            #         await ctx.reply("エラー: article要素が見つかりませんでした")
            #         await browser.close()
            #         return
            #
            #     # ツイートのスクリーンショットを保存するパス
            #     tweets_path = "tweets.png"
            #     await article.screenshot(path=tweets_path)
            #
            #     # Embedメッセージを作成
            #     embed = discord.Embed(
            #         title=f"{link}",
            #         color=discord.Color.blue()
            #     )
            #     file = discord.File(tweets_path, filename="tweets.png")
            #
            #     # Embed内で添付画像を参照
            #     embed.set_image(url="attachment://tweets.png")
            #
            #     await ctx.reply(embed=embed, file=file, mention_author=False)
            #     await browser.close()

    @tasks.loop(minutes=30)
    async def fetch_tweets_task(self):
        """
        定期的に最新ツイートをチェックし、新しいツイートがあれば指定のDiscordチャンネルに通知を送信するタスク。
        30分ごとに実行されます。
        """
        # 通知先のチャンネルを取得
        channel = self.bot.get_channel(self.channel_id)
        self.sent_tweets = self.load_sent_tweets()
        # 最新ツイートIDを取得
        last_id = await self.get_last_tweets_id()
        if last_id in self.sent_tweets:
            # 既に送信済みの場合は、リストの最初の要素を更新して終了
            self.sent_tweets[0] = last_id
            return

        # 新しいツイートがあった場合、通知メッセージを送信
        await channel.send(f"新しいツイートがあるよ～ {self.x_user}: https://twitter.com/{self.x_user}/status/{last_id}")
        # 送信済みツイートIDを保存
        self.save_sent_tweets([last_id])

    @fetch_tweets_task.before_loop
    async def before_fetch_tweets(self):
        """
        定期タスクが開始する前に、Botが完全に起動するのを待機する関数。
        """
        await self.bot.wait_until_ready()

    def cog_unload(self):
        """
        このCogがアンロードされる際に、定期タスクをキャンセルする関数。
        """
        self.fetch_tweets_task.cancel()


async def setup(bot: commands.Bot):
    """
    このCogをBotに登録するためのセットアップ関数。
    """
    await bot.add_cog(TweetCog(bot))
    print("TweetCog loaded.")
