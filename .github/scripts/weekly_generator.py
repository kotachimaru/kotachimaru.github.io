#!/usr/bin/env python3
"""
Instagram 週次投稿コンテンツ自動生成スクリプト
毎週日曜日に GitHub Actions から実行される。
3アプリの questions.js から問題を選択し、カルーセル画像を生成して
schedule.json に翌週の投稿スケジュールを書き込む。

特徴:
- 画像内に絵文字を使わない（文字化け対策）
- 本文を縦方向に中央寄せ・均等配置
- 解説を①②③単位で改行して可読性アップ
- 自己監査ループ: 80点を超えるまで問題を選び直す
"""
import os, sys, json, re, random, datetime
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
    0: "shinriha", 1: "jinriha", 2: "kokyuriha",
    3: "shinriha", 4: "jinriha", 5: "kokyuriha", 6: None,
}

BASE_DIR   = Path(__file__).parent.parent.parent   # kotachimaru.github.io/
SCHEDULE_F = BASE_DIR / "schedule.json"
USED_F     = BASE_DIR / "used_questions.json"
CAROUSEL_D = BASE_DIR / "carousel"
CAROUSEL_D.mkdir(exist_ok=True)

W, H   = 1080, 1080
MARGIN = 70
BODY_W = W - MARGIN * 2
WHITE  = (255, 255, 255)
GRAY   = (150, 150, 158)
LIGHT  = (225, 225, 232)
BG     = (15, 15, 20)
MEDIA  = "https://kotachimaru.github.io"

AUDIT_PASS = 80   # 合格点

# ============================
# PIL
# ============================
def get_pil():
    from PIL import Image, ImageDraw, ImageFont
    return Image, ImageDraw, ImageFont

_FONT_PATH = None
def font_path():
    global _FONT_PATH
    if _FONT_PATH:
        return _FONT_PATH
    for p in [
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]:
        if Path(p).exists():
            _FONT_PATH = p
            return p
    _FONT_PATH = None
    return None

def get_font(size):
    Image, ImageDraw, ImageFont = get_pil()
    p = font_path()
    return ImageFont.truetype(p, size) if p else ImageFont.load_default()

# ============================
# テキスト処理
# ============================
# 画像内では絵文字を使わない（文字化け対策）。絵文字・記号を除去。
EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "✅✨❤⁉‼⭐⭕️⃣]",
    flags=re.UNICODE)

def strip_emoji(s):
    return EMOJI_RE.sub("", s).strip()

def wrap_text(draw, text, font, max_width):
    """日本語テキストを max_width 内で1文字単位で折り返す"""
    lines, current = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(current); current = ""; continue
        test = current + ch
        if draw.textlength(test, font=font) > max_width and current:
            lines.append(current); current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines

def format_explanation(text):
    """解説を①②③④⑤ 単位（なければ。単位）の段落に分割"""
    text = strip_emoji(text)
    parts = re.split(r'(?=[①②③④⑤])', text)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) <= 1:
        parts = [s.strip() + "。" for s in text.split("。") if s.strip()]
    return parts

def fit_font(draw, build_lines, max_w, max_h, start, min_size, line_ratio=1.5):
    """build_lines(font)->行リスト。max_w×max_h に収まる最大サイズを返す。
    返り値: (font, lines, line_h, fits)  fits=収まったか"""
    size = start
    while size >= min_size:
        font = get_font(size)
        lines = build_lines(font)
        line_h = int(size * line_ratio)
        too_wide = any(draw.textlength(l, font=font) > max_w for l in lines)
        if len(lines) * line_h <= max_h and not too_wide:
            return font, lines, line_h, True
        size -= 2
    font = get_font(min_size)
    return font, build_lines(font), int(min_size * line_ratio), False

# ============================
# スライド描画（メトリクスを metrics に蓄積）
# ============================
def base_canvas(color, app_key):
    Image, ImageDraw, ImageFont = get_pil()
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 12], fill=color)              # 上部アクセント
    draw.text((W - MARGIN, 34), APPS[app_key]["label"],
              font=get_font(30), fill=color, anchor="ra")  # アプリ名（右上）
    return img, draw

def draw_question(color, app_key, q, metrics):
    img, draw = base_canvas(color, app_key)
    # ヘッダー
    draw.text((MARGIN, 38), "今日の1問", font=get_font(38), fill=color)
    draw.text((MARGIN, 96), f"【{strip_emoji(q['chapterName'])}】",
              font=get_font(28), fill=GRAY)
    # 本文（中央寄せ）
    zone_top, zone_bottom = 170, H - 120
    text = strip_emoji(q["question"])
    font, lines, lh, fits = fit_font(
        draw, lambda f: wrap_text(draw, text, f, BODY_W),
        BODY_W, zone_bottom - zone_top, start=56, min_size=30)
    total_h = len(lines) * lh
    y = zone_top + (zone_bottom - zone_top - total_h) // 2
    for line in lines:
        draw.text((W // 2, y), line, font=font, fill=WHITE, anchor="ma")
        y += lh
    # フッター
    draw.text((W // 2, H - 66), "スワイプして選択肢を見る  →",
              font=get_font(28), fill=GRAY, anchor="ma")
    metrics.append({"fits": fits, "truncated": False})
    return img

def draw_choices(color, app_key, q, metrics):
    img, draw = base_canvas(color, app_key)
    draw.text((MARGIN, 40), "選択肢", font=get_font(36), fill=WHITE)
    draw.rectangle([MARGIN, 96, W - MARGIN, 99], fill=color)
    nums = ["①", "②", "③", "④", "⑤"]
    opts = [f"{nums[i]} {strip_emoji(o)}" for i, o in enumerate(q["options"])]

    zone_top, zone_bottom = 150, H - 110
    # 各選択肢を折り返した全行を作る関数
    def build(font):
        all_lines = []
        for o in opts:
            wl = wrap_text(draw, o, font, BODY_W - 20)
            all_lines.extend(wl + [""])   # 選択肢ごとに空行
        return all_lines
    font, lines, lh, fits = fit_font(
        draw, build, BODY_W, zone_bottom - zone_top, start=40, min_size=24, line_ratio=1.4)
    total_h = len(lines) * lh
    y = zone_top + (zone_bottom - zone_top - total_h) // 2
    for line in lines:
        if line:
            draw.text((MARGIN, y), line, font=font, fill=WHITE)
        y += lh
    draw.text((W // 2, H - 60), "スワイプして答え合わせ  →",
              font=get_font(28), fill=GRAY, anchor="ma")
    metrics.append({"fits": fits, "truncated": False})
    return img

def draw_answer(color, app_key, q, metrics):
    img, draw = base_canvas(color, app_key)
    nums = ["①", "②", "③", "④", "⑤"]
    ci = q["answer"] - 1
    correct = f"{nums[ci]} {strip_emoji(q['options'][ci])}"

    # 正解ボックス（上部）※アプリ名ラベル（y34〜64）と重ならないよう下げる
    box_top, box_h = 92, 150
    dark = tuple(int(c * 0.30) for c in color)
    draw.rectangle([MARGIN, box_top, W - MARGIN, box_top + box_h],
                   fill=dark, outline=color, width=3)
    draw.text((W // 2, box_top + 26), "正  解", font=get_font(30),
              fill=color, anchor="ma")
    cfont, clines, clh, _ = fit_font(
        draw, lambda f: wrap_text(draw, correct, f, BODY_W - 60),
        BODY_W - 60, 70, start=38, min_size=24)
    cy = box_top + 78 + (66 - len(clines) * clh) // 2
    for line in clines:
        draw.text((W // 2, cy), line, font=cfont, fill=WHITE, anchor="ma")
        cy += clh

    # 解説（ボックス下〜フッター上のゾーンに縦中央寄せ）
    # 「解説」ラベルの高さ分(42px)を確保したうえでブロックを配置する
    label_h = 42
    zone_top, zone_bottom = box_top + box_h + label_h + 14, H - 96
    zone_h = zone_bottom - zone_top
    parts = format_explanation(q["explanation"])

    def build(font):
        all_lines = []
        for p in parts:
            all_lines.extend(wrap_text(draw, p, font, BODY_W))
            all_lines.append("")   # 段落間スペース
        # 末尾の空行は不要
        while all_lines and all_lines[-1] == "":
            all_lines.pop()
        return all_lines
    # 短い解説は大きめの文字で、長い解説は縮めて収める
    font, lines, lh, fits = fit_font(
        draw, build, BODY_W, zone_h, start=40, min_size=20, line_ratio=1.5)
    avail = zone_h // lh
    truncated = len(lines) > avail
    if truncated:
        lines = lines[:avail]
    total_h = len(lines) * lh
    # ブロックを縦中央寄せ（短い解説でも上に偏らない）
    offset = max(0, (zone_h - total_h) // 2)
    start_y = zone_top + offset
    # 「解説」ラベルはブロックの直上
    draw.text((MARGIN, start_y - label_h), "解説", font=get_font(30), fill=color)
    y = start_y
    for line in lines:
        if line:
            draw.text((MARGIN, y), line, font=font, fill=LIGHT)
        y += lh

    # フッターCTA
    draw.rectangle([0, H - 72, W, H], fill=(28, 28, 38))
    draw.text((W // 2, H - 48),
              f"問題集（全{APPS[app_key]['total']}問）→ プロフのリンク",
              font=get_font(26), fill=GRAY, anchor="ma")
    # 余白が大きすぎる場合のため充填率を記録
    fill_ratio = total_h / zone_h if zone_h else 1.0
    metrics.append({"fits": fits, "truncated": truncated, "fill_ratio": fill_ratio})
    return img

# ============================
# 自己監査
# ============================
def audit(metrics, q):
    """0-100 のスコアと問題点リストを返す"""
    score, issues = 100, []
    for i, m in enumerate(metrics, 1):
        if not m["fits"]:
            score -= 18
            issues.append(f"slide{i}: テキストがはみ出し気味")
        if m["truncated"]:
            score -= 25
            issues.append(f"slide{i}: 解説が長すぎて途切れた")
        # 解説スライドの充填率（縦中央寄せでも余白が大きすぎないか）
        fr = m.get("fill_ratio")
        if fr is not None:
            if fr < 0.35:
                score -= 15
                issues.append(f"slide{i}: 解説が短く余白が目立つ（充填率{fr:.0%}）")
            elif fr < 0.50:
                score -= 7
                issues.append(f"slide{i}: 解説がやや短い（充填率{fr:.0%}）")
    # 元データに絵文字が残っていないか（画像化前の素材チェック）
    raw = q["question"] + "".join(q["options"]) + q["explanation"]
    if EMOJI_RE.search(raw):
        # 除去はしているが、解説が極端に絵文字依存だと意味が崩れる可能性
        issues.append("元データに絵文字あり（画像では除去済み）")
    return max(0, score), issues

# ============================
# カルーセル生成（監査つき）
# ============================
def build_carousel_images(app_key, q):
    color = APPS[app_key]["color"]
    metrics = []
    imgs = [
        draw_question(color, app_key, q, metrics),
        draw_choices(color, app_key, q, metrics),
        draw_answer(color, app_key, q, metrics),
    ]
    score, issues = audit(metrics, q)
    return imgs, score, issues

def save_carousel(imgs, week_str, day_idx):
    paths = []
    for i, img in enumerate(imgs):
        fname = f"auto_{week_str}_{day_idx}_s{i+1}.jpg"
        img.save(str(CAROUSEL_D / fname), "JPEG", quality=92)
        paths.append(fname)
    return paths

# ============================
# データ取得・管理
# ============================
def fetch_questions(app_key):
    import requests
    js = requests.get(APPS[app_key]["questions_url"], timeout=30).text
    m = re.search(r'const QUESTIONS\s*=\s*(\[.*?\]);', js, re.DOTALL)
    if not m:
        raise ValueError(f"QUESTIONS not found: {app_key}")
    return json.loads(m.group(1))

def load_used():
    if USED_F.exists():
        return json.loads(USED_F.read_text())
    return {"shinriha": [], "jinriha": [], "kokyuriha": []}

def save_used(used):
    USED_F.write_text(json.dumps(used, ensure_ascii=False, indent=2))

def make_caption(app_key, q):
    app = APPS[app_key]
    nums = ["①", "②", "③", "④", "⑤"]
    ci = q["answer"] - 1
    opts = "\n".join(f"{nums[i]} {o}" for i, o in enumerate(q["options"]))
    return f"""【{app['full_label']}】今日の1問🔖

{q['question']}

{opts}

━━━━━━━━━━━━
✅ 正解：{nums[ci]} {q['options'][ci]}
━━━━━━━━━━━━

問題集（全{app['total']}問）はプロフのリンクから🔗
まず10問、無料でお試しできます

{app['hashtags']}"""

# ============================
# メイン
# ============================
def main():
    now_jst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    days_to_monday = (7 - now_jst.weekday()) % 7 or 7
    next_monday = now_jst.date() + datetime.timedelta(days=days_to_monday)
    week_str = next_monday.strftime("%Y%m%d")

    print("=== 週次生成開始 ===")
    print(f"実行 (JST): {now_jst:%Y-%m-%d %H:%M}")
    print(f"対象週: {next_monday} 〜 {next_monday + datetime.timedelta(days=6)}")

    print("\n問題データ取得中...")
    all_q = {}
    for key in APPS:
        all_q[key] = fetch_questions(key)
        print(f"  {APPS[key]['label']}: {len(all_q[key])}問")

    used = load_used()
    sunday_app = ["shinriha", "jinriha", "kokyuriha"][int(week_str) % 3]
    WEEKDAY_TO_APP[6] = sunday_app
    print(f"日曜アプリ: {APPS[sunday_app]['label']}")

    schedule = {}
    print("\n各日の生成（監査ループつき）:")
    for off in range(7):
        d = next_monday + datetime.timedelta(days=off)
        app_key = WEEKDAY_TO_APP[d.weekday()]
        day_ja = "月火水木金土日"[d.weekday()]
        print(f"\n  {d}（{day_ja}）{APPS[app_key]['label']}")

        # --- 監査ループ: 80点を超えるまで最大6回問題を選び直す ---
        best = None
        for attempt in range(1, 7):
            q = pick_candidate(all_q[app_key], used[app_key])
            imgs, score, issues = build_carousel_images(app_key, q)
            print(f"    試行{attempt}: id={q['id']} スコア={score}"
                  + (f" 課題={issues}" if issues else ""))
            if best is None or score > best[1]:
                best = (q, score, imgs)
            # 95点以上が取れたら即採用。それ未満なら最大6回まで試して最良を残す
            if score >= 95:
                break

        q, score, imgs = best
        used[app_key].append(q["id"])     # 採用した問題を使用済みに
        paths = save_carousel(imgs, week_str, off + 1)
        print(f"    → 採用 id={q['id']} スコア={score}")

        schedule[d.strftime("%Y-%m-%d")] = {
            "type": "carousel",
            "app": app_key,
            "app_label": APPS[app_key]["label"],
            "slides": [f"{MEDIA}/carousel/{p}" for p in paths],
            "caption": make_caption(app_key, q),
            "question_id": q["id"],
            "score": score,
        }

    SCHEDULE_F.write_text(json.dumps(schedule, ensure_ascii=False, indent=2))
    save_used(used)
    avg = sum(e["score"] for e in schedule.values()) / len(schedule)
    print(f"\nschedule.json 書き込み完了（{len(schedule)}件 / 平均スコア {avg:.0f}）")
    print("✅ 週次生成完了！")

def pick_candidate(questions, used_ids):
    """使用済みを避けて1問返す（採用確定はしない）"""
    unused = [q for q in questions if q["id"] not in used_ids]
    if not unused:
        used_ids.clear()
        unused = questions
    return random.choice(unused)

if __name__ == "__main__":
    main()
