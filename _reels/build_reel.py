#!/usr/bin/env python3
"""릴스 조립 — 유튜브 클립 + 자막 + 내레이션 → 1080×1920 mp4.

  python3 build_reel.py <구성파일.json>

**API로 발행하지 않는다.** 인스타 API로 올린 릴스는 인스타 음원 라이브러리를 못 쓴다.
트렌딩 오디오는 도달에 실제로 영향이 크므로, 파일을 텔레그램으로 받아
인스타 앱에서 직접 올리며 음원을 붙인다. (CLAUDE.md 2026-08-03 조정)

## 구조

한 **구간(segment)** 은 내레이션 한 토막이다. 길이는 목소리가 정한다.
그 안에서 **그림(shots)** 과 **자막(cues)** 은 따로 바뀐다.

```json
{
  "segments": [{
    "voice": {"src": "voice/take.m4a", "start": 1.3, "dur": 6.15, "tighten": 0.3},
    "shots": [
      {"src": "/path/a.mp4", "start": 16.5},
      {"src": "/path/b.mp4", "start": 36.0},
      {"still": "/path/sheet.jpg"}
    ],
    "cues": [
      {"lines": ["171cm"]},
      {"lines": ["69.6kg"], "accent": 0},
      {"lines": ["2년 동안", "안 변했습니다"], "t": 3.2}
    ]
  }]
}
```

**그림은 문장이 끝나기를 기다리지 않는다.** 말이 이어지는 중에 넘어가야
릴스 리듬이 산다. shots 에 `dur` 을 안 주면 구간 길이를 고르게 나눠 갖는다.

**자막은 말 단위로 바뀐다.** cue 에 `t` 를 안 주면 내레이션의 발화 구간을
찾아 자동으로 붙는다 (구간 수와 cue 수가 같을 때). 한 화면에 두 줄을 넘기지 않고
한 줄은 12자 안쪽으로 쓴다 — 인스타에서 그 이상은 읽히지 않는다.

`mute` 를 빼면 원본 소리를 남긴다 — 육성 후기 구간에서 쓴다.
`duck` 은 내레이션이 나오는 동안 원본 소리를 줄인다. 끊지 않고 서서히 올린다.

가로 영상을 세로로 바꿀 때 잘라내지 않는다. 배경을 흐리게 깔고 원본을 얹는다.
측정 장면은 피사체가 가운데 있지 않아서, 크롭하면 잘리는 쪽이 생긴다.
"""
import json, re, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1080, 1920
VIDEO_Y = 470            # 영상이 놓이는 세로 위치
FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
FONT_BOLD = 6            # Apple SD Gothic Neo Bold
SR = 44100
CAP_SIZE = 84            # 자막 기본 크기. 짧게 쓰는 대신 크게 띄운다
CAP_Y = 1210
ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent

# 내레이션 기준 음량. 성훈님 육성 구간이 -16 dB 언저리라 여기에 맞춘다.
LOUDNORM = f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample={SR}"

# 세로 변환 필터 — 배경은 꽉 채워 자르고 흐리게, 전경은 가로 1080 맞춤
# zoom > 1 이면 전경을 키운 뒤 중앙을 잘라 펀치인 효과 (레퍼런스 릴스의 컷 대체 리듬)
def vf_fit(zoom=1.0):
    fgw = round(W * zoom / 2) * 2
    fg = (f"[0:v]scale={fgw}:-2,crop={W}:ih*{W}/{fgw}[fg]" if zoom > 1.001
          else f"[0:v]scale={W}:-2[fg]")
    return (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},boxblur=28:2,eq=brightness=-0.16[bg];"
            f"{fg};[bg][fg]overlay=0:{VIDEO_Y},format=yuv420p[v]")

VF_FIT = vf_fit()


def run(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ffmpeg 실패:\n{' '.join(str(a) for a in args[:8])}…\n{r.stderr[-800:]}")


def probe_dur(path):
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip())


def resolve(p):
    """프로젝트 상대 경로도 받는다."""
    p = Path(p)
    return p if p.is_absolute() else (PROJECT / p)


def speech_spans(path, thresh=-45, gap=0.16, min_len=0.30):
    """소리 파일에서 말이 나오는 구간의 시작 시각들.

    silencedetect 는 숨소리나 음절 사이에서 0.2초짜리 허깨비 구간을 만들고,
    파일이 정적으로 끝나면 길이 0짜리 구간을 하나 더 얹는다. 그대로 쓰면
    자막이 0.2초 만에 지나가거나 마지막 한 장이 안 보인다.
    **min_len 보다 짧은 구간은 발화로 세지 않는다.**
    """
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-map", "0:a",
         "-af", f"silencedetect=noise={thresh}dB:d={gap}", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", r)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", r)]
    total = probe_dur(path)

    out, prev = [], 0.0
    for i, s in enumerate(starts):
        if s - prev >= min_len:
            out.append(prev)
        prev = ends[i] if i < len(ends) else total
    if total - prev >= min_len:
        out.append(prev)
    return out


def draw_lines(d, lines, size, y, accent):
    f = ImageFont.truetype(FONT, size, index=FONT_BOLD)
    cy = y
    for i, line in enumerate(lines):
        col = "#F2B5A0" if accent == i else "#FFFFFF"
        w = d.textlength(line, font=f)
        # 검은 외곽선 — 어떤 배경에서도 읽힌다
        d.text((W / 2 - w / 2, cy), line, font=f, fill=col,
               stroke_width=max(6, size // 9), stroke_fill=(0, 0, 0, 230))
        cy += size * 1.34


def caption_png(lines, out, size=CAP_SIZE, y=CAP_Y, accent=None):
    """자막을 투명 PNG로 그린다. drawtext 는 한글 ttc 처리가 불안정해서 쓰지 않는다."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # 두 줄이면 위로 올려 균형을 맞춘다
    draw_lines(ImageDraw.Draw(img), lines, size,
               y - (size * 0.67 if len(lines) > 1 else 0), accent)
    img.save(out)
    return out


def build_cover(cov, outdir, tmp):
    """릴스 커버(썸네일) 1080×1920. 본편과 같은 배치라 넘길 때 튀지 않는다.

    인스타는 프로필 격자에서 커버를 가운데로 잘라 보여준다. 위아래 끝은 잘린다고
    보고, 읽혀야 하는 글자는 영상 블록 가까이에 둔다.
    """
    frame = tmp / "cover_src.png"
    run(["ffmpeg", "-loglevel", "error", "-ss", str(cov["at"]),
         "-i", str(resolve(cov["src"])), "-frames:v", "1", str(frame), "-y"])

    src = Image.open(frame).convert("RGB")
    r = max(W / src.width, H / src.height)
    bg = src.resize((round(src.width * r), round(src.height * r)), Image.LANCZOS)
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2,
                  (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(28))).enhance(0.62)
    bg.paste(src.resize((W, round(src.height * W / src.width)), Image.LANCZOS), (0, VIDEO_Y))

    d = ImageDraw.Draw(bg)
    for blk in cov.get("blocks", []):
        draw_lines(d, blk["lines"], blk.get("size", 70), blk.get("y", 1200),
                   blk.get("accent"))
    out = outdir / "cover.jpg"
    bg.save(out, quality=92)
    return out


def build_voice(v, idx, tmp):
    """내레이션 한 토막을 wav 로 뽑는다. 정적 정리 → 음량 정규화 → 앞뒤 페이드."""
    out = tmp / f"vo{idx:02d}.wav"
    af = []
    gap = v.get("tighten")
    if gap:
        # 말 사이 정적을 gap 초까지 "줄인다". 없애는 게 아니다.
        #
        # start_duration 은 "이만큼 소리가 이어져야 통과시킨다" 는 뜻이라
        # 값을 키우면 말 첫머리가 그만큼 잘려나간다. 0에 가깝게 둔다.
        # start_silence / stop_silence 를 함께 줘야 정적이 0으로 붙지 않는다.
        # 둘을 빼면 단어가 서로 맞물려 발음이 뭉갠 것처럼 들린다.
        af.append(f"silenceremove=start_periods=1:start_duration=0.01:start_silence=0.18"
                  f":start_threshold=-45dB"
                  f":stop_periods=-1:stop_duration={gap}:stop_silence={gap}"
                  f":stop_threshold=-45dB:detection=peak")
    af.append(LOUDNORM)
    # 페이드는 첫 음절을 건드리지 않을 만큼만 (앞에 0.18초 여유가 있다)
    af.append("afade=t=in:st=0:d=0.03")
    run(["ffmpeg", "-loglevel", "error",
         "-ss", str(v["start"]), "-t", str(v["dur"]), "-i", str(resolve(v["src"])),
         "-map", "0:a", "-af", ",".join(af), "-ac", "2", "-ar", str(SR), str(out), "-y"])

    d = probe_dur(out)
    faded = tmp / f"vof{idx:02d}.wav"
    run(["ffmpeg", "-loglevel", "error", "-i", str(out),
         "-af", f"afade=t=out:st={max(0, d - 0.12):.3f}:d=0.12",
         "-ac", "2", "-ar", str(SR), str(faded), "-y"])
    return faded, d


def build_shots(seg, idx, tmp, dur):
    """구간의 그림. shots 가 여러 개면 이어 붙인다. 소리는 넣지 않는다."""
    shots = seg.get("shots") or [{k: seg[k] for k in ("src", "start", "still") if k in seg}]

    # dur 이 명시된 컷은 그대로 두고, 나머지가 남은 길이를 고르게 나눈다
    fixed = sum(float(s["dur"]) for s in shots if "dur" in s)
    free = [s for s in shots if "dur" not in s]
    each = (dur - fixed) / len(free) if free else 0
    if free and each <= 0:
        sys.exit(f"구간 {idx + 1}: 고정 컷 길이({fixed:.1f}초)가 구간({dur:.1f}초)보다 깁니다")

    parts = []
    for j, s in enumerate(shots):
        d = float(s.get("dur", each))
        out = tmp / f"shot{idx:02d}_{j}.mp4"
        if "still" in s:
            vin = ["-loop", "1", "-t", f"{d:.3f}", "-i", str(resolve(s["still"]))]
        else:
            vin = ["-ss", str(s["start"]), "-t", f"{d:.3f}", "-i", str(resolve(s["src"]))]
        run(["ffmpeg", "-loglevel", "error", *vin, "-filter_complex",
             vf_fit(float(s.get("zoom") or seg.get("zoom") or 1.0)),
             "-map", "[v]", "-an", "-r", "30", "-c:v", "libx264",
             "-preset", "medium", "-crf", "20", str(out), "-y"])
        parts.append(out)

    if len(parts) == 1:
        return parts[0]
    lst = tmp / f"shots{idx:02d}.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    joined = tmp / f"vid{idx:02d}.mp4"
    run(["ffmpeg", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", str(joined), "-y"])
    return joined


def cue_times(seg, cues, vo, dur):
    """자막이 뜨는 시각.

    기준은 **내레이션의 실제 발화 구간**이다. 눈대중으로 초를 찍으면
    말과 자막이 어긋난다. 한 발화 안에서 자막을 여러 장 넘길 때는
    `span` 으로 같은 구간에 묶고, 그 안을 글자 수 비율로 나눈다.
    `w` 를 주면 그 값으로 나눈다 — 자막을 줄여 쓴 경우 실제 말한 글자 수를 적는다.
    """
    if all("t" in c for c in cues):
        return [float(c["t"]) for c in cues]
    spans = speech_spans(vo) if vo else []
    off = float(seg.get("voice_at", 0))
    if not spans:
        return [dur * i / len(cues) for i in range(len(cues))]

    bounds = [s + off for s in spans] + [dur]
    groups = [c.get("span", i) for i, c in enumerate(cues)]
    if max(groups) >= len(spans):
        print(f"    · 발화 {len(spans)}구간 ≠ 자막 {len(cues)}장 → 균등 배분")
        return [dur * i / len(cues) for i in range(len(cues))]

    times, i = [], 0
    while i < len(cues):
        g = groups[i]
        j = i
        while j < len(cues) and groups[j] == g:
            j += 1
        t0, t1 = bounds[g], bounds[g + 1]
        ws = [float(c.get("w") or sum(len(x) for x in c["lines"])) for c in cues[i:j]]
        acc = t0
        for w in ws:
            # 말이 시작되기 살짝 전에 띄운다 — 자막이 늦으면 읽기 전에 넘어간다
            times.append(max(0.0, acc - 0.10))
            acc += (t1 - t0) * w / sum(ws)
        i = j
    return times


def burn_captions(vid, seg, idx, tmp, dur, vo):
    """자막을 시각별로 얹는다. 한 장씩 켜고 끈다."""
    cues = seg.get("cues") or ([{"lines": seg["lines"], "size": seg.get("size"),
                                 "y": seg.get("y"), "accent": seg.get("accent")}]
                               if seg.get("lines") else [])
    if not cues:
        return vid

    ts = cue_times(seg, cues, vo, dur)
    inputs, chain, last = [], [], "0:v"
    for j, (c, t0) in enumerate(zip(cues, ts)):
        t1 = ts[j + 1] if j + 1 < len(ts) else dur + 1
        png = caption_png(c["lines"], tmp / f"cap{idx:02d}_{j}.png",
                          size=c.get("size") or seg.get("size") or CAP_SIZE,
                          y=c.get("y") or seg.get("y") or CAP_Y,
                          accent=c.get("accent"))
        inputs += ["-i", str(png)]
        tag = "v" if j == len(cues) - 1 else f"v{j}"
        chain.append(f"[{last}][{j + 1}:v]overlay=0:0:"
                     f"enable='between(t,{t0:.3f},{t1:.3f})'[{tag}]")
        last = tag
    out = tmp / f"cap{idx:02d}.mp4"
    run(["ffmpeg", "-loglevel", "error", "-i", str(vid), *inputs,
         "-filter_complex", ";".join(chain), "-map", "[v]", "-an",
         "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         str(out), "-y"])
    print("    자막  " + " / ".join(f"{t:.1f}s {c['lines'][0]}" for c, t in zip(cues, ts)))
    return out


def build_audio(seg, idx, tmp, dur, vo):
    """구간의 소리. 원본(또는 무음) 위에 내레이션을 얹는다."""
    out = tmp / f"aud{idx:02d}.wav"
    silent = seg.get("mute") or seg.get("shots") or "still" in seg or "src" not in seg
    if silent:
        base = ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", f"anullsrc=r={SR}:cl=stereo"]
    else:
        base = ["-ss", str(seg["start"]), "-t", f"{dur:.3f}", "-i", str(resolve(seg["src"]))]

    if vo is None:
        run(["ffmpeg", "-loglevel", "error", *base, "-map", "0:a",
             "-af", f"aresample={SR}", "-ac", "2", "-ar", str(SR), str(out), "-y"])
        return out

    # 원본을 내레이션 동안 줄였다가 0.4초에 걸쳐 되돌린다 (딸깍 방지)
    duck, lvl = float(seg.get("duck", 0)), seg.get("duck_level", 0.18)
    pre = (f"volume=volume='{lvl}+{1 - lvl:.2f}*clip((t-{duck:.3f})/0.4\\,0\\,1)':eval=frame"
           if duck > 0 else "anull")
    delay = int(float(seg.get("voice_at", 0)) * 1000)
    # 원본 소리를 말 도중에 끊으면 딸깍 소리가 난다. 끝에 짧은 페이드를 건다.
    fade = "" if silent else f",afade=t=out:st={max(0, dur - 0.09):.3f}:d=0.09"
    fc = (f"[0:a]aresample={SR},{pre}{fade}[b];[1:a]adelay={delay}|{delay}[v];"
          f"[b][v]amix=inputs=2:duration=first:normalize=0[a]")
    run(["ffmpeg", "-loglevel", "error", *base, "-i", str(vo),
         "-filter_complex", fc, "-map", "[a]",
         "-ac", "2", "-ar", str(SR), "-t", f"{dur:.3f}", str(out), "-y"])
    return out


def segment(seg, idx, tmp):
    vo, vo_dur = (build_voice(seg["voice"], idx, tmp) if "voice" in seg else (None, 0.0))
    if vo and seg.get("fit", True):
        dur = vo_dur + float(seg.get("voice_at", 0)) + float(seg.get("tail", 0.3))
    else:
        dur = float(seg["dur"])

    vid = build_shots(seg, idx, tmp, dur)
    vid = burn_captions(vid, seg, idx, tmp, dur, vo)
    aud = build_audio(seg, idx, tmp, dur, vo)

    out = tmp / f"seg{idx:02d}.mp4"
    run(["ffmpeg", "-loglevel", "error", "-i", str(vid), "-i", str(aud),
         "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-ar", str(SR), "-ac", "2", "-shortest", str(out), "-y"])
    return out, dur


def panel_png(pnl, active, out):
    """진행형 리스트 패널 — 영상 위에 상시 떠 있고, 말하는 항목만 강조된다.

    레퍼런스(2026-08-13 제보 해부)의 트리 다이어그램 문법. 항목 리스트가 계속
    보여서 저장 욕구를 만들고, 하이라이트가 '지금 어디쯤'을 알려준다.
    """
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    size = pnl.get("size", 42)
    x, y = pnl.get("x", 56), pnl.get("y", 560)
    f = ImageFont.truetype(FONT, size, index=FONT_BOLD)
    for i, item in enumerate(pnl["items"]):
        col = "#F2B5A0" if i == active else "#FFFFFF"
        mark = "●" if i == active else "○"
        d.text((x, y), f"{mark} {item}", font=f, fill=col,
               stroke_width=max(4, size // 10), stroke_fill=(0, 0, 0, 230))
        y += int(size * 1.75)
    img.save(out)
    return out


def apply_panel(spec, final, tmp):
    pnl = spec.get("panel")
    if not pnl:
        return
    total = probe_dur(final)
    times = [float(t) for t in pnl["times"]]
    wins = [(-1, 0.0, times[0])] + [
        (i, times[i], times[i + 1] if i + 1 < len(times) else total)
        for i in range(len(times))]
    ins, chain, last = ["-i", str(final)], [], "0:v"
    for j, (act, t0, t1) in enumerate(wins):
        png = panel_png(pnl, act, tmp / f"panel{j}.png")
        ins += ["-i", str(png)]
        tag = "v" if j == len(wins) - 1 else f"p{j}"
        chain.append(f"[{last}][{j + 1}:v]overlay=0:0:"
                     f"enable='between(t,{t0:.2f},{t1:.2f})'[{tag}]")
        last = tag
    out = tmp / "panel.mp4"
    run(["ffmpeg", "-loglevel", "error", *ins, "-filter_complex", ";".join(chain),
         "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium",
         "-crf", "20", "-c:a", "copy", str(out), "-y"])
    out.replace(final)
    print(f"  패널 {len(pnl['items'])}항목 · 전환 {len(times)}회")


def apply_bgm(spec, final, tmp):
    """전 구간 저음량 BGM. 레퍼런스 3편 모두 무음 구간 0 — BGM이 바닥을 깔아준다.

    IG·틱톡은 앱에서 음원을 얹는 정책이므로 이 옵션은 주로 유튜브 쇼츠 파일용.
    """
    bgm = spec.get("bgm")
    if not bgm:
        return
    total = probe_dur(final)
    gain = float(bgm.get("gain_db", -22))
    out = tmp / "bgm.mp4"
    run(["ffmpeg", "-loglevel", "error", "-i", str(final),
         "-stream_loop", "-1", "-i", str(resolve(bgm["src"])),
         "-filter_complex",
         f"[1:a]atrim=0:{total:.3f},volume={gain}dB,"
         f"afade=t=out:st={max(0, total - 1.2):.3f}:d=1.2[b];"
         f"[0:a][b]amix=inputs=2:duration=first:normalize=0[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "160k", "-ar", str(SR),
         "-t", f"{total:.3f}", str(out), "-y"])
    out.replace(final)
    print(f"  BGM {Path(str(bgm['src'])).name} @ {gain}dB")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    outdir = ROOT / spec.get("slug", "reel")
    outdir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        parts, durs, t = [], [], 0.0
        for i, s in enumerate(spec["segments"]):
            shots = len(s.get("shots") or [1])
            print(f"  {i + 1}. {t:5.1f}s ~ {t + 0:5.1f}s  (컷 {shots}개)")
            p, d = segment(s, i, tmp)
            print(f"    길이  {d:.1f}초 → {t + d:.1f}s")
            parts.append(p)
            durs.append(d)
            t += d
        if "cover" in spec:
            print(f"\n  커버 {build_cover(spec['cover'], outdir, tmp)}")
        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
        final = outdir / "reel.mp4"
        xf = float(spec.get("xfade", 0))
        if xf and len(parts) > 1:
            # 세그먼트 사이를 디졸브 + 오디오 크로스페이드로 잇는다.
            # 하드컷의 점프컷·룸톤 단절을 없앤다. 0.2~0.3초가 자연스럽다.
            ins, vf, af = [], [], []
            for p in parts:
                ins += ["-i", str(p)]
            off, vprev, aprev = 0.0, "0:v", "0:a"
            for i in range(1, len(parts)):
                off += durs[i - 1] - xf
                vtag, atag = f"v{i}", f"a{i}"
                vf.append(f"[{vprev}][{i}:v]xfade=transition=fade"
                          f":duration={xf}:offset={off:.3f}[{vtag}]")
                af.append(f"[{aprev}][{i}:a]acrossfade=d={xf}[{atag}]")
                vprev, aprev = vtag, atag
            chain = ";".join(vf + af)
            vmap = f"[{vprev}]"
            if spec.get("overlay"):
                ins += ["-i", str(resolve(spec["overlay"]))]
                chain += f";[{vprev}][{len(parts)}:v]overlay=0:0[vo]"
                vmap = "[vo]"
            run(["ffmpeg", "-loglevel", "error", *ins,
                 "-filter_complex", chain, "-map", vmap, "-map", f"[{aprev}]",
                 "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                 "-c:a", "aac", "-b:a", "160k", "-ar", str(SR),
                 "-movflags", "+faststart", str(final), "-y"])
        elif spec.get("overlay"):
            # 전체 구간 고정 오버레이 (제목·로고 등). 1080×1920 투명 PNG.
            run(["ffmpeg", "-loglevel", "error", "-f", "concat", "-safe", "0",
                 "-i", str(lst), "-i", str(resolve(spec["overlay"])),
                 "-filter_complex", "[0:v][1:v]overlay=0:0[v]",
                 "-map", "[v]", "-map", "0:a?",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                 "-c:a", "aac", "-b:a", "160k", "-ar", str(SR),
                 "-movflags", "+faststart", str(final), "-y"])
        else:
            run(["ffmpeg", "-loglevel", "error", "-f", "concat", "-safe", "0",
                 "-i", str(lst), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                 "-c:a", "aac", "-b:a", "160k", "-ar", str(SR), "-movflags", "+faststart",
                 str(final), "-y"])
        apply_panel(spec, final, tmp)
        apply_bgm(spec, final, tmp)

    of = float(spec.get("outro_fade", 0))
    if of:
        # 끝맺음 — 마지막 프레임을 잠깐 정지(hold)로 잡아두고 그 위에서 페이드아웃.
        # 소스에서 구간을 연장하면 다음 문장 첫머리가 끼어들 수 있어 정지 프레임을 쓴다.
        hold = float(spec.get("outro_hold", 0.45))
        d = probe_dur(final)
        end = d + hold
        closed = final.with_name("reel_closed.mp4")
        run(["ffmpeg", "-loglevel", "error", "-i", str(final),
             "-vf", f"tpad=stop_mode=clone:stop_duration={hold},"
                    f"fade=t=out:st={end - of:.3f}:d={of}",
             "-af", f"apad=pad_dur={hold},"
                    f"afade=t=out:st={max(0, end - of - 0.2):.3f}:d={of + 0.2}",
             "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-c:a", "aac", "-b:a", "160k", "-ar", str(SR),
             "-movflags", "+faststart", str(closed), "-y"])
        closed.replace(final)

    info = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
         "-of", "default=nw=1:nk=1", str(final)], capture_output=True, text=True).stdout.split()
    print(f"\n{final}")
    print(f"  {float(info[0]):.1f}초 · {int(info[1]) // 1024 // 1024}MB · {W}×{H}")


if __name__ == "__main__":
    main()
