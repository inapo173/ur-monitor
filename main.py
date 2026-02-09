import requests
from bs4 import BeautifulSoup
import os
import time
import re
import datetime
import random
import sys

# ==========================================
# 1. ユーザー設定エリア
# ==========================================

# 監視したい物件のURLリスト
# ※ 末尾を "_room.html" に統一済み
TARGET_URLS = [
    # 福住一丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2660_room.html",
    # 木場公園三好住宅
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3450_room.html",
    # 木場公園平野住宅
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3570_room.html",
    # 木場三丁目パークハイツ
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3860_room.html",
    # 大島六丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_1920_room.html",
    # アーバンライフ西新井
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_1210_room.html",
    # 高島平団地
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2250_room.html",
    # 川口芝園団地
    "https://www.ur-net.go.jp/chintai/kanto/saitama/11_1250_room.html",
    # コンフォール和光西大和
    "https://www.ur-net.go.jp/chintai/kanto/saitama/50_4120_room.html",
    # 志村一丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_1190_room.html",
    # 大井六丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_1830_room.html",
    # 南千住七丁目ハイツ
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4290_room.html",
    # 上馬二丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2400_room.html",
    # 小島町二丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2540_room.html",
    # 東四ツ木二丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2640_room.html",
    # 大谷田一丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2810_room.html",
    # 北砂五丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2820_room.html",
    # 北砂七丁目
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2940_room.html",
    # 神田小川町ハイツ
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3820_room.html",
    # 新蓮根
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4760_room.html",
    # アクシス東四ツ木
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_5840_room.html",
    # 葛西クリーンタウン清新プラザ
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3480_room.html"
]

# 家賃の上限設定 (8万5000円)
MAX_RENT_LIMIT = 85000 

# GitHub Secretsから読み込む
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
HEALTHCHECK_URL = os.environ.get("HEALTHCHECK_URL", "")

# ==========================================
# 2. システム関数群
# ==========================================

def send_discord(message):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        if len(message) > 1900:
            message = message[:1900] + "\n... (省略されました)"
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
        print(">> Discord通知送信完了")
    except Exception as e:
        print(f"送信エラー: {e}")

def extract_room_details(soup):
    rooms = []
    rows = soup.find_all("tr")
    
    for row in rows:
        text = row.get_text()
        text = re.sub(r'\s+', ' ', text).strip()
        
        rent_match = re.search(r'([0-9,]+)円', text)
        size_match = re.search(r'([0-9]+)㎡|([0-9]+)m2', text)
        floor_match = re.search(r'([0-9]+)階', text)
        type_match = re.search(r'[1-4][LDKS]+', text)

        if rent_match:
            rent_str = rent_match.group(1).replace(",", "")
            rent = int(rent_str)
            
            if rent > MAX_RENT_LIMIT:
                continue
                
            room_info = {
                "rent_fmt": rent_match.group(0),
                "size": size_match.group(0) if size_match else "不明",
                "floor": floor_match.group(0) if floor_match else "不明",
                "type": type_match.group(0) if type_match else "-"
            }
            rooms.append(room_info)
    return rooms

def check_vacancy(url):
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ]
    headers = {"User-Agent": random.choice(user_agents)}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = response.apparent_encoding
        
        # === 修正ポイント: 掲載終了画面（満室）を検知 ===
        if "掲載は終了いたしました" in response.text or "お探しのページは見つかりません" in response.text:
            print(f"→ 満室 (掲載終了画面): {url}")
            return False
        # ===============================================

        if response.status_code != 200:
            error_msg = f"⚠ **アクセス・エラー発生**\nCode: {response.status_code}\nURL: {url}"
            print(error_msg)
            if response.status_code in [403, 500, 502, 503]:
                send_discord(error_msg)
            return False

        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text()
        
        if "条件に一致する物件はありませんでした" in page_text or "現在、空き室はありません" in page_text:
            print(f"→ 空きなし: {url}")
            return False

        rooms = extract_room_details(soup)
        if not rooms:
            print(f"→ 空きはあるが条件不一致: {url}")
            return False

        title = soup.find("h1")
        area_name = title.get_text(strip=True) if title else "不明な団地"
        
        msg = f"**【UR空室発見！】**\nTarget: {area_name}\nURL: {url}\n\n"
        for i, room in enumerate(rooms):
            if i >= 5:
                msg += "ほか複数件あり...\n"
                break
            msg += f"・{room['type']} | {room['floor']} | {room['size']} | **{room['rent_fmt']}**\n"
        
        send_discord(msg)
        return True

    except Exception as e:
        print(f"例外発生 ({url}): {e}")
        send_discord(f"⚠ **スクリプト・エラー**\n{e}\nURL: {url}")
        return False

# ==========================================
# 3. メイン実行ブロック
# ==========================================
if __name__ == "__main__":
    print("--- 監視ジョブ開始 ---")
    
    wait_time = random.randint(5, 30)
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
