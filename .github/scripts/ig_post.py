#!/usr/bin/env python3
"""
Instagram 自動投稿 ディスパッチャー
GitHub Actions から呼び出される。環境変数 IG_TOKEN が必要。
投稿日（JST）に基づいて該当するスクリプトの処理を実行する。
"""
import os, sys, json, requests, time, datetime

# ---- 設定 ----
TOKEN = os.environ.get("IG_TOKEN", "IGAAqHMMXPrH1BZAGJwSTYzbTE5TjFFVUE5anJaZA2VjRjFzQmc3OFNVODh2eTQ2WGJuNjJBejktTHNyVzltLVVublNpZAUJjLW53MU1LaVBZAWktuVU9Vc2RMR1dKWUtZAT0FqUkl5cEdtT2xiMUNOTnJxMUttVDRUSFdaZA2xVeVhiSQZDZD")
UID   = "26763073733385637"
BASE  = "https://graph.instagram.com/v21.0"
MEDIA = "https://kotachimaru.github.io"

# ---- 共通 API ヘルパー ----
def api(method, endpoint, **data):
    data["access_token"] = TOKEN
    url = f"{BASE}/{endpoint}"
    r = requests.post(url, data=data) if method == "POST" else requests.get(url, params=data)
    j = r.json()
    if "error" in j:
        print(f"ERROR: {j['error']}")
        sys.exit(1)
    return j

def wait_video(container_id, max_wait=300):
    print("  動画処理中...", end="", flush=True)
    for _ in range(max_wait // 5):
        time.sleep(5)
        res = requests.get(f"{BASE}/{container_id}",
            params={"fields": "status_code", "access_token": TOKEN}).json()
        status = res.get("status_code", "")
        print(f" {status}", end="", flush=True)
        if status == "FINISHED":
            print()
            return True
        if status == "ERROR":
            print(f"\nERROR: {res}")
            return False
    print("\nタイムアウト")
    return False

def post_reel(video_url, caption, label):
    print(f"=== {label} ===")
    res = api("POST", f"{UID}/media",
              media_type="REELS",
              video_url=video_url,
              caption=caption)
    container_id = res["id"]
    print(f"  コンテナID: {container_id}")
    if not wait_video(container_id):
        sys.exit(1)
    res = api("POST", f"{UID}/media_publish", creation_id=container_id)
    print(f"  ✅ 投稿完了！ ID: {res['id']}")

def post_carousel(image_urls, caption, label):
    print(f"=== {label} ===")
    child_ids = []
    for i, url in enumerate(image_urls, 1):
        res = api("POST", f"{UID}/media", image_url=url, is_carousel_item="true")
        child_ids.append(res["id"])
        print(f"  [{i}/{len(image_urls)}] コンテナ作成: {res['id']}")
    res = api("POST", f"{UID}/media",
              media_type="CAROUSEL",
              children=",".join(child_ids),
              caption=caption)
    carousel_id = res["id"]
    print(f"  カルーセルID: {carousel_id}")
    time.sleep(2)
    res = api("POST", f"{UID}/media_publish", creation_id=carousel_id)
    print(f"  ✅ 投稿完了！ ID: {res['id']}")

# ---- 投稿データ（日付 → 投稿内容） ----
SCHEDULE = {
    # 6/2 (火): 心リハ 問題解説リール
    "2026-06-02": lambda: post_reel(
        f"{MEDIA}/reel_quiz.mp4",
        """【心リハ指導士試験】今日の1問⚡️

β遮断薬を投与中の心疾患患者の
運動強度指標として最も適切なのはどれか？

動画で一緒に考えてみてください👆

正解と解説も後半に出てきます✅

同じような問題が本番でも出ます
「なぜそれが正解か」の理由まで理解するのが合格への近道です

問題集（全220問）はプロフのリンクから🔗
まず10問、無料でお試しできます

#心臓リハビリテーション指導士 #心リハ試験対策 #理学療法士""",
        "6/2 火曜投稿: 心リハ 問題解説リール"
    ),

    # 6/3 (水): 心リハ カルーセル 運動強度
    "2026-06-03": lambda: post_carousel(
        [f"{MEDIA}/carousel/int_{i:02d}.jpg" for i in range(1, 7)],
        """【保存推奨🔖】運動強度の決め方 完全まとめ

4つの方法を整理しました💡

①Karvonen法 → 心拍数で管理（最もよく使う）
②Borgスケール → 自覚症状で管理（β遮断薬投与中に必須）
③METs → 代謝当量（日常生活・退院指導に活用）
④AT → 嫌気性代謝閾値（心不全・重症例で重要）

「どれをどんな患者に使うか」まで答えられると
試験で迷いがなくなります✅

問題集（全220問）はプロフのリンクから🔗
まず10問、無料でお試しできます

#心臓リハビリテーション指導士 #心リハ #理学療法士""",
        "6/3 水曜投稿: 心リハ カルーセル 運動強度"
    ),

    # 6/4 (木): 腎リハ アプリ紹介リール
    "2026-06-04": lambda: post_reel(
        f"{MEDIA}/reel_jinriha.mp4",
        """【腎リハ指導士試験】アプリで効率よく対策✅

「全9章・370問」を収録した問題集アプリです📱

✔ インストール不要・登録不要
✔ スマホブラウザで今すぐ使える
✔ 間違えた問題を自動で記録

まず10問、無料でお試しできます🎯

プロフのリンクから👆

#腎臓リハビリテーション指導士 #腎リハ #理学療法士""",
        "6/4 木曜投稿: 腎リハ アプリ紹介リール"
    ),

    # 6/5 (金): 呼吸療法 アプリ紹介リール
    "2026-06-05": lambda: post_reel(
        f"{MEDIA}/reel_kokyuriha.mp4",
        """【呼吸療法認定士試験】アプリで効率よく対策✅

「全8章・310問」を収録した問題集アプリです📱

✔ インストール不要・登録不要
✔ スマホブラウザで今すぐ使える
✔ 間違えた問題を自動で記録

まず10問、無料でお試しできます🎯

プロフのリンクから👆

#3学会合同呼吸療法認定士 #呼吸療法 #理学療法士""",
        "6/5 金曜投稿: 呼吸療法 アプリ紹介リール"
    ),

    # 6/6 (土): 腎リハ 問題解説リール
    "2026-06-06": lambda: post_reel(
        f"{MEDIA}/reel_quiz_jinriha.mp4",
        """【腎リハ指導士試験】今日の1問⚡️

慢性腎臓病（CKD）患者の
運動療法の絶対禁忌はどれか？

動画で一緒に考えてみてください👆

正解と解説も後半に出てきます✅

同じような問題が本番でも出ます
「なぜそれが正解か」の理由まで理解するのが合格への近道です

問題集（全370問）はプロフのリンクから🔗
まず10問、無料でお試しできます

#腎臓リハビリテーション指導士 #腎リハ試験対策 #理学療法士""",
        "6/6 土曜投稿: 腎リハ 問題解説リール"
    ),

    # 6/7 (日): 呼吸療法 問題解説リール
    "2026-06-07": lambda: post_reel(
        f"{MEDIA}/reel_quiz_kokyuriha.mp4",
        """【呼吸療法認定士試験】今日の1問⚡️

COPD患者の呼吸リハビリで
最も推奨される運動強度はどれか？

動画で一緒に考えてみてください👆

正解と解説も後半に出てきます✅

同じような問題が本番でも出ます
「なぜそれが正解か」の理由まで理解するのが合格への近道です

問題集（全310問）はプロフのリンクから🔗
まず10問、無料でお試しできます

#3学会合同呼吸療法認定士 #呼吸療法試験対策 #理学療法士""",
        "6/7 日曜投稿: 呼吸療法 問題解説リール"
    ),

    # 6/8 (月): 腎リハ よく出る数字5選 カルーセル
    "2026-06-08": lambda: post_carousel(
        [f"{MEDIA}/carousel/jinriha_num_{i:02d}.jpg" for i in range(1, 8)],
        """【保存推奨🔖】腎リハ試験で絶対出る数字5選

試験前日に見返したくなるやつをまとめました📊

①eGFR 15未満 → 末期腎不全（G5）の定義
②3ヶ月以上 → CKD診断の持続期間
③3METs → 透析患者の日常生活動作目安
④収縮期血圧180mmHg → 運動療法の絶対禁忌
⑤透析後2時間 → 運動開始を避ける推奨時間

数字はセットで覚えると試験で迷わない💡

問題集（全370問）はプロフのリンクから🔗
まず10問、無料でお試しできます

#腎臓リハビリテーション指導士 #腎リハ #理学療法士""",
        "6/8 月曜投稿: 腎リハ よく出る数字5選 カルーセル"
    ),

    # 6/9 (火): 呼吸療法 よく出る数字5選 カルーセル
    "2026-06-09": lambda: post_carousel(
        [f"{MEDIA}/carousel/kokyuriha_num_{i:02d}.jpg" for i in range(1, 8)],
        """【保存推奨🔖】呼吸療法試験で絶対出る数字5選

試験前日に見返したくなるやつをまとめました📊

①FEV1/FVC 70%未満 → COPD診断の気流閉塞基準
②PaO₂ 60mmHg → 酸素療法開始の目安
③最大負荷の60〜80% → COPD運動強度の推奨値
④GOLD2 → FEV1 50〜80%（中等症）の目安
⑤25〜30m → 6分間歩行のMCID（最小臨床重要差）

数字の「なぜ」と一緒に覚えると記憶が定着する💡

問題集（全310問）はプロフのリンクから🔗
まず10問、無料でお試しできます

#3学会合同呼吸療法認定士 #呼吸療法 #理学療法士""",
        "6/9 火曜投稿: 呼吸療法 よく出る数字5選 カルーセル"
    ),

    # 6/10 (水): 心リハ 試験対策Tips カルーセル
    "2026-06-10": lambda: post_carousel(
        [f"{MEDIA}/carousel/tips_{i:02d}.jpg" for i in range(1, 7)],
        """【保存推奨🔖】心リハ試験 よく間違える5選

似たもの同士が紛らわしい項目をまとめました⚠️

①Karvonen vs Borg → 薬物投与時はBorg（心拍が使えない）
②HFrEF vs HFpEF → LVEF 40%未満がrEF（収縮不全）
③AT vs VO₂max → 心リハではAT基準が安全
④3METs vs 5METs → 3=日常生活、5=就労復帰
⑤CPX vs 負荷心電図 → CPXで運動耐容能を定量評価

「紛らわしい=よく出る」と思って準備を💡

問題集（全220問）はプロフのリンクから🔗
まず10問、無料でお試しできます

#心臓リハビリテーション指導士 #心リハ #理学療法士""",
        "6/10 水曜投稿: 心リハ 試験対策Tips カルーセル"
    ),
}

# ---- schedule.json からの投稿 ----
def post_from_schedule(today_str):
    """schedule.json を読んで本日分を投稿する"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    schedule_path = os.path.join(script_dir, "..", "..", "schedule.json")
    schedule_path = os.path.normpath(schedule_path)

    if not os.path.exists(schedule_path):
        return False

    with open(schedule_path, encoding="utf-8") as f:
        schedule_data = json.load(f)

    if today_str not in schedule_data:
        return False

    entry = schedule_data[today_str]
    label = entry.get("app_label", entry.get("app", ""))
    print(f"=== {today_str} {label} 自動投稿 ===")

    if entry["type"] == "carousel":
        post_carousel(
            entry["slides"],
            entry["caption"],
            f"{today_str} {label}"
        )
    elif entry["type"] == "reel":
        post_reel(
            entry["video_url"],
            entry["caption"],
            f"{today_str} {label}"
        )
    return True

# ---- 二重投稿ガード ----
def already_posted_today(today_str):
    """本日(JST)すでに投稿済みなら True を返す。手動実行と定期実行の二重投稿を防ぐ。"""
    try:
        r = requests.get(f"{BASE}/{UID}/media",
                         params={"fields": "timestamp", "limit": 5, "access_token": TOKEN})
        for m in r.json().get("data", []):
            ts = (m.get("timestamp") or "")[:19]  # 例: 2026-06-08T21:30:03 (UTC)
            if not ts:
                continue
            dt_jst = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(hours=9)
            if dt_jst.strftime("%Y-%m-%d") == today_str:
                return True
    except Exception as e:
        print(f"  投稿済みチェック失敗（続行）: {e}")
    return False


# ---- メイン ----
if __name__ == "__main__":
    # GitHub Actions は UTC で動くので JST (UTC+9) に変換
    now_jst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    today_str = now_jst.strftime("%Y-%m-%d")
    print(f"現在時刻 (JST): {now_jst.strftime('%Y-%m-%d %H:%M')}")
    print(f"投稿日: {today_str}")

    # 二重投稿ガード: 本日すでに投稿済みならスキップ
    if already_posted_today(today_str):
        print(f"本日（{today_str}）は既に投稿済みのためスキップします。")
        sys.exit(0)

    # 1. まず schedule.json（自動生成）を確認
    if post_from_schedule(today_str):
        sys.exit(0)

    # 2. なければ固定スケジュール（現在の週分）を確認
    if today_str in SCHEDULE:
        SCHEDULE[today_str]()
    else:
        print(f"本日（{today_str}）の投稿スケジュールはありません。")
        sys.exit(0)
