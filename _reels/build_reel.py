#!/usr/bin/env python3
"""릴스 조립 — 유튜브 클립 + 자막 → 1080×1920 mp4.

  /usr/bin/python3 build_reel.py <구성파일.json>

**API로 발행하지 않는다.** 인스타 API로 올린 릴스는 인스타 음원 라이브러리를 못 쓴다.
트렌딩 오디오는 도달에 실제로 영향이 크므로, 파일을 텔레그램으로 받아
인스타 앱에서 직접 올리며 음원을 붙인다. (CLAUDE.md 2026-08-03 조정)

구성 파일
```json
{
  "title": "성훈님 12주",
  "segments": [
    {"src": "/path/vid.mp4", "start": 128, "dur": 3.0, "mute": true,
     "lines": ["171cm 69.6kg", "2년 동안 안 변했습니다"]},
    {"still": "/path/sheet.jpg", "dur": 6.0, "lines": ["..."]}
  ]
}
```
`src`+`start`+`dur` 는 영상 구간, `still`+`dur` 는 정지 이미지.
`mute` 를 빼면 원본 소리를 남긴다 — 육성 후기 구간에서 쓴다.

가로 영상을 세로로 바꿀 때 잘라내지 않는다. 배경을 흐리게 깔고 원본을 얹는다.
측정 장면은 피사체가 가운데 있지 않아서, 크롭하면 잘리는 쪽이 생긴다.
"""
import json, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
VIDEO_Y = 470            # 영상이 놓이는 세로 위치
FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
FONT_BOLD = 6            # Apple SD Gothic Neo Bold
ROOT = Path(__file__).resolve().parent


def run(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ffmpeg 실패:\n{' '.join(args[:6])}…\n{r.stderr[-800:]}")


def caption_png(lines, out, size=76, y=1200, accent=None):
    """자막을 투명 PNG로 그린다. drawtext 는 한글 ttc 처리가 불안정해서 쓰지 않는다."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, size, index=FONT_BOLD)
    cy = y
    for i, line in enumerate(lines):
        col = "#F2B5A0" if (accent is not None and i == accent) else "#FFFFFF"
        w = d.textlength(line, font=f)
        # 검은 외곽선 — 어떤 배경에서도 읽힌다
        d.text((W / 2 - w / 2, cy), line, font=f, fill=col,
               stroke_width=8, stroke_fill=(0, 0, 0, 210))
        cy += size * 1.42
    img.save(out)


def segment(seg, idx, tmp):
    """구간 하나를 1080×1920 mp4로. 배경 흐림 + 원본 얹기 + 자막."""
    out = tmp / f"seg{idx:02d}.mp4"
    dur = float(seg["dur"])
    cap = tmp / f"cap{idx:02d}.png"
    caption_png(seg.get("lines", []), cap,
                size=seg.get("size", 76), y=seg.get("y", 1180),
                accent=seg.get("accent"))

    # 배경: 꽉 채워 자르고 흐리게 + 어둡게 / 전경: 가로 1080 맞춤
    vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
          f"crop={W}:{H},boxblur=28:2,eq=brightness=-0.16[bg];"
          f"[0:v]scale={W}:-2[fg];"
          f"[bg][fg]overlay=0:{VIDEO_Y}[v1];"
          f"[v1][1:v]overlay=0:0,format=yuv420p[v]")

    if "still" in seg:
        base = ["-loop", "1", "-t", str(dur), "-i", seg["still"]]
        amap = ["-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=44100:cl=stereo"]
        run(["ffmpeg", "-loglevel", "error", *base, "-i", str(cap), *amap,
             "-filter_complex", vf, "-map", "[v]", "-map", "2:a",
             "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-c:a", "aac", "-shortest", str(out), "-y"])
    else:
        base = ["-ss", str(seg["start"]), "-t", str(dur), "-i", seg["src"]]
        if seg.get("mute"):
            run(["ffmpeg", "-loglevel", "error", *base, "-i", str(cap),
                 "-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=44100:cl=stereo",
                 "-filter_complex", vf, "-map", "[v]", "-map", "2:a",
                 "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                 "-c:a", "aac", "-shortest", str(out), "-y"])
        else:
            run(["ffmpeg", "-loglevel", "error", *base, "-i", str(cap),
                 "-filter_complex", vf, "-map", "[v]", "-map", "0:a",
                 "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                 "-c:a", "aac", "-ar", "44100", "-ac", "2", str(out), "-y"])
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    outdir = ROOT / spec.get("slug", "reel")
    outdir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        parts = [segment(s, i, tmp) for i, s in enumerate(spec["segments"])]
        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
        final = outdir / "reel.mp4"
        run(["ffmpeg", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", str(lst), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
             str(final), "-y"])

    info = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
         "-of", "default=nw=1:nk=1", str(final)], capture_output=True, text=True).stdout.split()
    print(f"{final}")
    print(f"  {float(info[0]):.1f}초 · {int(info[1]) // 1024 // 1024}MB · {W}×{H}")


if __name__ == "__main__":
    main()
