# base_cog.py
from discord.ext import commands
from playwright.async_api import async_playwright
import requests
from bs4 import BeautifulSoup
import json
import re


class BaseCog(commands.Cog):
    def __init__(self):
        """
        BaseCogクラスのコンストラクタ
        """
        super.__init__()

    async def capture_screenshot(self, char_id: str, name_slug: str) -> str:
        """
        指定されたURL ( https://jp.tomestone.gg/character/{char_id}/{name_slug} ) から
        特定の要素を残した状態でスクリーンショットを撮影し、その画像ファイルのパスを返す関数。

        Args:
            char_id (str): キャラクターID
            name_slug (str): キャラクター名スラッグ

        Returns:
            str: スクリーンショットとして保存した画像ファイルのパス
        """
        # スクリーンショットを保存するファイル名
        pathname = "character.png"

        # 非同期でPlaywrightを使用
        async with async_playwright() as p:
            # ヘッドレスモード（画面表示なし）でChromiumを起動
            browser = await p.chromium.launch(headless=True)
            # 新規ページ（タブ）を開く
            page = await browser.new_page()
            # ビューポートサイズを設定
            await page.set_viewport_size({"width": 1280, "height": 1800})
            # 対象のURLを生成しページにアクセス
            url = f"https://jp.tomestone.gg/character/{char_id}/{name_slug}"
            await page.goto(url)

            # 残したい<div>要素のセレクタ
            keep_selector = ".flex.flex-row.flex-1.justify-center"

            # ページ上の不要な要素を削除し、残したい要素だけを残す処理
            await page.evaluate(f'''
                (selector) => {{
                    const keep = document.querySelector(selector);
                    if (!keep) return;

                    // 1) 'keep'要素からdocument.bodyまでDOMツリーをたどり、
                    //    各レベルで 'keep'要素以外の兄弟要素(sibling)を削除する。
                    let current = keep;
                    while (current && current !== document.body) {{
                        const parent = current.parentElement;
                        if (!parent) break;

                        // 兄弟要素のうち、'keep'要素ではないものを削除
                        for (const sibling of parent.children) {{
                            if (sibling !== current) {{
                                sibling.remove();
                            }}
                        }}
                        current = parent;
                    }}

                    // 2) グローバルにある<nav>や<script>なども削除
                    document.querySelectorAll('nav, script').forEach(el => el.remove());
                }}
            ''', keep_selector)

            # 必要な部分だけが残った状態でスクリーンショットを撮影
            await page.screenshot(path=pathname, clip={"x": 0, "y": 0, "width": 1280, "height": 1585})
            # ブラウザを閉じる
            await browser.close()

        return pathname

    def load_worlds_jp(self, data_file_worlds_jp):
        """
        日本語ワールド名のリストを格納したJSONファイルを読み込む関数。

        Args:
            data_file_worlds_jp (str): JSONファイルのパス

        Returns:
            list or dict: ロードに成功すればJSONデータを返し、
                          失敗した場合は空のリストを返す
        """
        try:
            with open(data_file_worlds_jp, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # ファイルが見つからない、またはJSONとして解釈できない場合は空のリストを返す
            return []

    def lodestone_search(self, query: str, worldname: str):
        """
        Lodestone上で、キャラクター名(query)とワールド名(worldname)を用いて検索し、
        一致するキャラクターのIDを取得する関数。

        指定したワールド名(worldname)が、あらかじめ用意されている日本語ワールド名のリストに
        含まれているかを確認した上で検索を実行する。

        取得したエントリのうち、class="entry" を持つ要素のみを対象とし、
        名前が完全一致するものを探して、そこからキャラクターIDを抽出する。

        Args:
            query (str): 検索したいキャラクター名
            worldname (str): 検索対象のワールド名

        Returns:
            str or None: 見つかった最初のキャラクターIDを文字列で返し、見つからない場合はNoneを返す
        """
        # 設定ファイル(config.json)を読み込む
        with open("config.json", "r") as f:
            config = json.load(f)

        # 日本語ワールド名のリストを読み込む
        data_file_worlds_jp = self.load_worlds_jp(config["DATA_FILE_WORLD_JP"])
        # 指定されたワールド名がリストに存在しない場合はNoneを返す
        if worldname not in data_file_worlds_jp:
            return None

        # パラメータを指定して検索URLを生成
        params = {"q": query, "worldname": worldname}
        url = "https://jp.finalfantasyxiv.com/lodestone/character/"
        response = requests.get(url, params=params)
        soup = BeautifulSoup(response.text, "html.parser")

        # class="entry" のエントリ要素をすべて探す
        entries = soup.find_all(lambda tag: tag.has_attr("class") and tag["class"] == ["entry"])
        if not entries:
            return None

        # 見つかった各エントリからキャラクター名とIDを抽出
        character_ids = []
        for entry in entries:
            # キャラクター名を保持している要素 (p.entry__name) を取得
            name_el = entry.find("p", class_="entry__name")
            if not name_el:
                # キャラクター名が取得できない場合はNoneを返す
                return None

            # テキストとして取得し、空白を除去
            found_name = name_el.get_text(strip=True)
            # キャラクター名が完全一致するか確認
            if found_name != query:
                # 一致しなければ次のエントリへ
                continue

            # エントリ内のリンクからキャラクターIDを取得
            link = entry.find("a", href=re.compile(r"/lodestone/character/\d+/"))
            if link:
                match = re.search(r"/lodestone/character/(\d+)/", link["href"])
                if match:
                    character_ids.append(match.group(1))
                    # 一件目が見つかった時点でループを抜ける（最初のIDを優先）
                    break

        # キャラクターIDが一つも見つからなければNoneを返す
        if not character_ids:
            return None

        # 最初に見つかったキャラクターIDを返す
        return character_ids[0]
