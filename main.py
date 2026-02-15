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
    
]

# ★★★ テスト用：30万円（運用開始時は85000に戻してください） ★★★
MAX_RENT_LIMIT = 85000

# 設定
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
HEALTHCHECK_URL = os.environ.get("HEALTHCHECK_URL", "")
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
    """HTMLからID(shisya, danchi, shikibetu)を探す（正規表現強化版）"""
    # シングルクォート、ダブルクォート、スペースの揺れに対応
    match = re.search(r"initSearch\s*\(\s*['\"](\d+)['\"]\s*,\s*['\"](\d+)['\"]\s*,\s*['\"](\d+)['\"]\s*\)", html_text)
    if match:
        return {
            "shisya": match.group(1),
            "danchi": match.group(2),
            "shikibetu": match.group(3)
        }
    return None

def fetch_room_data_via_api(identifiers, original_url):
    """APIからJSONデータを取得する"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": original_url,
        "Origin": "https://www.ur-net.go.jp",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    # ★提供された画像に基づきPayloadを修正（siteId削除など）★
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
        "sp": ""
    }
    
    try:
        response = requests.post(API_ENDPOINT, data=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            return None # エラーハンドリングは呼び出し元で行う
    except:
        return None

def check_vacancy(url):
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    headers = {
        "User-Agent": random.choice(user_agents),
        "Referer": "https://www.ur-net.go.jp/"
    }
    
    # ログ用の団地名初期値
    area_name = "団地名取得中..."

    try:
        # 1. HTML取得
        response = requests.get(url, headers=headers, timeout=30)
        
        # 団地名を先に取得（ログ出力用）
        soup = BeautifulSoup(response.content, "html.parser")
        title_tag = soup.find("h1")
        if title_tag:
            area_name = title_tag.get_text(strip=True)
        
        # ステータスコードチェック
        if response.status_code == 404:
            print(f"☁️ 空き室なし (ページ削除): {area_name}")
            return False
        
        # 2. ID抽出
        identifiers = get_identifiers(response.text)
        if not identifiers:
            print(f"☁️ 空き室なし (ID判定不可): {area_name}")
            return False
            
        # 3. API実行
        json_data = fetch_room_data_via_api(identifiers, url)
        
        if json_data is None:
            # APIエラーの場合も、現状は「空きなし（取得失敗）」としてログに出す
            print(f"☁️ 空き室なし (APIエラー): {area_name}")
            return False
            
        # 4. JSON解析
        valid_rooms = []
        skipped_count = 0
        total_rooms = len(json_data)
        
        for room in json_data:
            # データ整形
            rent_str = str(room.get("rent", "0")).replace("円", "").replace(",", "")
            room_name = room.get("name", "不明")
            room_type = room.get("type", "-")
            floor_space = str(room.get("floorspace", "-")).replace("&#13217;", "㎡")
            floor_num = room.get("floor", "-")
            
            try:
                rent = int(rent_str)
            except:
                continue
                
            # 家賃フィルター
            if rent > MAX_RENT_LIMIT:
                skipped_count += 1
                continue
                
            valid_rooms.append({
                "name": room_name,
                "rent_fmt": room.get("rent", ""),
                "type": room_type,
                "size": floor_space,
                "floor": floor_num
            })

        # --- 結果判定とログ出力 ---
        
        if len(valid_rooms) > 0:
            # 【発見】通知対象あり
            print(f"🎉 空室発見！ ({len(valid_rooms)}件): {area_name}")
            
            msg = f"**【UR空室発見！】**\nTarget: {area_name}\nURL: {url}\n\n"
            for i, r in enumerate(valid_rooms):
                if i >= 5:
                    msg += "ほか複数件あり...\n"
                    break
                msg += f"・{r['name']} | {r['type']} | {r['floor']} | **{r['rent_fmt']}**\n"
            
            send_discord(msg)
            return True

        elif total_rooms > 0:
            # 【惜しい】部屋はあるが条件不一致
            print(f"👀 空き室はあるが、条件不一致 (家賃オーバー {skipped_count}件): {area_name}")
            return False
            
        else:
            # 【空きなし】APIのリストが0件
            print(f"☁️ 空き室なし: {area_name}")
            return False

    except Exception as e:
        print(f"☁️ 空き室なし (エラー発生: {e}): {area_name}")
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
    
    # 少し待機
    wait_time = random.randint(2, 5)
    print(f"Wait for {wait_time} sec...")
    time.sleep(wait_time)
    
    found_any_in_this_run = False
    
    for url in TARGET_URLS:
        if not url: continue
        is_found = check_vacancy(url)
        if is_found:
            found_any_in_this_run = True
        time.sleep(2) # サーバー負荷軽減

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
