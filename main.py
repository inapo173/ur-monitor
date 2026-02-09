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
TARGET_URLS = [
    # リバーシティ21
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/23ku/detail/id1_1970.html",
    # 本郷真砂アーバンハイツ
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/23ku/detail/id1_1049.html",
    # コンフォール清澄白河
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/23ku/detail/id1_2991.html",
    # 南砂住宅
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/23ku/detail/id1_1330.html",
    # シティコート大島
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/23ku/detail/id1_3660.html",
    # ハートアイランド新田
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/23ku/detail/id1_4090.html",
    # 葛西クリーンタウン
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/23ku/detail/id1_1670.html",
    # パークタウン足立保木間
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/23ku/detail/id1_1660.html",
    # 高島平団地
    "https://www.ur-net.go.jp/chintai/kanto/tokyo/23ku/detail/id1_0680.html",
    # 浦安マリナイースト21
    "https://www.ur-net.go.jp/chintai/kanto/chiba/detail/id1_4870.html",
    # 見明川団地
    "https://www.ur-net.go.jp/chintai/kanto/chiba/detail/id1_1890.html",
    # 行徳・妙典エリア（駅検索結果）
    "https://www.ur-net.go.jp/chintai/kanto/chiba/list/?td=&p=&w=&st=1228020,1228030,1228040&t=1&t=2&t=3&t=4&r=20",
    # 川口芝園団地
    "https://www.ur-net.go.jp/chintai/kanto/saitama/detail/id1_1250.html",
    # コンフォール和光西大和
    "https://www.ur-net.go.jp/chintai/kanto/saitama/detail/id1_3080.html",
    # かなーちえ（川崎駅周辺検索結果）
    "https://www.ur-net.go.jp/chintai/kanto/kanagawa/list/?td=&p=&w=&st=1401140&t=1&t=2&t=3&t=4&r=20",
    # 横浜ポートサイド
    "https://www.ur-net.go.jp/chintai/kanto/kanagawa/detail/id1_3090.html",
]

# 家賃の上限設定
MAX_RENT_LIMIT = 130000 

# GitHub Secretsから読み込む
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
HEALTHCHECK_URL = os.environ.get("HEALTHCHECK_URL", "")

# ==========================================
# 2. システム関数群
# ==========================================

def send_discord(message):
    if not DISCORD_WEBHOOK_URL:
        print("⚠ Discord URLが設定されていません")
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
        
        if response.status_code != 200:
            print(f"アクセス失敗 ({response.status_code}): {url}")
            return False

        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text()
        if "条件に一致する物件はありませんでした" in page_text or "現在、空き室はありません" in page_text:
            print("→ 空きなし")
            return False

        rooms = extract_room_details(soup)
        if not rooms:
            print("→ 空きはあるが条件不一致")
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
        print(f"エラー発生 ({url}): {e}")
        return False

# ==========================================
# 3. メイン実行ブロック
# ==========================================
if __name__ == "__main__":
    print("--- 監視ジョブ開始 ---")
    
    # 待機時間を少し短縮（最大60秒）
    wait_time = random.randint(5, 60)
    print(f"人間らしさを出すため {wait_time}秒 待機します...")
    time.sleep(wait_time)
    
    found_any_in_this_run = False
    
    for url in TARGET_URLS:
        is_found = check_vacancy(url)
        if is_found:
            found_any_in_this_run = True
        time.sleep(2)

    # ----------------------------------------------------
    # 【定時連絡判定】日本時間 23:30 (UTC 14:30) の回に対応
    # ----------------------------------------------------
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    
    # UTC 14時台 (JST 23時台) かつ 25分以降なら「定時連絡」とみなす
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
