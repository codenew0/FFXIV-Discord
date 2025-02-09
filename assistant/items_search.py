import requests
from bs4 import BeautifulSoup
import json
import re
import os
import concurrent.futures
import threading

BASE_URL = "https://universalis.app"
JSON_FILE = "item_multi_result.json"
lock = threading.Lock()  # JSONファイル更新用のロック


def get_item_links():
    """
    https://universalis.app/items にアクセスし、
    liタグ内のaタグのhref属性が "/market/[item_n]" 形式の場合、
    item_n をキー、リンク（BASE_URL + href）を値として辞書に格納する
    """
    url = BASE_URL + "/items"
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    links = {}
    for li in soup.find_all("li"):
        a_tag = li.find("a", href=True)
        if a_tag:
            href = a_tag['href']
            match = re.match(r"^/market/(.+)$", href)
            if match:
                item_n = match.group(1)
                full_link = BASE_URL + href
                links[item_n] = full_link
    return links


def extract_title(text):
    """
    タイトル文字列から " - Universalis" の前の部分を抽出する
    """
    return text.split(" - Universalis")[0].strip()


def get_item_en(url):
    """
    通常のリクエストでページを取得し、titleタグから item_en を抽出する
    """
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    title_tag = soup.find("title")
    if title_tag:
        return extract_title(title_tag.text)
    return ""


def get_item_jp(url):
    """
    セッションを作成し、指定のCookieを設定してページを取得し、
    titleタグから item_jp を抽出する
    """
    session = requests.Session()
    session.cookies.set('mogboard_language', 'ja')
    session.cookies.set('mogboard_last_selected_server', 'Japan')
    response = session.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    title_tag = soup.find("title")
    if title_tag:
        return extract_title(title_tag.text)
    return ""


def load_existing_results():
    """
    JSONファイルが存在する場合、既存のデータを読み込む。
    存在しなければ空の辞書を返す。
    """
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_results(result):
    """
    現在の結果を JSON ファイルに保存する（ロック付き）
    """
    with lock:
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)


def process_item(item_n, url, result):
    """
    1つのアイテムに対する処理：英語・日本語のタイトル取得後、結果に追加し、即座にファイルへ保存
    """
    try:
        item_en = get_item_en(url)
        item_jp = get_item_jp(url)
        with lock:
            result[item_n] = {
                "link": url,
                "item_en": item_en,
                "item_jp": item_jp
            }
            # 1アイテムごとに JSON ファイルを更新
            with open(JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
        print(f"Processed {item_n}: link='{url}', en='{item_en}', jp='{item_jp}'")
    except Exception as e:
        print(f"Error processing {item_n}: {e}")


def main():
    # 既存の結果を読み込む
    result = load_existing_results()

    # 各アイテムのリンクを取得
    item_links = get_item_links()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for item_n, url in item_links.items():
            # 既に処理済みのアイテムはスキップ
            if item_n in result:
                print(f"{item_n} は既に存在するためスキップします。")
                continue
            futures.append(executor.submit(process_item, item_n, url, result))

        # すべてのタスクの完了を待つ
        concurrent.futures.wait(futures)

    # 全ての処理が完了後、結果を item_n のキー順にソートして再保存する
    sorted_result = dict(sorted(result.items(), key=lambda x: int(x[0])))
    save_results(sorted_result)
    print("全てのアイテムの処理が完了しました。JSONファイルを item_n の順に並べ替えました。")


if __name__ == "__main__":
    main()
