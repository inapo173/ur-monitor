import requests
from bs4 import BeautifulSoup
import os
import time
import re
import datetime
import random
import sys
import json

# ==========================================
# 1. ユーザー設定エリア
# ==========================================

# 監視したい物件のURLリスト（普通の.htmlのURLでOK）
TARGET_URLS = [
    # 福住一丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2660.html",
    # 木場公園三好住宅
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3450.html",
    # 木場公園平野住宅
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3570.html",
    # 木場三丁目パークハイツ
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3860.html",
    # 大島六丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_1920.html",
    # 高島平団地
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2250.html",
    # コンフォール和光西大和
    "https://www.ur-net.go.jp/chintai/kanto/saitama/50_4120.html",
    # 志村一丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_1190.html",
    # 大井六丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_1830.html",
    # 南千住七丁目ハイツ
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4290.html",
    # 上馬二丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2400.html",
    # 小島町二丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2540.html",
    # 東四ツ木二丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2640.html",
    # 大谷田一丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2810.html",
    # 北砂五丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2820.html",
    # 北砂七丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2940.html",
    # 神田小川町ハイツ
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3820.html",
    # 新蓮根
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4760.html",
    # アクシス東四ツ木
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_5840.html",
    # 葛西クリーンタウン清新プラザ
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3480.html",
    # 川口芝園団地
    "https://www.ur-net.go.jp/chintai/kanto/saitama/50_1820.html",
    # アーバンライフ西新井
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_5320.html",
    
    # === テスト用物件 ===
    "https://www.ur-net.go.jp/chintai/kanto/saitama/50_1270.html"
]

# ★★★ テスト用：30万円（成功したら85000に戻してください） ★★★
MAX_RENT_LIMIT = 300000

# GitHub Secretsから読み込む
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
HEALTHCHECK_URL = os.environ.get("HEALTHCHECK_URL", "")

# APIのエンドポイント（ここが情報の宝庫）
API_ENDPOINT = "https://www.ur-net.go.jp/chintai/api/bukken/detail/detail_bukken_room/"

# ==========================================
# 2. システム関数群
# ==========================================

def send_discord(message):
    if not DISCORD_WEBHOOK_URL:
        print("⚠ 【重要】Discord URLが設定されていません。")
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
        print(">> Discord通知送信完了")
    except Exception as e:
        print(f"送信エラー: {e}")

def get_identifiers(html_text):
    """
    HTMLの中から、APIを叩くために必要な「3つのID」を探し出す
    initSearch('50', '127', '0') のような記述を探す
    """
    match = re.search(r"initSearch\('(\d+)',\s*'(\d+)',\s*'(\d+)'\)", html_text)
    if match:
        return {
            "shisya": match.group(1),
            "danchi": match.group(2),
            "shikibetu": match.group(3)
        }
    return None

def fetch_room_data_via_api(identifiers, original_url):
    """
    IDを使って裏APIからJSONデータを取得する
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": original_url,
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.ur-net.go.jp"
    }
    
    # APIに送るデータ（これが「鍵」です）
    payload = {
        "shisya": identifiers["shisya"],
        "danchi": identifiers["danchi"],
        "shikibetu": identifiers["shikibetu"],
        "siteId": "chintai" # おそらく固定
    }
    
    try:
        response = requests.post(API_ENDPOINT, data=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            try:
                return response.json() # JSONとして読み込む
            except json.JSONDecodeError:
                print(f"⚠ API応答がJSONではありませんでした: {original_url}")
                return None
        else:
            print(f"⚠ APIアクセスエラー ({response.status_code}): {original_url}")
            return None
            
    except Exception as e:
        print(f"⚠ API通信例外: {e}")
        return None

def check_vacancy(url):
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    headers = {
        "User-Agent": random.choice(user_agents),
        "Referer": "https://www.ur-net.go.jp/"
    }
    
    try:
        # 1. まずHTMLページにアクセスしてIDを取得する
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 404:
            print(f"→ ページなし (404): {url}")
            return False
        
        # ID抽出
        identifiers = get_identifiers(response.text)
        if not identifiers:
            # IDが見つからない＝部屋データを持つページではない（または構造が変わった）
            print(f"→ ID抽出失敗（initSearchが見つかりません）: {url}")
            return False
            
        # 2. 抽出したIDを使ってAPIを叩く
        print(f"   (API問い合わせ中... {identifiers['shisya']}-{identifiers['danchi']}-{identifiers['shikibetu']})")
        json_data = fetch_room_data_via_api(identifiers, url)
        
        if not json_data:
            print(f"→ データ取得失敗（APIエラーまたは空）: {url}")
            return False
            
        # 3. JSONデータを解析して部屋を探す
        valid_rooms = []
        
        # JSONはリスト形式で返ってくる [ {room1}, {room2}... ]
        for room in json_data:
            # 必要な情報を辞書から取り出す
            rent_str = room.get("rent", "0").replace("円", "").replace(",", "")
            room_name = room.get("name", "不明")
            room_type = room.get("type", "-")
            floor_space = room.get("floorspace", "-") # &#13217;などが含まれるかも
            floor_num = room.get("floor", "-")
            
            try:
                rent = int(rent_str)
            except:
                continue # 家賃が数値にできないデータは無視
                
            # 家賃フィルター
            if rent > MAX_RENT_LIMIT:
                continue
                
            # HTML特殊文字のクリーニング
            floor_space = floor_space.replace("&#13217;", "㎡")
            
            valid_rooms.append({
                "name": room_name,
                "rent_fmt": room.get("rent", ""),
                "type": room_type,
                "size": floor_space,
                "floor": floor_num
            })

        if not valid_rooms:
            print(f"→ 条件に合う空き部屋なし（API応答あり・予算オーバーなど）: {url}")
            return False

        # 4. 通知送信
        soup = BeautifulSoup(response.content, "html.parser")
        title = soup.find("h1")
        area_name = title.get_text(strip=True) if title else "不明な団地"
        
        msg = f"**【UR空室発見！】**\nTarget: {area_name}\nURL: {url}\n\n"
        for i, r in enumerate(valid_rooms):
            if i >= 5:
                msg += "ほか複数件あり...\n"
                break
            msg += f"・{r['name']} | {r['type']} | {r['floor']} | **{r['rent_fmt']}**\n"
        
        send_discord(msg)
        return True

    except Exception as e:
        print(f"例外発生 ({url}): {e}")
        return False

# ==========================================
# 3. メイン実行ブロック
# ==========================================
if __name__ == "__main__":
    print("--- 監視ジョブ開始 ---")
    
    if DISCORD_WEBHOOK_URL:
        print("✅ Discord設定: OK")
    else:
        print("❌ Discord設定: 未設定")

    wait_time = random.randint(5, 15)
    print(f"Wait for {wait_time} sec...")
    time.sleep(wait_time)
    
    found_any_in_this_run = False
    
    for url in TARGET_URLS:
        if not url: continue
        is_found = check_vacancy(url)
        if is_found:
            found_any_in_this_run = True
        time.sleep(2)

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if now_utc.hour == 14 and now_utc.minute >= 25:
        if not found_any_in_this_run:
            summary_msg = "🏁 **【本日の監視終了】**\n23:30の定時連絡です。\n本日は条件に合う空き物件はありませんでした。\nまた明日8:00から監視を再開します。"
            send_discord(summary_msg)

    if HEALTHCHECK_URL:
        try:
            requests.get(HEALTHCHECK_URL, timeout=10)
            print("Healthchecks Ping送信完了")
        except:
            pass
            
    print("--- 監視ジョブ終了 ---")
