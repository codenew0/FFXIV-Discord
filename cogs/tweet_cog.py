# cogs/tweet_cog.py
import os
from discord.ext import commands, tasks
from playwright.async_api import async_playwright
import json
import re
from datetime import datetime

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

    async def get_tweet_ids_playwright(self, username, count=2):
        """
        Get tweet IDs using Playwright to bypass X/Twitter's blocking

        Args:
            username (str): Twitter username (without @)
            count (int): Number of tweet IDs to retrieve (default: 2)

        Returns:
            list: List of tweet IDs
        """

        async with async_playwright() as p:
            # Launch browser with options to appear more human-like
            browser = await p.chromium.launch(
                headless=True,  # Set to False if you want to see the browser
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )

            try:
                # Create new page with realistic viewport
                page = await browser.new_page(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )

                # Set additional headers to look more like a real browser
                await page.set_extra_http_headers({
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Cache-Control': 'max-age=0'
                })

                url = f"https://twitter.com/{username}"
                print(f"Navigating to {url}...")

                # Navigate to the page
                await page.goto(url, wait_until='networkidle', timeout=30000)

                # Wait a bit for dynamic content to load
                await page.wait_for_timeout(3000)

                # Try to handle login popup or other overlays
                try:
                    # Close any modals that might appear
                    close_buttons = await page.query_selector_all('[aria-label="Close"]')
                    for button in close_buttons:
                        await button.click()
                        await page.wait_for_timeout(500)
                except:
                    pass

                tweet_ids = []

                # Method 1: Look for tweet links in the page
                # print("Looking for tweet links...")
                tweet_links = await page.query_selector_all('a[href*="/status/"]')

                seen_ids = set()
                for link in tweet_links:
                    try:
                        href = await link.get_attribute('href')
                        if href:
                            match = re.search(r'/status/(\d+)', href)
                            if match:
                                tweet_id = match.group(1)
                                if tweet_id not in seen_ids and len(tweet_ids) < count:
                                    tweet_ids.append(tweet_id)
                                    seen_ids.add(tweet_id)
                                    print(f"Found tweet ID: {tweet_id}")
                    except:
                        continue

                # Method 2: Look for article elements with data attributes
                if len(tweet_ids) < count:
                    # print("Looking for tweet articles...")
                    articles = await page.query_selector_all('article[data-testid="tweet"]')

                    for article in articles[:count]:
                        try:
                            # Look for status links within each article
                            status_link = await article.query_selector('a[href*="/status/"]')
                            if status_link:
                                href = await status_link.get_attribute('href')
                                if href:
                                    match = re.search(r'/status/(\d+)', href)
                                    if match:
                                        tweet_id = match.group(1)
                                        if tweet_id not in seen_ids and len(tweet_ids) < count:
                                            tweet_ids.append(tweet_id)
                                            seen_ids.add(tweet_id)
                                            # print(f"Found tweet ID from article: {tweet_id}")
                        except:
                            continue

                # Method 3: Scroll and wait for more tweets if needed
                if len(tweet_ids) < count:
                    # print("Scrolling to load more tweets...")
                    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    await page.wait_for_timeout(2000)

                    # Try again after scrolling
                    new_links = await page.query_selector_all('a[href*="/status/"]')
                    for link in new_links:
                        try:
                            href = await link.get_attribute('href')
                            if href:
                                match = re.search(r'/status/(\d+)', href)
                                if match:
                                    tweet_id = match.group(1)
                                    if tweet_id not in seen_ids and len(tweet_ids) < count:
                                        tweet_ids.append(tweet_id)
                                        seen_ids.add(tweet_id)
                                        # print(f"Found tweet ID after scroll: {tweet_id}")
                        except:
                            continue

                return tweet_ids[:count]

            except Exception as e:
                print(f"Error during scraping: {e}")
                return []

            finally:
                await browser.close()

    async def get_tweet_ids_nitter(self, username, count=2):
        """
        Alternative method using Nitter instances with Playwright
        """
        nitter_instances = [
            'nitter.net',
            'nitter.it',
            'nitter.nixnet.services',
            'nitter.poast.org'
        ]

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            try:
                page = await browser.new_page()

                for instance in nitter_instances:
                    try:
                        url = f"https://{instance}/{username}"
                        # print(f"Trying Nitter instance: {instance}")

                        await page.goto(url, timeout=15000)
                        await page.wait_for_timeout(2000)

                        tweet_ids = []

                        # Look for tweet links in Nitter
                        tweet_links = await page.query_selector_all('.tweet-link, a[href*="/status/"]')

                        for link in tweet_links[:count]:
                            try:
                                href = await link.get_attribute('href')
                                if href:
                                    match = re.search(r'/status/(\d+)', href)
                                    if match:
                                        tweet_ids.append(match.group(1))
                            except:
                                continue

                        if tweet_ids:
                            # print(f"Successfully got {len(tweet_ids)} IDs from {instance}")
                            return tweet_ids[:count]

                    except Exception as e:
                        print(f"Failed to fetch from {instance}: {e}")
                        continue

                return []

            finally:
                await browser.close()

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

    async def get_last_tweets_id_old(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # 指定のTwitter（X）アカウントページにアクセス
            await page.goto("https://x.com/FF_XIV_JP", timeout=60000)

            # ツイートリンク（/FF_XIV_JP/status/で始まる）の読み込みを待つ
            await page.wait_for_selector("a[href^='/FF_XIV_JP/status/']")

            # ツイートリンクを2つ探す（末尾が数字のみのものを対象）
            links = await page.query_selector_all("a[href^='/FF_XIV_JP/status/']")
            if links is None:
                print("指定のリンクが見つかりませんでした。")
                await browser.close()
                return None

            print(links)
            valid_links = []

            for link in links:
                href = await link.get_attribute("href")
                if href and re.match(r"^/FF_XIV_JP/status/\d+$", href):  # 数字のみで終わるリンクのみ取得
                    valid_links.append(link)
                    print(valid_links)

            if len(valid_links) < 2:
                print("ツイートが2件未満です。")
                await browser.close()
                return None

            tweet_data = []
            for link in valid_links[:2]:  # 最初の2つを取得
                href = await link.get_attribute("href")
                time_element = await link.query_selector("time")
                datetime_value = await time_element.get_attribute("datetime") if time_element else None

                if href and datetime_value:
                    tweet_id = href.rsplit('/', 1)[-1]
                    tweet_data.append((tweet_id, datetime_value))

            await browser.close()

            if len(tweet_data) < 2:
                print("有効なツイートが2件取得できませんでした。")
                return None

            # 日付で比較し、新しい方のIDを返す
            tweet_data.sort(key=lambda x: datetime.fromisoformat(x[1]), reverse=True)
            return tweet_data[0][0]

    @commands.command(name="X")
    async def last_tweets(self, ctx: commands.Context, count: int = 1):
        """
        公式Xを覗く！（FF_XIV_JPの最後のツイートを見る）
        """
        async with ctx.typing():
            # 最新ツイートIDを取得
            tweet_ids = await self.get_tweet_ids_playwright(self.x_user, count)

            if not tweet_ids:
                print("\nMain method failed, trying Nitter instances...")
                tweet_ids = await self.get_tweet_ids_nitter(self.x_user, count)

            if tweet_ids:
                # ツイートのURLを生成
                messages = []
                for i, tweet_id in enumerate(tweet_ids, 1):
                    link = f"https://x.com/{self.x_user}/status/{tweet_id}"
                    messages.append(f"ツイート {i}: {link}")

                await ctx.reply("\n".join(messages))

                # print(f"\n✅ Successfully found {len(tweet_ids)} tweet ID(s):")
                # print("-" * 40)
                # for i, tweet_id in enumerate(tweet_ids, 1):
                #     print(f"Tweet {i} ID: {tweet_id}")
                #     print(f"URL: https://twitter.com/{username}/status/{tweet_id}")
                #     print("-" * 40)
            else:
                # print("\n❌ No tweet IDs found. Possible reasons:")
                # print("1. Account is private or suspended")
                # print("2. Account doesn't exist")
                # print("3. Twitter/X has updated their structure")
                # print("4. Network connectivity issues")
                # print("5. All methods were blocked")
                # print("\nTip: Try changing the username or running with headless=False to debug")

                await ctx.reply("ツイートの取得に失敗しました。")

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
        tweet_ids = await self.get_tweet_ids_playwright(self.x_user, 1)
        if not tweet_ids:
            print("\nMain method failed, trying Nitter instances...")
            tweet_ids = await self.get_tweet_ids_nitter(self.x_user, 1)

        if tweet_ids[0] in self.sent_tweets:
            # 既に送信済みの場合は、リストの最初の要素を更新して終了
            self.sent_tweets[0] = tweet_ids[0]
            return

        # 新しいツイートがあった場合、通知メッセージを送信
        await channel.send(f"新しいツイートがあるよ～ {self.x_user}: https://twitter.com/{self.x_user}/status/{tweet_ids[0]}")
        # 送信済みツイートIDを保存
        self.save_sent_tweets([tweet_ids[0]])

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
