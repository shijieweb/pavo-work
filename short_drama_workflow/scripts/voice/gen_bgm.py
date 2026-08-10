# -*- coding: utf-8 -*-
"""
gen_bgm.py —— 程序化生成「占位」BGM 与音效（纯 Python，无外部依赖）。
⚠️ 仅作样片占位，正式发布前须替换为商用授权音乐（登记到执行手册 BGM 库）。

输出：
  <out>/audio/bgm_XX.wav   按 shot.emotion 合成的环境/情绪垫乐（时长=shot.duration）
  <out>/audio/sfx_XX.wav   按 shot.sfx 标签合成的音效（impact/typing/whoosh/roar/explosion）

assemble 阶段会把 对话 + bgm + sfx 三层混音。
"""
import os, sys, json, math, wave, random, argparse, struct

SR = 44100

NOTE = {  # 常用音高 -> 频率
    "C3":130.81,"E3":164.81,"G3":196.00,"A3":220.00,
    "C4":261.63,"E4":329.63,"G4":392.00,"A4":440.00,
    "C5":523.25,"E5":659.25,"G5":783.99,"A5":880.00,
}

def write_wav(path, samples):
    samples = [max(-1.0, min(1.0, s)) for s in samples]
    with wave.open(path, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        frames = b"".join(struct.pack("<h", int(s*32767)) for s in samples)
        w.writeframes(frames)

def env(n, a=0.02, d=0.1, s=0.7, r=0.2):
    """ADSR 包络（比例）"""
    out = []
    na, nd, nr = int(n*a), int(n*d), int(n*r)
    ns = n - na - nd - nr
    if ns < 0: ns = 0
    for i in range(na): out.append(i/na)
    for i in range(nd): out.append(1 - (1-s)*(i/nd))
    out += [s]*ns
    for i in range(nr): out.append(s*(1 - i/nr))
    return out[:n] or [0.0]*n

def tone(freq, dur, vol=0.3, harmonics=1, wave_type="sine"):
    n = int(SR*dur)
    e = env(n)
    out = []
    for i in range(n):
        t = i/SR
        v = 0.0
        base = math.sin(2*math.pi*freq*t)
        if harmonics > 1:
            base += 0.4*math.sin(2*math.pi*2*freq*t) + 0.2*math.sin(2*math.pi*3*freq*t)
        if wave_type == "tri":
            base = 2*abs(2*(t*freq - math.floor(t*freq+0.5)))-1
        v = base * e[i] * vol
        out.append(v)
    return out

def silence(dur):
    return [0.0]*int(SR*dur)

def mix_add(a, b, b_gain=1.0, offset=0):
    n = max(len(a), len(b)+offset)
    out = list(a) + [0.0]*(n-len(a))
    for i, v in enumerate(b):
        idx = i + offset
        if 0 <= idx < n:
            out[idx] += v*b_gain
    return out

# ---------------- BGM 按情绪 ----------------
def bgm_neutral(dur):
    seq = ["C4","E4","G4","C5"]
    out = silence(dur)
    step = 0.5
    t = 0.0
    while t < dur:
        f = NOTE[seq[int(t/step) % len(seq)]]
        seg = tone(f, step*0.9, vol=0.12, harmonics=2)
        out = mix_add(out, seg, 1.0, int(SR*t))
        t += step
    # 低频铺底
    pad = tone(65.4, dur, vol=0.05, harmonics=1)
    out = mix_add(out, pad, 1.0)
    return out

def bgm_angry(dur):
    out = silence(dur)
    # 低音脉冲鼓点
    beat = 0.5
    t = 0.0
    while t < dur:
        thump = tone(55, 0.25, vol=0.4, harmonics=2)
        out = mix_add(out, thump, 1.0, int(SR*t))
        t += beat
    # 紧张中频
    seq = ["A3","A3","C4","A3"]
    t = 0.0; step = 0.5
    while t < dur:
        f = NOTE[seq[int(t/step)%len(seq)]]
        seg = tone(f, step*0.8, vol=0.10, harmonics=2)
        out = mix_add(out, seg, 1.0, int(SR*t)); t += step
    return out

def bgm_excited(dur):
    seq = ["C5","E5","G5","E5"]
    out = silence(dur)
    step = 0.25
    t = 0.0
    while t < dur:
        f = NOTE[seq[int(t/step)%len(seq)]]
        seg = tone(f, step*0.9, vol=0.13, harmonics=2)
        out = mix_add(out, seg, 1.0, int(SR*t)); t += step
    return out

def bgm_sad(dur):
    seq = ["A3","C4","E4","C4"]
    out = silence(dur)
    step = 0.75
    t = 0.0
    while t < dur:
        f = NOTE[seq[int(t/step)%len(seq)]]
        seg = tone(f, step*0.95, vol=0.10, harmonics=1)
        out = mix_add(out, seg, 1.0, int(SR*t)); t += step
    return out

def bgm_combat(dur):
    out = bgm_angry(dur)
    # 叠加驱动中频
    seq = ["C4","G4","C4","G4"]
    t = 0.0; step = 0.25
    while t < dur:
        f = NOTE[seq[int(t/step)%len(seq)]]
        seg = tone(f, step*0.8, vol=0.08, harmonics=2)
        out = mix_add(out, seg, 1.0, int(SR*t)); t += step
    return out

BGM_DISPATCH = {
    "neutral": bgm_neutral, "angry": bgm_angry, "excited": bgm_excited,
    "sad": bgm_sad, "combat": bgm_combat, "": bgm_neutral,
}

# ---------------- SFX ----------------
def sfx_impact(dur=0.35):
    n = int(SR*dur)
    out = []
    for i in range(n):
        t = i/SR
        envv = math.exp(-t*12)
        noise = (random.random()*2-1)*0.5
        thump = math.sin(2*math.pi*60*t)*0.6
        out.append((noise+thump)*envv*0.8)
    return out

def sfx_explosion(dur=0.9):
    n = int(SR*dur)
    out = []
    for i in range(n):
        t = i/SR
        envv = math.exp(-t*4)
        noise = (random.random()*2-1)*0.6
        boom = math.sin(2*math.pi*(80-40*t)*t)*0.5
        out.append((noise+boom)*envv*0.9)
    return out

def sfx_typing(dur=0.6):
    out = []
    for k in range(8):
        t0 = k*0.07
        seg = sfx_impact(0.04)
        out = mix_add(out, [v*0.5 for v in seg], 1.0, int(SR*t0))
    out += silence(max(0, dur - len(out)/SR))
    return out[:int(SR*dur)] or silence(dur)

def sfx_whoosh(dur=0.8):
    n = int(SR*dur)
    out = []
    for i in range(n):
        t = i/SR
        envv = math.sin(math.pi*t/dur)
        noise = (random.random()*2-1)
        out.append(noise*envv*0.4)
    return out

def sfx_roar(dur=1.0):
    n = int(SR*dur)
    out = []
    for i in range(n):
        t = i/SR
        envv = 0.5+0.5*math.sin(2*math.pi*3*t)
        freq = 120 - 70*t
        tone_v = math.sin(2*math.pi*freq*t)
        noise = (random.random()*2-1)*0.4
        out.append((tone_v*0.6+noise)*envv*0.6)
    return out

SFX_DISPATCH = {
    "impact": sfx_impact, "explosion": sfx_explosion, "typing": sfx_typing,
    "whoosh": sfx_whoosh, "roar": sfx_roar,
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--storyboard", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=999)
    ap.add_argument("--global-mode", dest="global_mode", action="store_true",
                    help="产出整片全局BGM（忽略 storyboard，配合 --duration/--emotion）")
    ap.add_argument("--duration", type=float, default=60.0, help="全局BGM时长(秒)")
    ap.add_argument("--emotion", default="neutral", help="全局BGM情绪(neutral/angry/excited/sad/combat)")
    args = ap.parse_args()
    if args.global_mode:
        out = os.path.join(args.out, "bgm_global.wav")
        os.makedirs(args.out, exist_ok=True)
        write_wav(out, BGM_DISPATCH.get(args.emotion, bgm_neutral)(args.duration))
        print(f"[global-bgm] {out} dur={args.duration:.1f}s emo={args.emotion}")
        return
    sb = json.load(open(args.storyboard, encoding="utf-8"))
    audio_dir = os.path.join(args.out, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    for shot in sb["shots"][:args.limit]:
        sid = shot["id"]
        dur = shot.get("duration", 5)
        # BGM
        emo = shot.get("emotion", "neutral") or "neutral"
        bgm = BGM_DISPATCH.get(emo, bgm_neutral)(dur)
        write_wav(os.path.join(audio_dir, f"bgm_{sid:02d}.wav"), bgm)
        # SFX
        sfx_tag = shot.get("sfx")
        if sfx_tag:
            tags = sfx_tag if isinstance(sfx_tag, list) else [sfx_tag]
            sfx = silence(dur)
            for tg in tags:
                fn = SFX_DISPATCH.get(tg)
                if fn:
                    seg = fn()
                    sfx = mix_add(sfx, seg, 0.9, 0)
            write_wav(os.path.join(audio_dir, f"sfx_{sid:02d}.wav"), sfx)
        print(f"[bgm] shot {sid:02d} emotion={emo} sfx={sfx_tag}")

if __name__ == "__main__":
    main()
