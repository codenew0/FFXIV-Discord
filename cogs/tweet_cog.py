# cogs/tweet_cog.py
import discord
import os
from discord.ext import commands, tasks
from playwright.async_api import async_playwright
import json

# Resolve the file path relative to your project root.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SENT_TWEETS_FILE = os.path.join(BASE_DIR, "sent_tweets.json")


class TweetCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Load necessary configuration from config.json
        with open("config.json", "r") as f:
            config = json.load(f)
        self.channel_id = config["CHANNEL_ID"]
        self.x_user = "FF_XIV_JP"
        self.data_file_tweets = config.get("DATA_FILE_TWEETS", "sent_tweets.json")
        self.sent_tweets = self.load_sent_tweets()
        self.fetch_tweets_task.start()

    def load_sent_tweets(self):
        try:
            with open(SENT_TWEETS_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_sent_tweets(self, tweets_id):
        # Save only the last 10 tweet IDs to keep the file small
        with open(self.data_file_tweets, "w") as f:
            json.dump(tweets_id, f, indent=4)

    async def get_last_tweets_id(self):
        async with async_playwright() as p:
            # Chromium ブラウザをヘッドレスモードで起動
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # 指定の URL にアクセス
            await page.goto("https://x.com/FF_XIV_JP", timeout=10000)

            # /FF_XIV_JP/status/ で始まるリンクが読み込まれるのを待つ
            await page.wait_for_selector("a[href^='/FF_XIV_JP/status/']")

            # 最初に見つかったリンクを取得
            link = await page.query_selector("a[href^='/FF_XIV_JP/status/']")
            if link is None:
                print("指定のリンクが見つかりませんでした。")
                await browser.close()
                return None

            # リンクの href 属性を取得（例: "/FF_XIV_JP/status/IDNumberxxx"）
            href = await link.get_attribute("href")
            if not href:
                print("リンクの href 属性が取得できませんでした。")
                await browser.close()
                return None

            # href の末尾の部分（ID）を抽出する
            id_value = href.rsplit('/', 1)[-1]
            await browser.close()

            return id_value

    @commands.command(name="X")
    async def last_tweets(self, ctx: commands.Context):
        """
                Get the last tweets
        """
        async with ctx.typing():
            last_id = await self.get_last_tweets_id()
            link = f"https://x.com/FF_XIV_JP/status/{last_id}"
            async with async_playwright() as p:
                # Chromium ブラウザをヘッドレスモードで起動
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(link, timeout=10000)

                await page.wait_for_selector("article")
                article = await page.query_selector("article")
                if article is None:
                    await ctx.reply("Error: cannot find article element")
                    await browser.close()
                    return

                tweets_parh = "tweets.png"
                await article.screenshot(path=tweets_parh)
                embed = discord.Embed(
                    title=f"{link}",
                    color=discord.Color.blue()
                )
                file = discord.File(tweets_parh, filename="tweets.png")

                # Reference the attached file in the embed
                embed.set_image(url="attachment://tweets.png")

                await ctx.reply(embed=embed, file=file, mention_author=False)

    @tasks.loop(minutes=20)
    async def fetch_tweets_task(self):
        channel = self.bot.get_channel(self.channel_id)

        last_id = await self.get_last_tweets_id()
        if last_id in self.sent_tweets:
            self.sent_tweets[0] = last_id
            return

        await channel.send(f"New tweet from {self.x_user}: https://twitter.com/{self.x_user}/status/{last_id}")
        self.save_sent_tweets(self.sent_tweets)

    @fetch_tweets_task.before_loop
    async def before_fetch_tweets(self):
        await self.bot.wait_until_ready()

    def cog_unload(self):
        self.fetch_tweets_task.cancel()


async def setup(bot: commands.Bot):
    await bot.add_cog(TweetCog(bot))
    print("TweetCog loaded.")
