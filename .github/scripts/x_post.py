#!/usr/bin/env python3
"""
X（旧Twitter）自動投稿スクリプト
GitHub Actions から毎日 21:00 JST に実行される。
アプリの初期画面をPlaywrightでスクリーンショットしてXに投稿する。
"""
import os, sys, json, requests, datetime
from requests_oauthlib import OAuth1
from playwright.sync_api import sync_playwright

# ---- 認証 ----
auth = OAuth1(
    os.environ["X_CONSUMER_KEY"],
    os.environ["X_CONSUMER_SECRET"],
    os.environ["X_ACCESS_TOKEN"],
    os.environ["X_ACCESS_TOKEN_SECRET"],
)

# ---- API エンドポイント ----
UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"
TWEET_URL  = "https://api.twitter.com/2/tweets"

# ---- アプリ初期画面 URL ----
APP_URLS = {
    "shinriha":  "https://kotachimaru.github.io/shinriha/",
    "jinriha":   "https://kotachimaru.github.io/jinriha/",
    "kokyuriha": "https://kotachimaru.github.io/kokyuriha/",
    "shinfuzen": "https://kotachimaru.github.io/shinfuzen/",
}

# ---- 固定スケジュール（ig_post.py の SCHEDULE に対応）----
SCHEDULE = {
    "2026-06-02": {"app": "shinriha", "caption": """【心リハ指導士試験】今日の1問⚡️

β遮断薬を投与中の心疾患患者の
運動強度指標として最も適切なのはどれか？

動画で一緒に考えてみてください👆

正解と解説も後半に出てきます✅

同じような問題が本番でも出ます
「なぜそれが正解か」の理由まで理解するのが合格への近道です

問題集（全220問）はプロフのリンクから🔗
まず10問、無料でお試しできます

#心臓リハビリテーション指導士 #心リハ試験対策 #理学療法士"""},

    "2026-06-03": {"app": "shinriha", "caption": """【保存推奨🔖】運動強度の決め方 完全まとめ

4つの方法を整理しました💡

①Karvonen法 → 心拍数で管理（最もよく使う）
②Borgスケール → 自覚症状で管理（β遮断薬投与中に必須）
③METs → 代謝当量（日常生活・退院指導に活用）
④AT → 嫌気性代謝閾値（心不全・重症例で重要）

「どれをどんな患者に使うか」まで答えられると
試験で迷いがなくなります✅

問題集（全220問）はプロフのリンクから🔗
まず10問、無料でお試しできます

#心臓リハビリテーション指導士 #心リハ #理学療法士"""},

    "2026-06-04": {"app": "jinriha", "caption": """【腎リハ指導士試験】アプリで効率よく対策✅

「全9章・370問」を収録した問題集アプリです📱

✔ インストール不要・登録不要
✔ スマホブラウザで今すぐ使える
✔ 間違えた問題を自動で記録

まず10問、無料でお試しできます🎯

プロフのリンクから👆

#腎臓リハビリテーション指導士 #腎リハ #理学療法士"""},

    "2026-06-05": {"app": "kokyuriha", "caption": """【呼吸療法認定士試験】アプリで効率よく対策✅

「全8章・310問」を収録した問題集アプリです📱

✔ インストール不要・登録不要
✔ スマホブラウザで今すぐ使える
✔ 間違えた問題を自動で記録

まず10問、無料でお試しできます🎯

プロフのリンクから👆

#3学会合同呼吸療法認定士 #呼吸療法 #理学療法士"""},

    "2026-06-06": {"app": "jinriha", "caption": """【腎リハ指導士試験】今日の1問⚡️

慢性腎臓病（CKD）患者の
運動療法の絶対禁忌はどれか？

動画で一緒に考えてみてください👆

正解と解説も後半に出てきます✅

同じような問題が本番でも出ます
「なぜそれが正解か」の理由まで理解するのが合格への近道です

問題集（全370問）はプロフのリンクから🔗
まず10問、無料でお試しできます

#腎臓リハビリテーション指導士 #腎リハ試験対策 #理学療法士"""},

    "2026-06-07": {"app": "kokyuriha", "caption": """【呼吸療法認定士試験】今日の1問⚡️

COPD患者の呼吸リハビリで
最も推奨される運動強度はどれか？

動画で一緒に考えてみてください👆

正解と解説も後半に出てきます✅

同じような問題が本番でも出ます
「なぜそれが正解か」の理由まで理解するのが合格への近道です

問題集（全310問）はプロフのリンクから🔗
まず10問、無料でお試しできます

#3学会合同呼吸療法認定士 #呼吸療法試験対策 #理学療法士"""},

    "2026-06-08": {"app": "jinriha", "caption": """【保存推奨🔖】腎リハ試験で絶対出る数字5選

試験前日に見返したくなるやつをまとめました📊

①eGFR 15未満 → 末期腎不全（G5）の定義
②3ヶ月以上 → CKD診断の持続期間
③3METs → 透析患者の日常生活動作目安
④収縮期血圧180mmHg → 運動療法の絶対禁忌
⑤透析後2時間 → 運動開始を避ける推奨時間

数字はセットで覚えると試験で迷わない💡

問題集（全370問）はプロフのリンクから🔗
まず10問、無料でお試しできます

#腎臓リハビリテーション指導士 #腎リハ #理学療法士"""},

    "2026-06-09": {"app": "kokyuriha", "caption": """【保存推奨🔖】呼吸療法試験で絶対出る数字5選

試験前日に見返したくなるやつをまとめました📊

①FEV1/FVC 70%未満 → COPD診断の気流閉塞基準
②PaO₂ 60mmHg → 酸素療法開始の目安
③最大負荷の60〜80% → COPD運動強度の推奨値
④GOLD2 → FEV1 50〜80%（中等症）の目安
⑤25〜30m → 6分間歩行のMCID（最小臨床重要差）

数字の「なぜ」と一緒に覚えると記憶が定着する💡

問題集（全310問）はプロフのリンクから🔗
まず10問、無料でお試しできます

#3学会合同呼吸療法認定士 #呼吸療法 #理学療法士"""},

    "2026-06-10": {"app": "shinriha", "caption": """【保存推奨🔖】心リハ試験 よく間違える5選

似たもの同士が紛らわしい項目をまとめました⚠️

①Karvonen vs Borg → 薬物投与時はBorg（心拍が使えない）
②HFrEF vs HFpEF → LVEF 40%未満がrEF（収縮不全）
③AT vs VO₂max → 心リハではAT基準が安全
④3METs vs 5METs → 3=日常生活、5=就労復帰
⑤CPX vs 負荷心電図 → CPXで運動耐容能を定量評価

「紛らわしい=よく出る」と思って準備を💡

問題集（全220問）はプロフのリンクから🔗
まず10問、無料でお試しできます

#心臓リハビリテーション指導士 #心リハ #理学療法士"""},
}


# ---- スクリーンショット ----
def take_screenshot(url, out_path="/tmp/app_screen.png"):
    print(f"  スクリーンショット中: {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.screenshot(path=out_path, full_page=False)
        browser.close()
    print("  スクリーンショット完了")
    return out_path


# ---- X API ----
def upload_media(img_path):
    with open(img_path, "rb") as f:
        data = f.read()
    r = requests.post(UPLOAD_URL, auth=auth, files={"media": data})
    j = r.json()
    if "media_id_string" not in j:
        print(f"  メディアアップロードエラー: {j}")
        sys.exit(1)
    media_id = j["media_id_string"]
    print(f"  メディアID: {media_id}")
    return media_id


def post_tweet(text, media_id):
    MAX = 277
    truncated = text if len(text) <= MAX else text[:MAX] + "…"
    body = {"text": truncated, "media": {"media_ids": [media_id]}}
    r = requests.post(TWEET_URL, auth=auth, json=body)
    j = r.json()
    if "data" not in j:
        print(f"  ツイートエラー: {j}")
        sys.exit(1)
    print(f"  ✅ ツイート投稿完了！ ID: {j['data']['id']}")


# ---- schedule.json からの取得 ----
def get_from_schedule_json(today_str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    schedule_path = os.path.normpath(os.path.join(script_dir, "..", "..", "schedule.json"))
    if not os.path.exists(schedule_path):
        return None
    with open(schedule_path, encoding="utf-8") as f:
        schedule_data = json.load(f)
    if today_str not in schedule_data:
        return None
    entry = schedule_data[today_str]
    return {"app": entry.get("app", "shinriha"), "caption": entry.get("caption", "")}


# ---- メイン ----
if __name__ == "__main__":
    now_jst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    today_str = now_jst.strftime("%Y-%m-%d")
    print(f"現在時刻 (JST): {now_jst.strftime('%Y-%m-%d %H:%M')}")
    print(f"投稿日: {today_str}")

    # 1. schedule.json（自動生成）を優先
    entry = get_from_schedule_json(today_str)

    # 2. なければ固定 SCHEDULE
    if entry is None:
        if today_str not in SCHEDULE:
            print(f"本日（{today_str}）の投稿スケジュールはありません。")
            sys.exit(0)
        entry = SCHEDULE[today_str]

    app     = entry["app"]
    caption = entry["caption"]
    print(f"=== {today_str} {app} X投稿 ===")

    app_url  = APP_URLS.get(app, APP_URLS["shinriha"])
    img_path = take_screenshot(app_url)
    media_id = upload_media(img_path)
    post_tweet(caption, media_id)
