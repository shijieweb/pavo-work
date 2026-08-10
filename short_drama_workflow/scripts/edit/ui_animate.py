# -*- coding: utf-8 -*-
"""
ui_animate.py —— 把 UI 参考静帧渲染成「动态」MP4，替代原静态静帧占位。
解决老板指出的：界面没有任何动态化（不对）。

做法：PIL 逐帧绘制（打字机 / 弹幕涌动 / 红警闪烁 / 倒计时跳动 / 悬念字渐显 /
战斗 HUD / 伤害飘字 / 战利品弹窗），ffmpeg 压成 clip_XX.mp4，命名与 assemble 一致。

零 AGNES 配额、本地运行、CJK 用项目根 simhei.ttf。
"""
import os, sys, json, math, subprocess, tempfile, shutil
import argparse
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FPS = 24
FONT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "simhei.ttf")
W, H = 1080, 1920

def load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()

def bg_from_ref(refs_dir, ref):
    p = os.path.join(refs_dir, f"{ref}.png")
    if os.path.isfile(p):
        im = Image.open(p).convert("RGB")
        im = im.resize((W, H))
        return im
    # 兜底纯色
    return Image.new("RGB", (W, H), (10, 10, 14))

def write_frames(tmp, frames):
    paths = []
    for i, fr in enumerate(frames):
        p = os.path.join(tmp, f"f{i:05d}.png")
        fr.save(p)
        paths.append(p)
    return paths

def encode(tmp, out_mp4, dur):
    lst = sorted(os.listdir(tmp))
    if not lst:
        raise RuntimeError("no frames")
    cmd = ["ffmpeg", "-y", "-framerate", str(FPS), "-i", os.path.join(tmp, "f%05d.png"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-t", f"{dur:.2f}", out_mp4]
    subprocess.run(cmd, capture_output=True)
    return out_mp4

# ---------- 动画基类工具 ----------
def fit_text(draw, text, font, max_w):
    """按宽度折行（中文按字符）"""
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        t = cur + ch
        if draw.textlength(t, font=font) > max_w and cur:
            lines.append(cur); cur = ch
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines

def draw_centered_text(img, text, font, fill, y_center, max_w=900, line_h=None, anchor="mm"):
    d = ImageDraw.Draw(img)
    lines = fit_text(d, text, font, max_w)
    lh = line_h or (font.size + 14)
    total = lh * len(lines)
    y = y_center - total/2 + lh/2
    for ln in lines:
        d.text((W/2, y), ln, font=font, fill=fill, anchor="mm")
        y += lh

# ---------- 各类 UI 动画 ----------
def anim_popup_typing(shot, bg, font, dur):
    """shot1 金色任务弹窗：弹入 + 金色辉光脉冲 + 打字机字幕"""
    frames = []
    sub = shot.get("subtitle", "")
    n = int(dur * FPS)
    type_n = max(8, int(n * 0.7))
    for f in range(n):
        im = bg.copy().convert("RGBA").filter(ImageFilter.GaussianBlur(2))
        d = ImageDraw.Draw(im)
        d.rectangle([0,0,W,H], fill=(0,0,0,120))  # 暗化
        # 弹窗缩放（前 12 帧弹入）
        t = min(1.0, f/12)
        e = 1 - (1-t)**3
        pw, ph = int(820*e), int(520*e)
        x0, y0 = (W-pw)//2, (H-ph)//2 - 80
        x1, y1 = x0+pw, y0+ph
        glow = int(120 + 80*math.sin(f/4))
        if pw > 20 and ph > 20:
            d.rounded_rectangle([x0-6, y0-6, x1+6, y1+6], radius=28, outline=(glow, int(glow*0.85), 90, 255), width=8)
            d.rounded_rectangle([x0, y0, x1, y1], radius=24, fill=(20,16,8,255), outline=(220,180,80,255), width=4)
            d.text((W/2, y0+70), "系 统 任 务", font=load_font(46), fill=(240,200,90,255), anchor="mm")
            if sub:
                shown = sub[:max(0, int(type_n * f / n))] if f < type_n else sub
                draw_centered_text(im, shown, font, (245,240,230,255), H/2 + 30, max_w=700)
        frames.append(im)
    return frames

def anim_chat_flood(shot, bg, font, dur):
    """shot8 弹幕涌动：多条气泡从底部依次冒出、上滚"""
    frames = []
    msgs = ["这方案谁拍的板？", "准点下班真香", "林小满又提前搞完了？", "这效率离谱啊",
            "拒绝无效加班！", "求带啊大佬", "整顿职场从我做起", "截图发群里", "主管都看愣了", "05后YYDS"]
    n = int(dur * FPS)
    base = bg.copy().convert("RGBA")
    for f in range(n):
        im = base.copy()
        d = ImageDraw.Draw(im)
        # 半透明聊天面板
        d.rectangle([40, H-900, W-40, H-120], fill=(10,12,20,170))
        # 当前可见气泡（按时间推进）
        visible = int(f / (n/len(msgs))) + 3
        y = H - 180
        for i in range(min(visible, len(msgs))):
            idx = len(msgs) - 1 - i
            txt = msgs[idx]
            bw = int(d.textlength(txt, font=font)) + 40
            alpha = 255 if i < 6 else max(40, 255 - (i-6)*40)
            d.rounded_rectangle([60, y-46, 60+bw, y], radius=20, fill=(30,40,70,alpha))
            d.text((80, y-23), txt, font=font, fill=(200,220,255,alpha), anchor="lm")
            y -= 64
        frames.append(im)
    return frames

def anim_warn_flash(shot, bg, font, dur):
    """shot9/11 红色警告：红框脉冲 + 轻微抖动 + 打字机字幕"""
    frames = []
    sub = shot.get("subtitle", "")
    n = int(dur * FPS)
    type_n = max(8, int(n * 0.6))
    for f in range(n):
        shx = int(6*math.sin(f/3)) if f < 10 else 0
        im = Image.new("RGB", (W, H), (12,4,4))
        im.paste(bg, (shx, 0))
        d = ImageDraw.Draw(im)
        pulse = int(120 + 100*math.sin(f/3))
        d.rectangle([30,30,W-30,H-30], outline=(pulse,40,40), width=10)
        if sub:
            shown = sub[:max(0, int(type_n * f / n))] if f < type_n else sub
            draw_centered_text(im, shown, load_font(52), (255,210,210), H/2, max_w=900)
        frames.append(im)
    return frames

def anim_countdown(shot, bg, font, dur):
    """shot13 处罚倒计时：数字逐秒递减 + 每跳缩放脉冲"""
    frames = []
    n = int(dur * FPS)
    start = 30
    for f in range(n):
        im = Image.new("RGB", (W, H), (8,4,4))
        d = ImageDraw.Draw(im)
        sec = start - int(f / FPS)
        if sec < 0: sec = 0
        txt = f"处罚倒计时 00:{sec:02d}"
        # 每秒初跳动
        phase = (f % FPS) / FPS
        scale = 1 + 0.25*max(0, 1 - phase*4)
        fs = int(64 * scale)
        d.text((W/2, H/2), txt, font=load_font(fs), fill=(255,80,80), anchor="mm")
        d.text((W/2, H/2+120), "系统判定中...", font=load_font(40), fill=(200,160,160), anchor="mm")
        frames.append(im)
    return frames

def anim_suspense(shot, bg, font, dur):
    """shot15 悬念：黑底 + 白字逐字渐显"""
    frames = []
    sub = shot.get("subtitle", "")
    n = int(dur * FPS)
    type_n = max(10, int(n*0.8))
    for f in range(n):
        im = Image.new("RGB", (W, H), (0,0,0))
        d = ImageDraw.Draw(im)
        if sub:
            cnt = max(0, int(type_n * f / n)) if f < type_n else len(sub)
            shown = sub[:cnt]
            # 当前字高亮
            draw_centered_text(im, shown, load_font(56), (240,240,240), H/2, max_w=900)
            if cnt < len(sub) and f % 24 < 12:
                pass
        frames.append(im)
    return frames

def anim_combat_hud(shot, bg, font, dur):
    """EP02 战斗 HUD：双方血条 + 战斗开始横幅滑入"""
    frames = []
    n = int(dur * FPS)
    for f in range(n):
        im = bg.copy()
        d = ImageDraw.Draw(im)
        # 顶部玩家血条
        d.rectangle([40,60,540,110], outline=(255,255,255), width=3)
        d.rectangle([44,64,536,106], fill=(60,200,80))
        d.text((50,40), "玩家739  Lv.1", font=load_font(34), fill=(230,230,230))
        # 顶部黑龙血条
        d.rectangle([W-540,60,W-40,110], outline=(255,255,255), width=3)
        d.rectangle([W-536,64,W-44,106], fill=(200,60,60))
        d.text((W-50,40), "全服黑龙  ???", font=load_font(34), fill=(230,230,230), anchor="rm")
        # 横幅滑入
        if f < 18:
            bx = int(W/2 + (1-f/18)*W)
        else:
            bx = W/2
        d.rectangle([bx-300, H/2-60, bx+300, H/2+60], fill=(180,30,30))
        d.text((bx, H/2), "战 斗 开 始", font=load_font(60), fill=(255,230,120), anchor="mm")
        frames.append(im)
    return frames

def anim_damage_numbers(shot, bg, font, dur):
    """EP02 伤害飘字：-9999 暴击 飞出"""
    frames = []
    n = int(dur * FPS)
    for f in range(n):
        im = bg.copy()
        d = ImageDraw.Draw(im)
        for k in range(5):
            appear = 10 + k*8
            if f < appear: continue
            prog = (f - appear) / 30
            if prog > 1: prog = 1
            x = 300 + k*120 + prog*200
            y = H/2 - 200 - prog*300
            size = int(70 * (1 - prog*0.3))
            col = (255, 220, 60) if k % 2 == 0 else (255, 120, 60)
            d.text((x, y), f"-{9999 - k*111}", font=load_font(size), fill=col, anchor="mm")
            if k == 0 and f > appear:
                d.text((x, y-90), "暴击!", font=load_font(56), fill=(255,80,80), anchor="mm")
        frames.append(im)
    return frames

def anim_loot_popup(shot, bg, font, dur):
    """EP02 战利品弹窗：宝箱光效 + 战利品列表渐显"""
    frames = []
    n = int(dur * FPS)
    loots = ["传说·屠龙者之刃 x1", "全服首杀称号 x1", "神装礼包 x3", "金币 +999999"]
    for f in range(n):
        im = bg.copy()
        d = ImageDraw.Draw(im)
        im = Image.alpha_composite(im.convert("RGBA"), Image.new("RGBA",(W,H),(0,0,0,100))).convert("RGB")
        d = ImageDraw.Draw(im)
        pw, ph = 760, 620
        x0, y0 = (W-pw)//2, (H-ph)//2 - 60
        glow = int(150 + 80*math.sin(f/4))
        d.rounded_rectangle([x0-6,y0-6,x0+pw+6,y0+ph+6], radius=24, outline=(glow,glow*0.8,90), width=6)
        d.rounded_rectangle([x0,y0,x0+pw,y0+ph], radius=20, fill=(18,14,6), outline=(220,180,80), width=4)
        d.text((W/2, y0+70), "★ 战 利 品 ★", font=load_font(48), fill=(240,200,90), anchor="mm")
        for i, lt in enumerate(loots):
            if f > 14 + i*10:
                d.text((W/2, y0+170 + i*100), lt, font=load_font(40), fill=(235,230,210), anchor="mm")
        frames.append(im)
    return frames

DISPATCH = {
    "popup_typing": anim_popup_typing,
    "chat_flood": anim_chat_flood,
    "warn_flash": anim_warn_flash,
    "countdown": anim_countdown,
    "suspense": anim_suspense,
    "combat_hud": anim_combat_hud,
    "damage_numbers": anim_damage_numbers,
    "loot_popup": anim_loot_popup,
}

def render_one(shot, refs_dir, out_clip):
    dur = shot.get("duration", 5)
    ref = shot.get("ref", "screen_base")
    bg = bg_from_ref(refs_dir, ref)
    anim = shot.get("ui_anim") or "popup_typing"
    fn = DISPATCH.get(anim, anim_popup_typing)
    font = load_font(48)
    frames = fn(shot, bg, font, dur)
    tmp = tempfile.mkdtemp(prefix="uianim_")
    try:
        write_frames(tmp, frames)
        encode(tmp, out_clip, dur)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out_clip

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--storyboard", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=999)
    args = ap.parse_args()
    sb = json.load(open(args.storyboard, encoding="utf-8"))
    refs_dir = os.path.join(args.out, "refs")
    clips_dir = os.path.join(args.out, "clips")
    os.makedirs(clips_dir, exist_ok=True)
    cnt = 0
    for shot in sb["shots"][:args.limit]:
        if not shot.get("ui_shot"):
            continue
        sid = shot["id"]
        out_clip = os.path.join(clips_dir, f"clip_{sid:02d}.mp4")
        render_one(shot, refs_dir, out_clip)
        sz = os.path.getsize(out_clip)
        print(f"[ui_anim] shot {sid:02d} -> {out_clip} ({sz}B)")
        cnt += 1
    print(f"[ui_anim] done, animated {cnt} UI shots")

if __name__ == "__main__":
    main()
