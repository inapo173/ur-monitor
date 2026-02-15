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

# 監視したい物件のURLリスト
# 普通のURL(.html)を入れておけば、自動でIDを解析して裏APIを見に行きます
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
    
    # === テスト用（西上尾第二） ===
    "https://www.ur-net.go.jp/chintai/kanto/saitama/50_1270.html"
]

# ★★★ テスト用：30万円（成功したら85000に戻してください） ★★★
MAX_RENT_LIMIT = 300000

# GitHub Secretsから読み込む
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
HEALTHCHECK_URL = os.environ.get("HEALTHCHECK_URL", "")

# ★★★ 【重要】解析で判明した正しいAPI住所 ★★★
API_ENDPOINT = "https://chintai.r6.ur-net.go.jp/chintai/api/bukken/detail/detail_bukken_room/"

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
    HTMLの中からinitSearch('50', '127', '0')のようなIDを探し出す
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
    解析された正しい住所と合言葉でAPIを叩く
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": original_url,
        "Origin": "https://www.ur-net.go.jp", # ここ重要
        "X-Requested-With": "XMLHttpRequest"   # これがないと無視されることがある
    }
    
    # ★★★ 解析画像に基づいた正しいPayload ★★★
    payload = {
        "rent_low": "",
        "rent_high": "",
        "floorspace_low": "",
        "floorspace_high": "",
        "shisya": identifiers["shisya"],
        "danchi": identifiers["danchi"],
        "shikibetu": identifiers["shikibetu"],
        "newBukkenRoom": "",
        "orderByField": "0",
        "orderBySort": "0",
        "pageIndex": "0",
        "sp": "" # スマホフラグ（PCのふりをするので空でOK）
    }
    
    try:
        # requests.postでdataに辞書を渡すと、自動的に
        # Content-Type: application/x-www-form-urlencoded になります（これが正解）
        response = requests.post(API_ENDPOINT, data=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            try:
                return response.json()
            except json.JSONDecodeError:
                print(f"⚠ API応答がJSONではありません: {original_url}")
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
            print(f"→ ID抽出失敗（initSearchが見つかりません）: {url}")
            return False
            
        # 2. 抽出したIDを使って正しいAPIを叩く
        print(f"   (API問い合わせ: {identifiers['shisya']}-{identifiers['danchi']}-{identifiers['shikibetu']})")
        json_data = fetch_room_data_via_api(identifiers, url)
        
        if not json_data:
            print(f"→ データ取得失敗（APIエラーまたは空）: {url}")
            return False
            
        # 3. JSONデータを解析して部屋を探す
        valid_rooms = []
        
        # 提供いただいたJSON構造に合わせて解析
        for room in json_data:
            # 家賃（"46,800円" -> 46800）
            rent_str = room.get("rent", "0").replace("円", "").replace(",", "")
            room_name = room.get("name", "不明")
            room_type = room.get("type", "-")
            # 床面積の特殊文字 &#13217; (㎡) を変換
            floor_space = room.get("floorspace", "-").replace("&#13217;", "㎡")
            floor_num = room.get("floor", "-")
            
            try:
                rent = int(rent_str)
            except:
                continue
                
            # 家賃フィルター
            if rent > MAX_RENT_LIMIT:
                continue
                
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

    # テスト時は待ち時間を短く
    wait_time = random.randint(2, 5)
    print(f"Wait for {wait_time} sec...")
    time.sleep(wait_time)
    
    found_any_in_this_run = False
    
    for url in TARGET_URLS:
        if not url: continue
        is_found = check_vacancy(url)
        if is_found:
            found_any_in_this_run = True
        time.sleep(2) # 連続アクセスしすぎないよう待機

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
