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

    # Modified get_tweet_ids_playwright method to exclude retweets
    async def get_tweet_ids_playwright(self, username, count=2):
        """
        Get tweet IDs using Playwright to bypass X/Twitter's blocking
        Modified to exclude retweets/reposts

        Args:
            username (str): Twitter username (without @)
            count (int): Number of tweet IDs to retrieve (default: 2)

        Returns:
            list: List of tweet IDs (excluding retweets)
        """

        async with async_playwright() as p:
            # Launch browser with options to appear more human-like
            browser = await p.chromium.launch(
                headless=True,
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

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                url = f"https://X.com/{username}"
                print(f"[{timestamp}] Navigating to {url}...")

                # Navigate to the page
                await page.goto(url, wait_until='networkidle', timeout=30000)

                # Wait a bit for dynamic content to load
                await page.wait_for_timeout(3000)

                # Try to handle login popup or other overlays
                try:
                    close_buttons = await page.query_selector_all('[aria-label="Close"]')
                    for button in close_buttons:
                        await button.click()
                        await page.wait_for_timeout(500)
                except:
                    pass

                tweet_ids = []
                seen_ids = set()

                # Method 1: Look for tweet articles and filter out retweets
                articles = await page.query_selector_all('article[data-testid="tweet"]')

                for article in articles:
                    if len(tweet_ids) >= count:
                        break

                    try:
                        # Check if this is a retweet by looking for retweet indicators
                        is_retweet = await self.is_retweet(article)

                        if is_retweet:
                            print("Skipping retweet...")
                            continue

                        # Look for status links within each article
                        status_link = await article.query_selector('a[href*="/status/"]')
                        if status_link:
                            href = await status_link.get_attribute('href')
                            if href:
                                match = re.search(r'/status/(\d+)', href)
                                if match:
                                    tweet_id = match.group(1)
                                    if tweet_id not in seen_ids:
                                        tweet_ids.append(tweet_id)
                                        seen_ids.add(tweet_id)
                                        print(f"Found original tweet ID: {tweet_id}")
                    except Exception as e:
                        print(f"Error processing article: {e}")
                        continue

                # Method 2: Fallback - Look for tweet links and filter by URL pattern
                if len(tweet_ids) < count:
                    tweet_links = await page.query_selector_all('a[href*="/status/"]')

                    for link in tweet_links:
                        if len(tweet_ids) >= count:
                            break

                        try:
                            href = await link.get_attribute('href')
                            if href:
                                # Check if the link belongs to the target user (not a retweet)
                                if f"/{username}/status/" in href:
                                    match = re.search(r'/status/(\d+)', href)
                                    if match:
                                        tweet_id = match.group(1)
                                        if tweet_id not in seen_ids:
                                            tweet_ids.append(tweet_id)
                                            seen_ids.add(tweet_id)
                                            print(f"Found tweet ID from link: {tweet_id}")
                        except:
                            continue

                # Method 3: Scroll and wait for more tweets if needed
                if len(tweet_ids) < count:
                    print("Scrolling to load more tweets...")
                    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    await page.wait_for_timeout(2000)

                    # Try again after scrolling with retweet filtering
                    new_articles = await page.query_selector_all('article[data-testid="tweet"]')
                    for article in new_articles:
                        if len(tweet_ids) >= count:
                            break

                        try:
                            is_retweet = await self.is_retweet(article)
                            if is_retweet:
                                continue

                            status_link = await article.query_selector('a[href*="/status/"]')
                            if status_link:
                                href = await status_link.get_attribute('href')
                                if href and f"/{username}/status/" in href:
                                    match = re.search(r'/status/(\d+)', href)
                                    if match:
                                        tweet_id = match.group(1)
                                        if tweet_id not in seen_ids:
                                            tweet_ids.append(tweet_id)
                                            seen_ids.add(tweet_id)
                                            print(f"Found tweet ID after scroll: {tweet_id}")
                        except:
                            continue

                return tweet_ids[:count]

            except Exception as e:
                print(f"Error during scraping: {e}")
                return []

            finally:
                await browser.close()

    async def is_retweet(self, article_element):
        """
        Check if a tweet article element represents a retweet

        Args:
            article_element: Playwright element representing a tweet article

        Returns:
            bool: True if it's a retweet, False otherwise
        """
        try:
            # Method 1: Look for retweet text indicators
            retweet_indicators = [
                '[data-testid="socialContext"]',  # "Username retweeted" text
                'span:has-text("retweeted")',
                'span:has-text("Retweeted")',
                'span:has-text("reposted")',
                'span:has-text("Reposted")',
                '[aria-label*="retweet"]',
                '[aria-label*="Retweet"]'
            ]

            for indicator in retweet_indicators:
                element = await article_element.query_selector(indicator)
                if element:
                    return True

            # Method 2: Check for retweet icon (🔁 or SVG)
            retweet_icons = await article_element.query_selector_all('svg')
            for icon in retweet_icons:
                try:
                    # Check if the SVG has retweet-related attributes
                    viewbox = await icon.get_attribute('viewBox')
                    if viewbox and '24 24' in viewbox:
                        # Check the path data for retweet icon pattern
                        path = await icon.query_selector('path')
                        if path:
                            d_attr = await path.get_attribute('d')
                            if d_attr and ('M4.5 3.88' in d_attr or 'M23.77 15.67' in d_attr):
                                return True
                except:
                    continue

            # Method 3: Check if the tweet link doesn't belong to the target user
            status_link = await article_element.query_selector('a[href*="/status/"]')
            if status_link:
                href = await status_link.get_attribute('href')
                if href and f"/{self.x_user}/status/" not in href:
                    return True

            # Method 4: Look for "Show this thread" or quote tweet indicators
            quote_indicators = [
                '[data-testid="card.layoutLarge.detail"]',
                '[data-testid="card.layoutSmall.detail"]',
                'div[role="link"]'
            ]

            for indicator in quote_indicators:
                element = await article_element.query_selector(indicator)
                if element:
                    # Additional check to see if it's a quote tweet
                    inner_text = await element.inner_text() if element else ""
                    if "Show this thread" in inner_text:
                        return True

            return False

        except Exception as e:
            print(f"Error checking if retweet: {e}")
            return False

    # Also modify the Nitter method to exclude retweets
    async def get_tweet_ids_nitter(self, username, count=2):
        """
        Alternative method using Nitter instances with Playwright
        Modified to exclude retweets
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
                        print(f"Trying Nitter instance: {instance}")

                        await page.goto(url, timeout=15000)
                        await page.wait_for_timeout(2000)

                        tweet_ids = []
                        seen_ids = set()

                        # Look for tweet containers in Nitter
                        tweet_containers = await page.query_selector_all('.timeline-item')

                        for container in tweet_containers:
                            if len(tweet_ids) >= count:
                                break

                            try:
                                # Check if this is a retweet in Nitter
                                retweet_indicator = await container.query_selector('.retweet-header, .quote-link')
                                if retweet_indicator:
                                    print("Skipping retweet in Nitter...")
                                    continue

                                # Look for the tweet link
                                tweet_link = await container.query_selector('a[href*="/status/"]')
                                if tweet_link:
                                    href = await tweet_link.get_attribute('href')
                                    if href and f"/{username}/status/" in href:
                                        match = re.search(r'/status/(\d+)', href)
                                        if match:
                                            tweet_id = match.group(1)
                                            if tweet_id not in seen_ids:
                                                tweet_ids.append(tweet_id)
                                                seen_ids.add(tweet_id)
                            except:
                                continue

                        if tweet_ids:
                            print(f"Successfully got {len(tweet_ids)} original tweet IDs from {instance}")
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
            else:
                await ctx.reply("ツイートの取得に失敗しました。")

    @tasks.loop(minutes=30)
    async def fetch_tweets_task(self):
        """
        定期的に最新ツイートをチェックし、新しいツイートがあれば指定のDiscordチャンネルに通知を送信するタスク。
        30分ごとに実行されます。
        ピン留めされたツイートを除外し、真に新しいツイートのみを検出します。
        """
        # 通知先のチャンネルを取得
        channel = self.bot.get_channel(self.channel_id)
        self.sent_tweets = self.load_sent_tweets()

        # 複数のツイートIDを取得（ピン留めツイートを考慮して多めに取得）
        tweet_ids = await self.get_tweet_ids_playwright(self.x_user, 3)
        if not tweet_ids:
            print("\nMain method failed, trying Nitter instances...")
            tweet_ids = await self.get_tweet_ids_nitter(self.x_user, 3)
            if not tweet_ids:
                print("Failed to fetch any tweet IDs")
                return

        # 送信済みツイートがない場合は、最初のツイートIDを保存して終了
        if not self.sent_tweets:
            self.save_sent_tweets([tweet_ids[0]])
            return

        # 最後に送信したツイートIDを取得
        last_sent_tweet_id = self.sent_tweets[0] if self.sent_tweets else None

        # 新しいツイートを探す（送信済みリストにないもので、IDが最後に送信したものより大きいもの）
        new_tweets = []
        for tweet_id in tweet_ids:
            # ツイートIDは時系列順なので、数値として比較できる
            if tweet_id not in self.sent_tweets:
                if last_sent_tweet_id is None or int(tweet_id) > int(last_sent_tweet_id):
                    new_tweets.append(tweet_id)

        if not new_tweets:
            # 新しいツイートがない場合
            return

        # 最新の新しいツイート（IDが最大のもの）を取得
        newest_tweet_id = max(new_tweets, key=lambda x: int(x))

        # 新しいツイートがあった場合、通知メッセージを送信
        await channel.send(
            f"新しいツイートがあるよ～ {self.x_user}: https://X.com/{self.x_user}/status/{newest_tweet_id}")

        # 送信済みツイートIDを更新（最新のものを先頭に追加し、古いものは制限）
        updated_sent_tweets = [newest_tweet_id]
        # 既存の送信済みリストから重複を除いて最大10件まで保持
        for tweet_id in self.sent_tweets:
            if tweet_id != newest_tweet_id and len(updated_sent_tweets) < 10:
                updated_sent_tweets.append(tweet_id)

        self.save_sent_tweets(updated_sent_tweets)

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
