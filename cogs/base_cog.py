# cogs/base_cog.py
import json
import re
from pathlib import Path
from typing import Optional, Dict, List
import requests
from bs4 import BeautifulSoup
from discord.ext import commands


class ConfigManager:
    """設定ファイルの管理クラス"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self._config = None
    
    @property
    def config(self) -> Dict:
        """設定を読み込む（キャッシュ付き）"""
        if self._config is None:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"❌ 設定ファイルの読み込みエラー: {e}")
                self._config = {}
        return self._config
    
    def get_worlds_jp(self) -> List[str]:
        """日本語ワールドリストを取得"""
        worlds_file = self.config.get("DATA_FILE_WORLD_JP", "worlds_jp.json")
        try:
            with open(worlds_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"❌ ワールドリストの読み込みエラー: {worlds_file}")
            return []


class LodestoneSearcher:
    """Lodestone検索機能を提供するクラス"""
    
    BASE_URL = "https://jp.finalfantasyxiv.com/lodestone"
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
    
    def search_character(self, character_name: str, world_name: str) -> Optional[str]:
        """
        Lodestoneでキャラクターを検索し、IDを返す
        
        Args:
            character_name: キャラクター名（フルネーム）
            world_name: ワールド名
        
        Returns:
            キャラクターID（見つからない場合はNone）
        """
        # ワールド名が有効かチェック
        valid_worlds = self.config_manager.get_worlds_jp()
        if world_name not in valid_worlds:
            print(f"❌ 無効なワールド名: {world_name}")
            return None
        
        # 検索パラメータ
        params = {
            "q": character_name,
            "worldname": world_name
        }
        
        try:
            url = f"{self.BASE_URL}/character/"
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 検索結果のエントリを取得
            entries = soup.find_all("div", class_="entry")
            
            if not entries:
                print(f"⚠️ キャラクターが見つかりません: {character_name}@{world_name}")
                return None
            
            # 完全一致するキャラクターを探す
            for entry in entries:
                name_element = entry.find("p", class_="entry__name")
                if not name_element:
                    continue
                
                found_name = name_element.get_text(strip=True)
                
                # 名前が完全一致するか確認
                if found_name == character_name:
                    link = entry.find("a", href=re.compile(r"/lodestone/character/\d+/"))
                    if link:
                        match = re.search(r"/lodestone/character/(\d+)/", link["href"])
                        if match:
                            character_id = match.group(1)
                            print(f"✅ キャラクター発見: {character_name} (ID: {character_id})")
                            return character_id
            
            print(f"⚠️ 完全一致するキャラクターが見つかりません: {character_name}")
            return None
            
        except requests.RequestException as e:
            print(f"❌ Lodestone検索エラー: {e}")
            return None
    
    def get_character_url(self, character_id: str) -> str:
        """キャラクターのLodestone URLを生成"""
        return f"{self.BASE_URL}/character/{character_id}/"


class BaseCog(commands.Cog):
    """基本的な機能を提供する基底Cogクラス"""
    
    def __init__(self):
        """BaseCogのコンストラクタ"""
        super().__init__()
        self.config_manager = ConfigManager()
        self.searcher = LodestoneSearcher(self.config_manager)
    
    def lodestone_search(self, character_name: str, world_name: str) -> Optional[str]:
        """
        Lodestoneでキャラクターを検索（互換性のため）
        
        Args:
            character_name: キャラクター名
            world_name: ワールド名
        
        Returns:
            キャラクターID
        """
        return self.searcher.search_character(character_name, world_name)
    
    def get_lodestone_url(self, character_id: str) -> str:
        """キャラクターのLodestone URLを取得"""
        return self.searcher.get_character_url(character_id)