# cogs/freetalk_cog.py
import os
from typing import Optional
from discord.ext import commands
from google import genai
from google.genai import types


class ChatPersonality:
    """チャットの性格設定を管理するクラス"""
    
    YANKEE = {
        "name": "ヤンキー",
        "system_instruction": "君はヤンキーだ！ヤンキーの喋り方で話す。威勢がよく、少し荒っぽいが根は悪くない。",
        "empty_message": "何か話したいことあんのか？！",
        "use_search": False
    }
    
    NORMAL = {
        "name": "丁寧",
        "system_instruction": (
            "君は有能なFF14のプロプレイヤーで、ゲーム内の問題を丁寧に回答できる。"
            "他の幅広い知識も持っており、親切で分かりやすく説明する。"
        ),
        "empty_message": "どうされましたか？何かお困りですか？",
        "use_search": True
    }
    
    TSUNDERE_JK = {
        "name": "ツンデレJK",
        "system_instruction": (
            "君はツンデレJKで、口は悪いが根は優しい。素直じゃないが時々デレる。"
            "プライド高めで上から目線だけど、本当は構ってほしい。"
            "語尾に「〜なんだからね！」「べ、別に...」などをつける。"
        ),
        "empty_message": "べ、別に話したいわけじゃないんだからね！",
        "use_search": True
    }


class FreeTalkCog(commands.Cog):
    """
    AIを使ったフリートーク機能を提供するCogクラス
    複数の性格モードでユーザーと対話できる
    """
    
    def __init__(self, bot: commands.Bot):
        """
        FreeTalkCogのコンストラクタ
        
        Args:
            bot: Botのインスタンス
        """
        self.bot = bot
        self.api_key = os.environ.get("AI_API_KEY", "")
        if not self.api_key:
            raise KeyError("AI_API_KEY が環境変数に設定されていません（.env を確認してください）")
        
        self._client: genai.Client | None = None

        # 各性格のチャットを初期化
        self.chats: dict = {
            "yankee": self._create_chat(ChatPersonality.YANKEE),
            "normal": self._create_chat(ChatPersonality.NORMAL),
            "tsundere": self._create_chat(ChatPersonality.TSUNDERE_JK)
        }

    def _ensure_client(self) -> genai.Client:
        """クライアントが閉じていれば再生成して返す。"""
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _create_chat(self, personality: dict) -> any:
        config_params = {
            "system_instruction": personality["system_instruction"],
            "max_output_tokens": 2000,
            "top_k": 2,
            "top_p": 0.5,
            "temperature": 0.5
        }

        if personality.get("use_search", False):
            config_params["tools"] = [types.Tool(google_search=types.GoogleSearch())]

        return self._ensure_client().chats.create(
            model='gemini-2.5-flash',
            config=types.GenerateContentConfig(**config_params)
        )
    
    async def _send_ai_message(
        self, 
        ctx: commands.Context, 
        chat: any, 
        message: str,
        empty_message: str
    ) -> None:
        """
        AIにメッセージを送信して応答を返す共通処理
        
        Args:
            ctx: コマンドのコンテキスト
            chat: 使用するチャットオブジェクト
            message: ユーザーのメッセージ
            empty_message: メッセージが空の場合の返信
        """
        if not message:
            await ctx.reply(empty_message)
            return
        
        async with ctx.typing():
            try:
                response = chat.send_message(message)
                ai_reply = response.text
                
                if not ai_reply:
                    await ctx.reply("❌ AIからの応答が取得できませんでした。")
                    return
                
                # Discord の文字数制限対策
                if len(ai_reply) > 2000:
                    ai_reply = ai_reply[:1900] + "\n\n...(文字数制限のため省略)"
                
                await ctx.reply(ai_reply)
                
            except Exception as e:
                print(f"❌ AI応答エラー: {e}")
                await ctx.reply("❌ エラーが発生しました。もう一度お試しください。")
    
    @commands.command(name="ft", aliases=["freetalk"])
    async def freetalk_yankee(self, ctx: commands.Context, *, message: Optional[str] = None):
        """
        🔥 ヤンキー口調で会話します
        
        使い方: !ft <メッセージ>
        例: !ft おはよう
        """
        await self._send_ai_message(
            ctx, 
            self.chats["yankee"], 
            message,
            ChatPersonality.YANKEE["empty_message"]
        )
    
    @commands.command(name="ftn", aliases=["freetalk_normal"])
    async def freetalk_normal(self, ctx: commands.Context, *, message: Optional[str] = None):
        """
        💼 丁寧な口調で会話します（FF14の知識も豊富）
        
        使い方: !ftn <メッセージ>
        例: !ftn 極ゴルベーザの攻略を教えて
        """
        await self._send_ai_message(
            ctx, 
            self.chats["normal"], 
            message,
            ChatPersonality.NORMAL["empty_message"]
        )
    
    @commands.command(name="ftjk", aliases=["freetalk_jk", "tsundere"])
    async def freetalk_tsundere(self, ctx: commands.Context, *, message: Optional[str] = None):
        """
        💕 ツンデレJK口調で会話します
        
        使い方: !ftjk <メッセージ>
        例: !ftjk こんにちは
        """
        await self._send_ai_message(
            ctx, 
            self.chats["tsundere"], 
            message,
            ChatPersonality.TSUNDERE_JK["empty_message"]
        )
    
    @commands.command(name="reset_chat", hidden=True)
    @commands.is_owner()
    async def reset_chat(self, ctx: commands.Context, mode: str = "all"):
        """
        🔄 チャット履歴をリセットします（Bot所有者のみ）
        
        使い方: !reset_chat [mode]
        mode: yankee, normal, tsundere, all (デフォルト: all)
        """
        modes_to_reset = []
        
        if mode == "all":
            modes_to_reset = ["yankee", "normal", "tsundere"]
        elif mode in self.chats:
            modes_to_reset = [mode]
        else:
            await ctx.reply(f"❌ 無効なモード: {mode}\n使用可能: yankee, normal, tsundere, all")
            return
        
        # クライアントごと作り直すことで接続問題も解消する
        self._client = None

        for mode_name in modes_to_reset:
            personality = {
                "yankee": ChatPersonality.YANKEE,
                "normal": ChatPersonality.NORMAL,
                "tsundere": ChatPersonality.TSUNDERE_JK
            }[mode_name]

            self.chats[mode_name] = self._create_chat(personality)
        
        await ctx.reply(f"✅ チャット履歴をリセットしました: {', '.join(modes_to_reset)}")


async def setup(bot: commands.Bot):
    """このCogをBotに登録"""
    try:
        await bot.add_cog(FreeTalkCog(bot))
        print("✅ FreeTalkCog loaded.")
    except Exception as e:
        print(f"❌ FreeTalkCog の読み込みに失敗: {e}")
        raise