# cogs/tweet_cog.py
import discord
from discord.ext import commands, tasks
import tweepy
import json

class TweetCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Load necessary configuration from config.json
        with open("config.json", "r") as f:
            config = json.load(f)
        self.channel_id = config["CHANNEL_ID"]
        self.bearer_token = config["TWITTER_BEARER_TOKEN"]
        self.x_user = "FF_XIV_JP"
        self.data_file_tweets = config.get("DATA_FILE_TWEETS", "tweets.json")
        self.client = tweepy.Client(bearer_token=self.bearer_token)
        self.sent_tweets = self.load_sent_tweets()
        # self.fetch_tweets_task.start()

    def load_sent_tweets(self):
        try:
            with open(self.data_file_tweets, "r") as f:
                return [int(tweet_id) for tweet_id in json.load(f)]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_sent_tweets(self):
        # Save only the last 10 tweet IDs to keep the file small
        with open(self.data_file_tweets, "w") as f:
            json.dump(self.sent_tweets[-10:], f, indent=4)

    @tasks.loop(minutes=20)
    async def fetch_tweets_task(self):
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            try:
                user = self.client.get_user(username=self.x_user)
                if user.data:
                    user_id = user.data.id
                    response = self.client.get_users_tweets(id=user_id, max_results=5, tweet_fields=["created_at"])
                    if response.data:
                        new_tweets = []
                        for tweet in response.data:
                            if tweet.id not in self.sent_tweets:
                                new_tweets.append(tweet)
                                self.sent_tweets.append(tweet.id)
                        if new_tweets:
                            for tweet in new_tweets:
                                await channel.send(
                                    f"New tweet from {self.x_user}: https://twitter.com/{self.x_user}/status/{tweet.id}"
                                )
                            self.save_sent_tweets()
            except Exception as e:
                print(f"Error fetching tweets: {e}")

    @fetch_tweets_task.before_loop
    async def before_fetch_tweets(self):
        await self.bot.wait_until_ready()

    def cog_unload(self):
        self.fetch_tweets_task.cancel()


async def setup(bot: commands.Bot):
    await bot.add_cog(TweetCog(bot))
    print("TweetCog loaded.")
