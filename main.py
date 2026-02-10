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
        if len(message) > 1900:
            message = message[:1900] + "\n... (省略されました)"
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
        print(">> Discord通知送信完了")
    except Exception as e:
        print(f"送信エラー: {e}")

def extract_room_details_hybrid(soup):
    """
    【最終版】HTMLの構造（tableかdivか）に関わらず、
    「号室」と「家賃」がセットで含まれる行を探し出す強力なロジック
    """
    rooms = []
    
    # ページ内の「行」になりそうな要素をすべて取得（trもdivもliも）
    # これでテーブルレイアウトでもスマホ用レイアウトでも対応可能
    candidates = soup.find_all(['tr', 'div', 'li', 'dd'])
    
    # 重複除外用セット
    seen_identifiers = set()

    for element in candidates:
        text = element.get_text()
        # 全角スペースや改行を半角スペース1つに統一
        clean_text = re.sub(r'\s+', ' ', text).strip()
        
        # --- フィルタリング（ここが最重要） ---

        # 1. 「号室」という文字がないブロックは、部屋リストではないので無視！
        # これにより、ページ上部の「目安家賃（〜）」を確実に除外できます
        if "号室" not in clean_text:
            continue

        # 2. 家賃（円）が含まれていないブロックも無視
        if "円" not in clean_text:
            continue
            
        # 3. 家賃の「幅（〜）」がある行は、万が一「号室」という文字が紛れていても無視
        if "〜" in clean_text or "～" in clean_text or "range" in clean_text:
            continue

        # --- データ抽出 ---
        
        # 家賃抽出（カンマ区切り対応）
        rent_match = re.search(r'([0-9,]+)\s?円', clean_text)
        
        # 部屋番号抽出（例：505号室）
        room_num_match = re.search(r'([0-9\-]+号棟[0-9]+号室|[0-9]+号室)', clean_text)
        
        # 両方見つかった場合のみ「部屋」と認定
        if rent_match and room_num_match:
            room_number = room_num_match.group(1)
            
            # 親要素もdiv、子要素もdivの場合、同じ部屋を何度も拾う可能性があるので重複チェック
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
            
            # その他の情報（広さ・階数・間取り）
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

def check_vacancy(url):
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ]
    headers = {
        "User-Agent": random.choice(user_agents),
        "Referer": "https://www.ur-net.go.jp/"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        
        # 文字コード自動調整（URはたまに古いShift_JISなどが混ざるため）
        if response.encoding is None or response.encoding == 'ISO-8859-1':
            response.encoding = response.apparent_encoding

        # 1. ページ自体の消失チェック
        if "掲載は終了いたしました" in response.text or "お探しのページは見つかりません" in response.text:
            print(f"→ 満室 (掲載終了画面): {url}")
            return False

        if response.status_code != 200:
            error_msg = f"⚠ **アクセス・エラー発生**\nCode: {response.status_code}\nURL: {url}"
            print(error_msg)
            if response.status_code in [403, 404, 500, 502, 503]:
                send_discord(error_msg)
            return False

        # BeautifulSoupオブジェクト作成
        soup = BeautifulSoup(response.content, "html.parser")
        page_text = soup.get_text()

        # 2. 空きなしキーワードチェック
        no_vacancy_keywords = [
            "条件に一致する物件はありませんでした",
            "現在、空き室はありません",
            "ご希望の物件はありませんでした"
        ]
        
        for keyword in no_vacancy_keywords:
            if keyword in page_text:
                print(f"→ 空きなし（{keyword}）: {url}")
                return False

        # 3. ハイブリッド抽出実行
        rooms = extract_room_details_hybrid(soup)
        
        if not rooms:
            print(f"→ データ抽出なし（予算オーバーまたは解析不可）: {url}")
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
        send_discord(f"⚠ **スクリプト・エラー**\n{e}\nURL: {url}")
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
