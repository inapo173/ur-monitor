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
# ★普通のURL(.html)を入れておけば、自動で裏ルートを探しに行きます
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

# ★★★ テスト中（30万） ★★★ 通知が来たら 85000 に戻してください
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

def extract_room_details(soup):
    """
    HTMLの中から部屋情報を探し出す関数
    """
    rooms = []
    candidates = soup.find_all(['tr', 'div', 'li', 'dd'])
    seen_identifiers = set()

    for element in candidates:
        text = element.get_text()
        clean_text = re.sub(r'\s+', ' ', text).strip()
        
        # 1. 家賃の「幅（～）」がある行は無視（目安家賃を除外）
        if "〜" in clean_text or "～" in clean_text or "range" in clean_text:
            continue

        # 2. 「号室」がない行は無視
        if "号室" not in clean_text:
            continue

        # 3. 「円」がない行は無視
        if "円" not in clean_text:
            continue

        # データ抽出
        rent_match = re.search(r'([0-9,]+)\s?円', clean_text)
        room_num_match = re.search(r'([0-9\-]+号棟[0-9]+号室|[0-9]+号室)', clean_text)
        
        if rent_match and room_num_match:
            room_number = room_num_match.group(1)
            
            if room_number in seen_identifiers:
                continue
            
            rent_str = rent_match.group(1).replace(",", "")
            try:
                rent = int(rent_str)
            except:
                continue
            
            # 家賃フィルター
            if rent > MAX_RENT_LIMIT:
                continue
            
            size_match = re.search(r'([0-9]+)\s?(㎡|m2)', clean_text)
            floor_match = re.search(r'([0-9]+)\s?階', clean_text)
            type_match = re.search(r'[0-9]?[LDKSR]+', clean_text)

            room_info = {
                "number": room_number,
                "rent_fmt": rent_match.group(0),
                "size": size_match.group(0) if size_match else "不明",
                "floor": floor_match.group(0) if floor_match else "不明",
                "type": type_match.group(0) if type_match else "-"
            }
            rooms.append(room_info)
            seen_identifiers.add(room_number)

    return rooms

def get_ajax_url(soup, original_url):
    """
    HTML内の秘密の暗号（initSearch）を見つけて、裏APIのURLを作る
    """
    scripts = soup.find_all("script")
    for script in scripts:
        if script.string and "initSearch" in script.string:
            # initSearch('50', '127', '0') のような数字を探す
            match = re.search(r"initSearch\('(\d+)',\s*'(\d+)',\s*'(\d+)'\)", script.string)
            if match:
                shisya = match.group(1) # 例: 50
                danchi = match.group(2) # 例: 127
                shubetsu = match.group(3) # 例: 0
                
                # URの裏API（データのありか）のURLを作成
                # パターン: /chintai/api/bukken/detail/dtl_50_127_0.html
                api_url = f"https://www.ur-net.go.jp/chintai/api/bukken/detail/dtl_{shisya}_{danchi}_{shubetsu}.html"
                print(f"   (裏APIを発見: {api_url})")
                return api_url
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
        # 1. まず普通のURLにアクセス
        response = requests.get(url, headers=headers, timeout=30)
        if response.encoding is None or response.encoding == 'ISO-8859-1':
            response.encoding = response.apparent_encoding

        if response.status_code != 200:
            print(f"⚠ アクセス失敗 ({response.status_code}): {url}")
            return False

        soup = BeautifulSoup(response.content, "html.parser")
        page_text = soup.get_text()

        # 2. 満室チェック（お辞儀画面）
        if "掲載は終了いたしました" in page_text or "お探しのページは見つかりません" in page_text:
            print(f"→ 満室 (掲載終了画面): {url}")
            return False

        # 3. まずはこのページから部屋を探す
        rooms = extract_room_details(soup)
        
        # 4. もし部屋が見つからなければ、裏API（隠しページ）を探しに行く
        if not rooms:
            # "initSearch" という暗号を探して、裏URLを作る
            api_url = get_ajax_url(soup, url)
            
            if api_url:
                # 裏APIにアクセス
                try:
                    time.sleep(1) # 優しくアクセス
                    api_response = requests.get(api_url, headers=headers, timeout=30)
                    api_response.encoding = 'utf-8' # APIはだいたいUTF-8
                    
                    if api_response.status_code == 200:
                        api_soup = BeautifulSoup(api_response.content, "html.parser")
                        # 裏ページからもう一度部屋を探す
                        rooms = extract_room_details(api_soup)
                except Exception as e:
                    print(f"   (裏APIアクセスエラー: {e})")

        # 5. 結果判定
        if not rooms:
            print(f"→ 条件に合う空き部屋なし（または予算オーバー）: {url}")
            return False

        title = soup.find("h1")
        area_name = title.get_text(strip=True) if title else "不明な団地"
        
        msg = f"**【UR空室発見！】**\nTarget: {area_name}\nURL: {url}\n\n"
        for i, room in enumerate(rooms):
            if i >= 5:
                msg += "ほか複数件あり...\n"
                break
            msg += f"・{room['number']} | {room['type']} | {room['floor']} | **{room['rent_fmt']}**\n"
        
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
