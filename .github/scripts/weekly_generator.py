#!/usr/bin/env python3
"""
Instagram 週次投稿コンテンツ自動生成スクリプト
毎週日曜日に GitHub Actions から実行される。
3アプリの questions.js から問題を選択し、カルーセル画像を生成して
schedule.json に翌週の投稿スケジュールを書き込む。
"""
import os, sys, json, re, random, textwrap, datetime, subprocess
from pathlib import Path

# ============================
# 設定
# ============================
APPS = {
    "shinriha": {
        "label": "心リハ",
        "full_label": "心臓リハビリテーション指導士",
        "color": (59, 130, 246),       # BLUE
        "questions_url": "https://raw.githubusercontent.com/kotachimaru/shinriha/main/questions.js",
        "total": 220,
        "hashtags": "#心臓リハビリテーション指導士 #心リハ試験対策 #理学療法士",
    },
    "jinriha": {
        "label": "腎リハ",
        "full_label": "腎臓リハビリテーション指導士",
        "color": (139, 92, 246),       # PURPLE
        "questions_url": "https://raw.githubusercontent.com/kotachimaru/jinriha/main/questions.js",
        "total": 370,
        "hashtags": "#腎臓リハビリテーション指導士 #腎リハ試験対策 #理学療法士",
    },
    "kokyuriha": {
        "label": "呼吸療法",
        "full_label": "3学会合同呼吸療法認定士",
        "color": (6, 182, 212),        # CYAN
        "questions_url": "https://raw.githubusercontent.com/kotachimaru/kokyuriha/main/questions.js",
        "total": 310,
        "hashtags": "#3学会合同呼吸療法認定士 #呼吸療法試験対策 #理学療法士",
    },
}

# 曜日→アプリ割り当て (月=0 〜 日=6)
WEEKDAY_TO_APP = {
    0: "shinriha",    # 月
    1: "jinriha",     # 火
    2: "kokyuriha",   # 水
    3: "shinriha",    # 木
    4: "jinriha",     # 金
    5: "kokyuriha",   # 土
    6: None,          # 日: 輪番（後で決定）
}

BASE_DIR   = Path(__file__).parent.parent.parent   # kotachimaru.github.io/
SCHEDULE_F = BASE_DIR / "schedule.json"
USED_F     = BASE_DIR / "used_questions.json"
CAROUSEL_D = BASE_DIR / "carousel"
CAROUSEL_D.mkdir(exist_ok=True)

WHITE  = (255, 255, 255)
BLACK  = (10, 10, 10)
GRAY   = (100, 100, 100)
LIGHT  = (245, 245, 245)
MEDIA  = "https://kotachimaru.github.io"

# ============================
# PIL フォント設定
# ============================
def get_pil():
    try:
        from PIL import Image, ImageDraw, ImageFont
        return Image, ImageDraw, ImageFont
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "Pillow", "-q"])
        from PIL import Image, ImageDraw, ImageFont
        return Image, ImageDraw, ImageFont

def get_font(size, bold=False):
    Image, ImageDraw, ImageFont = get_pil()
    paths = [
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

# ============================
# questions.js パーサー
# ============================
def fetch_questions(app_key):
    import requests
    url = APPS[app_key]["questions_url"]
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    js = resp.text
    # JS配列をJSONとして抽出
    m = re.search(r'const QUESTIONS\s*=\s*(\[.*?\]);', js, re.DOTALL)
    if not m:
        raise ValueError(f"QUESTIONS not found in {url}")
    return json.loads(m.group(1))

# ============================
# 使用済み問題の管理
# ============================
def load_used():
    if USED_F.exists():
        return json.loads(USED_F.read_text())
    return {"shinriha": [], "jinriha": [], "kokyuriha": []}

def save_used(used):
    USED_F.write_text(json.dumps(used, ensure_ascii=False, indent=2))

def pick_question(questions, used_ids):
    """未使用の問題からランダムに1問選ぶ。全部使い切ったらリセット。"""
    unused = [q for q in questions if q["id"] not in used_ids]
    if not unused:
        print("  全問使用済み→リセット")
        used_ids.clear()
        unused = questions
    q = random.choice(unused)
    used_ids.append(q["id"])
    return q

# ============================
# カルーセル画像生成
# ============================
def wrap_text(draw, text, font, max_width):
    """テキストを max_width 内で折り返す"""
    words = list(text)  # 日本語は1文字ずつ
    lines = []
    current = ""
    for ch in text:
        test = current + ch
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines

def draw_slide(draw, W, H, color, slide_type, app_key, content):
    """1枚のスライドを描画"""
    Image, ImageDraw, ImageFont = get_pil()

    # 背景
    draw.rectangle([0, 0, W, H], fill=(15, 15, 20))

    # アクセントバー（上部）
    draw.rectangle([0, 0, W, 8], fill=color)

    # アプリラベル（右上）
    label = APPS[app_key]["label"]
    f_label = get_font(28)
    draw.text((W - 20, 20), label, font=f_label, fill=color, anchor="ra")

    if slide_type == "question":
        # 問題スライド
        f_tag = get_font(32)
        draw.text((30, 30), "今日の1問 🔥", font=f_tag, fill=color)

        # 章名
        f_ch = get_font(26)
        draw.text((30, 80), f"【{content['chapterName']}】", font=f_ch, fill=GRAY)

        # 問題文
        f_q = get_font(38)
        q_lines = wrap_text(draw, content["question"], f_q, W - 60)
        y = 140
        for line in q_lines:
            draw.text((30, y), line, font=f_q, fill=WHITE)
            y += 52

        # スワイプ誘導
        f_sw = get_font(28)
        draw.text((W // 2, H - 50), "👉 スワイプして選択肢を見る", font=f_sw,
                  fill=GRAY, anchor="mm")

    elif slide_type == "choices":
        # 選択肢スライド
        f_title = get_font(34)
        draw.text((30, 30), "選択肢", font=f_title, fill=WHITE)
        draw.rectangle([30, 72, W - 30, 74], fill=color)

        nums = ["①", "②", "③", "④", "⑤"]
        f_c = get_font(32)
        y = 100
        for i, opt in enumerate(content["options"]):
            opt_lines = wrap_text(draw, f"{nums[i]} {opt}", f_c, W - 60)
            for line in opt_lines:
                draw.text((30, y), line, font=f_c, fill=WHITE)
                y += 46
            y += 6

        f_sw = get_font(28)
        draw.text((W // 2, H - 50), "👉 スワイプして答え合わせ", font=f_sw,
                  fill=GRAY, anchor="mm")

    elif slide_type == "answer":
        # 正解・解説スライド
        correct_idx = content["answer"] - 1
        nums = ["①", "②", "③", "④", "⑤"]
        correct_text = f"{nums[correct_idx]} {content['options'][correct_idx]}"

        # 正解ボックス
        f_ans = get_font(36)
        draw.rectangle([20, 20, W - 20, 110], fill=(*color, 40), outline=color, width=2)
        draw.text((W // 2, 42), "✅ 正解", font=f_ans, fill=color, anchor="mm")
        f_cor = get_font(34)
        cor_lines = wrap_text(draw, correct_text, f_cor, W - 60)
        y = 78
        for line in cor_lines:
            draw.text((W // 2, y), line, font=f_cor, fill=WHITE, anchor="mm")
            y += 42

        # 解説
        f_exp_title = get_font(30)
        draw.text((30, y + 10), "📝 解説", font=f_exp_title, fill=color)
        y += 50
        f_exp = get_font(28)
        exp_lines = wrap_text(draw, content["explanation"], f_exp, W - 60)
        for line in exp_lines[:8]:   # 最大8行
            draw.text((30, y), line, font=f_exp, fill=LIGHT)
            y += 40
            if y > H - 80:
                break

        # CTA
        f_cta = get_font(26)
        draw.rectangle([0, H - 70, W, H], fill=(25, 25, 35))
        total = APPS[app_key]["total"]
        draw.text((W // 2, H - 45), f"問題集（全{total}問）→ プロフのリンク🔗",
                  font=f_cta, fill=GRAY, anchor="mm")

def generate_carousel(app_key, question, week_str, day_idx):
    """3枚スライドのカルーセルを生成してファイル名リストを返す"""
    Image, ImageDraw, ImageFont = get_pil()
    W, H = 1080, 1080
    color = APPS[app_key]["color"]

    slide_types = ["question", "choices", "answer"]
    prefix = f"auto_{week_str}_{day_idx}"
    paths = []

    for i, stype in enumerate(slide_types):
        img = Image.new("RGB", (W, H), (15, 15, 20))
        draw = ImageDraw.Draw(img)
        draw_slide(draw, W, H, color, stype, app_key, question)

        fname = f"{prefix}_s{i+1}.jpg"
        fpath = CAROUSEL_D / fname
        img.save(str(fpath), "JPEG", quality=92)
        paths.append(fname)
        print(f"    生成: carousel/{fname}")

    return paths

# ============================
# キャプション生成
# ============================
def make_caption(app_key, question):
    app = APPS[app_key]
    nums = ["①", "②", "③", "④", "⑤"]
    correct_idx = question["answer"] - 1
    correct_text = question["options"][correct_idx]

    return f"""【{app['full_label']}】今日の1問🔥

{question['question']}

{chr(10).join(f'{nums[i]} {opt}' for i, opt in enumerate(question['options']))}

━━━━━━━━━━━━
✅ 正解：{nums[correct_idx]} {correct_text}
━━━━━━━━━━━━

問題集（全{app['total']}問）はプロフのリンクから🔗
まず10問、無料でお試しできます

{app['hashtags']}"""

# ============================
# メイン：翌週スケジュール生成
# ============================
def main():
    import requests

    # JST で今日の日付を取得（GitHub Actionsは UTC）
    now_jst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    # 翌週の月曜日を計算
    days_to_monday = (7 - now_jst.weekday()) % 7
    if days_to_monday == 0:
        days_to_monday = 7
    next_monday = now_jst.date() + datetime.timedelta(days=days_to_monday)
    week_str = next_monday.strftime("%Y%m%d")

    print(f"=== 週次生成開始 ===")
    print(f"実行日時 (JST): {now_jst.strftime('%Y-%m-%d %H:%M')}")
    print(f"生成対象週: {next_monday} 〜 {next_monday + datetime.timedelta(days=6)}")

    # 問題データ読み込み
    print("\n問題データ取得中...")
    all_questions = {}
    for key in APPS:
        print(f"  {APPS[key]['label']} ...", end="", flush=True)
        all_questions[key] = fetch_questions(key)
        print(f" {len(all_questions[key])}問")

    # 使用済み管理
    used = load_used()

    # 日曜のアプリ輪番（week_str から決定）
    sunday_apps = ["shinriha", "jinriha", "kokyuriha"]
    week_num = int(week_str) % 3
    sunday_app = sunday_apps[week_num]
    WEEKDAY_TO_APP[6] = sunday_app
    print(f"\n日曜アプリ: {APPS[sunday_app]['label']}")

    # 7日分の問題選択・画像生成
    schedule = {}
    print("\n各日の問題選択・画像生成:")

    for day_offset in range(7):
        target_date = next_monday + datetime.timedelta(days=day_offset)
        weekday = target_date.weekday()
        app_key = WEEKDAY_TO_APP[weekday]
        day_str = target_date.strftime("%Y-%m-%d")
        day_ja = ["月", "火", "水", "木", "金", "土", "日"][weekday]
        app_label = APPS[app_key]["label"]

        print(f"\n  {day_str}（{day_ja}）: {app_label}")

        q = pick_question(all_questions[app_key], used[app_key])
        print(f"    問題 id={q['id']}: {q['question'][:30]}...")

        # カルーセル画像生成
        slide_files = generate_carousel(app_key, q, week_str, day_offset + 1)

        # スケジュールエントリ作成
        schedule[day_str] = {
            "type": "carousel",
            "app": app_key,
            "app_label": app_label,
            "slides": [f"{MEDIA}/carousel/{f}" for f in slide_files],
            "caption": make_caption(app_key, q),
            "question_id": q["id"],
        }

    # schedule.json 保存
    SCHEDULE_F.write_text(json.dumps(schedule, ensure_ascii=False, indent=2))
    print(f"\nschedule.json 書き込み完了（{len(schedule)}件）")

    # used_questions.json 保存
    save_used(used)
    print("used_questions.json 更新完了")

    print("\n✅ 週次生成完了！")

if __name__ == "__main__":
    main()
