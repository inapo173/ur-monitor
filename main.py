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
# ★ここには「普通のURL」を入れてください。
# プログラムが自動でデータのあるページ(_room.html)を探しに行きます。
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

# ★★★ テスト用（30万円） ★★★ 通知が来たら 85000 に戻してください
MAX_RENT_LIMIT = 300000

# GitHub Secretsから読み込む
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
HEALTHCHECK_URL = os.environ.get("HEALTHCHECK_URL", "")

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

def get_room_url(url):
    """
    普通のURL(.html)を、データが入っているURL(_room.html)に変換する
    """
    if "_room.html" in url:
        return url
    return url.replace(".html", "_room.html")

def extract_room_details(soup):
    rooms = []
    
    # 【重要】提供されたHTML解析の結果、
    # 部屋リストは必ず <tbody class="rep_room"> の中にあることが判明しました。
    # 逆に、ここ以外にある「円」はただの目安（紹介文）なので無視します。
    
    table_body = soup.find("tbody", class_="rep_room")
    
    if not table_body:
        # _room.htmlを見に行ってもここが空なら、本当に空室がない
        return []

    # 部屋リストの各行（tr）を取得
    rows = table_body.find_all("tr")
    
    for row in rows:
        text = row.get_text()
        clean_text = re.sub(r'\s+', ' ', text).strip()
        
        # 家賃を抽出
        rent_match = re.search(r'([0-9,]+)\s?円', clean_text)
        
        if rent_match:
            # カンマを除去して数値化
            rent_str = rent_match.group(1).replace(",", "")
            try:
                rent = int(rent_str)
            except:
                continue
            
            # 家賃フィルター
            if rent > MAX_RENT_LIMIT:
                continue
            
            # その他の情報を抽出
            # 部屋番号（例：1-35号棟405号室）
            room_num_match = re.search(r'([0-9\-]+号棟[0-9]+号室|[0-9]+号室)', clean_text)
            room_number = room_num_match.group(1) if room_num_match else "部屋番号不明"
            
            # 広さ
            size_match = re.search(r'([0-9]+)\s?(㎡|m2)', clean_text)
            
            # 階数
            floor_match = re.search(r'([0-9]+)\s?階', clean_text)
            
            # タイプ（1LDKなど）
            type_match = re.search(r'[0-9]?[LDKSR]+', clean_text)

            room_info = {
                "number": room_number,
                "rent_fmt": rent_match.group(0),
                "size": size_match.group(0) if size_match else "-",
                "floor": floor_match.group(0) if floor_match else "-",
                "type": type_match.group(0) if type_match else "-"
            }
            rooms.append(room_info)

    return rooms

def check_vacancy(original_url):
    # 【重要】データが入っている "_room.html" に変換してアクセスする
    target_url = get_room_url(original_url)
    
    # ブラウザのふりをする（これがないと _room.html がエラーになることがある）
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    headers = {
        "User-Agent": random.choice(user_agents),
        "Referer": original_url  # 元のページから来たふりをする
    }
    
    try:
        response = requests.get(target_url, headers=headers, timeout=30)
        
        # 文字化け対策
        if response.encoding is None or response.encoding == 'ISO-8859-1':
            response.encoding = response.apparent_encoding

        # 404エラー（ページなし）は、URの場合「部屋がゼロでページが消された」可能性が高い
        if response.status_code == 404:
            print(f"→ 空きなし (ページ消失/404): {target_url}")
            return False
            
        if response.status_code != 200:
            print(f"⚠ アクセスエラー ({response.status_code}): {target_url}")
            return False

        soup = BeautifulSoup(response.content, "html.parser")
        page_text = soup.get_text()

        # 満室・終了の判定
        if "掲載は終了いたしました" in page_text or "お探しのページは見つかりません" in page_text:
            print(f"→ 満室 (掲載終了画面): {target_url}")
            return False

        if "条件に一致する物件はありませんでした" in page_text or "現在、空き室はありません" in page_text:
            print(f"→ 空きなし: {target_url}")
            return False

        # データ抽出
        rooms = extract_room_details(soup)
        
        if not rooms:
            print(f"→ 条件に合う空き部屋なし（または予算オーバー）: {target_url}")
            return False

        # 通知メッセージ作成
        title = soup.find("h1")
        area_name = title.get_text(strip=True) if title else "不明な団地"
        
        msg = f"**【UR空室発見！】**\nTarget: {area_name}\nURL: {target_url}\n\n"
        for i, room in enumerate(rooms):
            if i >= 5:
                msg += "ほか複数件あり...\n"
                break
            msg += f"・{room['number']} | {room['type']} | {room['floor']} | **{room['rent_fmt']}**\n"
        
        send_discord(msg)
        return True

    except Exception as e:
        print(f"例外発生 ({target_url}): {e}")
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
