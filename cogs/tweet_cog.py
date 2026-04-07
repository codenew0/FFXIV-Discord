# cogs/tweet_cog.py
import os
import json
import re
import asyncio
from datetime import datetime
from discord.ext import commands, tasks
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# プロジェクトルートからの相対パスでファイルパスを解決
BASE_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SENT_TWEETS_FILE = os.path.join(BASE_DIR, "sent_tweets.json")


class TweetCog(commands.Cog):
    """
    X (旧Twitter) の最新ツイートを取得し、Discordに通知するCog。
    定期的にツイートをチェックし、新規ツイートがあれば通知します。
    """

    def __init__(self, bot: commands.Bot):
        """
        初期化処理。
        設定ファイルの読み込み、送信済みツイートの読み込み、定期タスクの開始を行います。
        """
        self.bot = bot
        
        # 設定ファイルの読み込み
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        self.channel_id = config["CHANNEL_ID"]
        self.x_user = "FF_XIV_JP"
        self.data_file_tweets = config.get("DATA_FILE_TWEETS", "sent_tweets.json")
        self.sent_tweets = self.load_sent_tweets()
        
        # 定期タスクの開始
        self.fetch_tweets_task.start()

    async def get_tweet_ids_playwright(self, username: str, count: int = 2) -> list:
        """
        Playwrightを使用してツイートIDを取得します（リツイートは除外）。

        Args:
            username: Xのユーザー名（@なし）
            count: 取得するツイート数（デフォルト: 2）

        Returns:
            ツイートIDのリスト（リツイートを除く）
        """
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(
                    headless=True,  # 新しいヘッドレスモードを自動使用
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--disable-gpu'
                    ]
                )
            except Exception as e:
                print(f"ブラウザ起動エラー: {e}")
                return []

            try:
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                
                page = await context.new_page()

                # HTTPヘッダーを設定
                await page.set_extra_http_headers({
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                })

                url = f"https://x.com/{username}"
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{timestamp}] {url} にアクセス中...")

                # タイムアウトを長めに設定し、待機条件を緩和
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                except PlaywrightTimeout:
                    print("ページ読み込みタイムアウト。部分的に読み込まれた内容で続行します...")
                
                # DOMが安定するまで待機
                await page.wait_for_timeout(5000)

                # ポップアップを閉じる
                try:
                    close_buttons = await page.query_selector_all('[aria-label="閉じる"], [aria-label="Close"]')
                    for button in close_buttons:
                        try:
                            await button.click(timeout=1000)
                            await page.wait_for_timeout(500)
                        except Exception:
                            pass
                except Exception:
                    pass

                tweet_ids = []
                seen_ids = set()

                # スクレイピング試行回数を増やす
                max_attempts = 3
                for attempt in range(max_attempts):
                    if len(tweet_ids) >= count:
                        break
                    
                    print(f"ツイート取得試行 {attempt + 1}/{max_attempts}")
                    
                    # 方法1: ツイート記事から取得
                    articles = await page.query_selector_all('article[data-testid="tweet"]')
                    print(f"見つかった記事数: {len(articles)}")

                    for article in articles:
                        if len(tweet_ids) >= count:
                            break

                        try:
                            if await self._is_retweet(article):
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
                                            print(f"取得: {tweet_id}")
                        except Exception as e:
                            print(f"記事処理エラー: {e}")
                            continue

                    # 十分なツイートが取得できた場合は終了
                    if len(tweet_ids) >= count:
                        break
                    
                    # スクロールして再試行
                    if attempt < max_attempts - 1:
                        print("スクロールして追加読み込み中...")
                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        await page.wait_for_timeout(3000)

                # 方法2: すべてのステータスリンクから取得（フォールバック）
                if len(tweet_ids) < count:
                    print("フォールバック: すべてのリンクから検索中...")
                    all_links = await page.query_selector_all('a[href*="/status/"]')
                    
                    for link in all_links:
                        if len(tweet_ids) >= count:
                            break
                        
                        try:
                            href = await link.get_attribute('href')
                            if href and f"/{username}/status/" in href:
                                match = re.search(r'/status/(\d+)', href)
                                if match:
                                    tweet_id = match.group(1)
                                    if tweet_id not in seen_ids:
                                        tweet_ids.append(tweet_id)
                                        seen_ids.add(tweet_id)
                                        print(f"リンクから取得: {tweet_id}")
                        except Exception:
                            continue

                print(f"最終取得数: {len(tweet_ids)}")
                return tweet_ids[:count]

            except Exception as e:
                print(f"スクレイピングエラー: {e}")
                return []

            finally:
                try:
                    await context.close()
                except Exception:
                    pass
                await browser.close()

    async def _is_retweet(self, article_element) -> bool:
        """
        ツイート要素がリツイートかどうかを判定します。

        Args:
            article_element: Playwright要素（ツイート記事）

        Returns:
            リツイートの場合True、オリジナルツイートの場合False
        """
        try:
            # 方法1: リツイートを示すテキストを探す
            retweet_indicators = [
                '[data-testid="socialContext"]',
                'span:has-text("がリツイートしました")',
                'span:has-text("retweeted")',
                'span:has-text("Retweeted")',
            ]

            for indicator in retweet_indicators:
                try:
                    element = await article_element.query_selector(indicator)
                    if element:
                        return True
                except Exception:
                    continue

            # 方法2: ツイートリンクが対象ユーザーのものかチェック
            try:
                status_link = await article_element.query_selector('a[href*="/status/"]')
                if status_link:
                    href = await status_link.get_attribute('href')
                    if href and f"/{self.x_user}/status/" not in href:
                        return True
            except Exception:
                pass

            return False

        except Exception as e:
            print(f"リツイート判定エラー: {e}")
            return False

    async def get_tweet_ids_vxtwitter(self, username: str, count: int = 2) -> list:
        """
        vxtwitterを使用してツイートIDを取得します（代替手段）。
        vxtwitterは軽量で高速なため、タイムアウトが発生しにくいです。

        Args:
            username: Xのユーザー名
            count: 取得するツイート数

        Returns:
            ツイートIDのリスト
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            try:
                page = await browser.new_page()
                url = f"https://vxtwitter.com/{username}"
                print(f"vxTwitterを試行中: {url}")

                try:
                    await page.goto(url, timeout=20000, wait_until='domcontentloaded')
                    await page.wait_for_timeout(2000)

                    tweet_ids = []
                    seen_ids = set()

                    # ツイートリンクを探す
                    links = await page.query_selector_all('a[href*="/status/"]')

                    for link in links:
                        if len(tweet_ids) >= count:
                            break

                        try:
                            href = await link.get_attribute('href')
                            if href and f"/{username}/status/" in href:
                                match = re.search(r'/status/(\d+)', href)
                                if match:
                                    tweet_id = match.group(1)
                                    if tweet_id not in seen_ids:
                                        tweet_ids.append(tweet_id)
                                        seen_ids.add(tweet_id)
                        except Exception:
                            continue

                    if tweet_ids:
                        print(f"vxTwitterから{len(tweet_ids)}件取得しました")
                        return tweet_ids[:count]

                except Exception as e:
                    print(f"vxTwitterエラー: {e}")
                    return []

            finally:
                await browser.close()

        return []

    async def get_tweet_ids_api_fallback(self, username: str, count: int = 2) -> list:
        """
        最終手段: 既知のツイートIDパターンから推測
        （この方法は推奨されませんが、完全にアクセスできない場合の最後の手段）
        """
        print("警告: すべての取得方法が失敗しました")
        return []

    def load_sent_tweets(self) -> list:
        """
        送信済みツイートIDをJSONファイルから読み込みます。

        Returns:
            送信済みツイートIDのリスト
        """
        try:
            with open(SENT_TWEETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_sent_tweets(self, tweets_id: list):
        """
        ツイートIDをJSONファイルに保存します。

        Args:
            tweets_id: 保存するツイートIDのリスト
        """
        with open(self.data_file_tweets, "w", encoding="utf-8") as f:
            json.dump(tweets_id, f, indent=4, ensure_ascii=False)

    @commands.command(name="X")
    async def last_tweets(self, ctx: commands.Context, count: int = 1):
        """
        FF_XIV_JPの最新ツイートを表示します。
        
        使い方: !X [件数]
        例: !X 3
        """
        async with ctx.typing():
            tweet_ids = await self.get_tweet_ids_playwright(self.x_user, count)

            # 代替手段1: vxtwitter
            if not tweet_ids:
                print("vxTwitterを試行します...")
                tweet_ids = await self.get_tweet_ids_vxtwitter(self.x_user, count)

            if tweet_ids:
                messages = []
                for i, tweet_id in enumerate(tweet_ids, 1):
                    link = f"https://x.com/{self.x_user}/status/{tweet_id}"
                    messages.append(f"ツイート {i}: {link}")
                await ctx.reply("\n".join(messages))
            else:
                await ctx.reply(
                    "ツイートの取得に失敗しました。\n"
                    "Xのサーバーが混雑しているか、一時的にアクセスできない可能性があります。\n"
                    "しばらく待ってから再度お試しください。"
                )

    @tasks.loop(minutes=30)
    async def fetch_tweets_task(self):
        """
        30分ごとに最新ツイートをチェックし、新規ツイートがあればDiscordに通知します。
        """
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            print(f"エラー: チャンネルID {self.channel_id} が見つかりません")
            return

        self.sent_tweets = self.load_sent_tweets()

        # メイン手段
        tweet_ids = await self.get_tweet_ids_playwright(self.x_user, 3)
        
        # 代替手段1: vxtwitter
        if not tweet_ids:
            print("vxTwitterを試行します...")
            tweet_ids = await self.get_tweet_ids_vxtwitter(self.x_user, 3)
        
        if not tweet_ids:
            print("ツイートIDの取得に失敗しました。次回の実行を待ちます。")
            return

        # 初回実行時
        if not self.sent_tweets:
            self.save_sent_tweets([tweet_ids[0]])
            print("初回実行: 最新ツイートIDを保存しました")
            return

        last_sent_tweet_id = self.sent_tweets[0]

        # 新規ツイートを検出
        new_tweets = []
        for tweet_id in tweet_ids:
            if tweet_id not in self.sent_tweets and int(tweet_id) > int(last_sent_tweet_id):
                new_tweets.append(tweet_id)

        if not new_tweets:
            print("新規ツイートはありません")
            return

        newest_tweet_id = max(new_tweets, key=lambda x: int(x))

        # 通知を送信
        try:
            await channel.send(
                f"🐦 新しいツイートがあります！\n"
                f"https://x.com/{self.x_user}/status/{newest_tweet_id}"
            )
            print(f"新規ツイートを通知しました: {newest_tweet_id}")
        except Exception as e:
            print(f"通知送信エラー: {e}")
            return

        # 送信済みリストを更新
        updated_sent_tweets = [newest_tweet_id]
        for tweet_id in self.sent_tweets:
            if tweet_id != newest_tweet_id and len(updated_sent_tweets) < 10:
                updated_sent_tweets.append(tweet_id)

        self.save_sent_tweets(updated_sent_tweets)

    @fetch_tweets_task.before_loop
    async def before_fetch_tweets(self):
        """定期タスク開始前にBotの準備完了を待機します。"""
        await self.bot.wait_until_ready()
        print("TweetCog: 定期タスクを開始しました")

    @fetch_tweets_task.error
    async def fetch_tweets_task_error(self, error):
        """定期タスクのエラーハンドリング"""
        print(f"定期タスクエラー: {error}")
        # エラーが発生しても次回の実行は継続

    def cog_unload(self):
        """Cogアンロード時に定期タスクをキャンセルします。"""
        self.fetch_tweets_task.cancel()
        print("TweetCog: 定期タスクを停止しました")


async def setup(bot: commands.Bot):
    """BotにTweetCogを追加します。"""
    await bot.add_cog(TweetCog(bot))
    print("TweetCog loaded.")