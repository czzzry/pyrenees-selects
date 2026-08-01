#!/usr/bin/env python3
"""Build deterministic 4K picture and audio assets for the Pyrenees v6 edit."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


FFMPEG = Path("/usr/local/bin/ffmpeg")
FFPROBE = Path("/usr/local/bin/ffprobe")
PHONE = Path(
    "/Users/cezarybaraniecki/Documents/AI project/AI Video Editor/"
    "raw_footage/phone_pyrenees_2024"
)
DRONE = Path("/Users/cezarybaraniecki/Documents/DJI drone")
APP_SUPPORT = Path(
    "/Users/cezarybaraniecki/Library/Application Support/Pyrenees Selects"
)
V2 = APP_SUPPORT / "revisions_v2"
V5 = APP_SUPPORT / "revisions_v5"
OUT = APP_SUPPORT / "revisions_v6"
HYPERLAPSE = DRONE / "HYPERLAPSE/001_0065"
FONT = Path("/System/Library/Fonts/Supplemental/Didot.ttc")

FPS = "30000/1001"
HARDWARE_VIDEO = [
    "-c:v",
    "h264_videotoolbox",
    "-b:v",
    "50M",
    "-maxrate",
    "70M",
    "-bufsize",
    "100M",
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
]


def run(*args: str) -> None:
    destination = Path(args[-1])
    if destination.suffix.lower() in {".mp4", ".mov", ".wav"}:
        if destination.exists() and destination.stat().st_size > 1024:
            probe = subprocess.run(
                [
                    str(FFPROBE),
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(destination),
                ],
                capture_output=True,
                text=True,
            )
            if probe.returncode == 0 and probe.stdout.strip():
                return
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def has_audio(path: Path) -> bool:
    probe = subprocess.run(
        [
            str(FFPROBE),
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(probe.stdout.strip())


def render_title_overlay() -> Path:
    overlay = OUT / "Pyrenees-Extended-Cut-title-overlay-v6.png"
    canvas = Image.new("RGBA", (3840, 2160), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    title_font = ImageFont.truetype(str(FONT), 270)
    year_font = ImageFont.truetype(str(FONT), 94)
    subtitle_font = ImageFont.truetype(str(FONT), 58)

    def centered(text: str, y: int, font: ImageFont.FreeTypeFont, spacing: int = 0) -> None:
        if spacing:
            widths = [draw.textlength(char, font=font) for char in text]
            width = sum(widths) + spacing * (len(text) - 1)
            x = (3840 - width) / 2
            for char, char_width in zip(text, widths):
                draw.text(
                    (x, y),
                    char,
                    font=font,
                    fill=(255, 255, 255, 242),
                    stroke_width=2,
                    stroke_fill=(0, 0, 0, 115),
                )
                x += char_width + spacing
        else:
            box = draw.textbbox((0, 0), text, font=font, stroke_width=2)
            x = (3840 - (box[2] - box[0])) / 2
            draw.text(
                (x, y),
                text,
                font=font,
                fill=(255, 255, 255, 242),
                stroke_width=2,
                stroke_fill=(0, 0, 0, 115),
            )

    centered("PYRENEES", 870, title_font, 18)
    centered("2024", 1235, year_font, 20)
    centered("THE EXTENDED CUT", 1390, subtitle_font, 12)
    canvas.save(overlay)
    return overlay


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    overlay = render_title_overlay()

    run(
        "-framerate",
        FPS,
        "-i",
        str(HYPERLAPSE / "HYPERLAPSE_%04d.JPG"),
        "-loop",
        "1",
        "-i",
        str(overlay),
        "-filter_complex",
        (
            "[0:v]scale=3840:-2:flags=lanczos,"
            "crop=3840:2160:(iw-ow)/2:(ih-oh)/2,setsar=1[bg];"
            "[1:v]format=rgba,fade=t=in:st=0.25:d=0.75:alpha=1,"
            "fade=t=out:st=2.85:d=0.75:alpha=1[text];"
            "[bg][text]overlay=0:0:shortest=1,format=nv12[v]"
        ),
        "-map",
        "[v]",
        "-t",
        "4.170833",
        "-r",
        FPS,
        "-an",
        *HARDWARE_VIDEO,
        str(OUT / "Pyrenees-clean-hyperlapse-title-v6.mp4"),
    )

    fixed_phone = (
        ("01-train-v6.mp4", "PXL_20240612_092451722.mp4", 0.0, 8.8, 6.006),
        ("02-phone-c83-v6.mp4", "PXL_20240612_110104817.mp4", 18.0, 10.0, 5.005),
        ("07-phone-c88-v6.mp4", "PXL_20240613_072239313.mp4", 6.0, 8.0, 5.005),
        ("19-phone-c111-v6.mp4", "PXL_20240615_052909649.mp4", 0.0, 18.7, 8.008),
        ("21-phone-c116-v6.mp4", "PXL_20240615_122335379.mp4", 0.0, 8.0, 5.005),
        ("25-phone-c124-v6.mp4", "PXL_20240616_122129085.mp4", 4.0, 8.0, 5.005),
    )
    for output_name, source_name, source_start, source_duration, target_duration in fixed_phone:
        playback_rate = source_duration / target_duration
        source_path = PHONE / source_name
        common = [
            "-hwaccel",
            "videotoolbox",
            "-ss",
            f"{source_start:.6f}",
            "-t",
            f"{source_duration:.6f}",
            "-i",
            str(source_path),
        ]
        if has_audio(source_path):
            run(
                *common,
                "-filter_complex",
                (
                    f"[0:v]setpts=(PTS-STARTPTS)/{playback_rate:.9f},"
                    f"fps={FPS},format=nv12[v];"
                    f"[0:a]atrim=0:{target_duration:.6f},"
                    "asetpts=PTS-STARTPTS,aresample=48000[a]"
                ),
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-t",
                f"{target_duration:.6f}",
                *HARDWARE_VIDEO,
                "-c:a",
                "aac",
                "-b:a",
                "256k",
                str(OUT / output_name),
            )
        else:
            run(
                *common,
                "-vf",
                (
                    f"setpts=(PTS-STARTPTS)/{playback_rate:.9f},"
                    f"fps={FPS},format=nv12"
                ),
                "-an",
                "-t",
                f"{target_duration:.6f}",
                *HARDWARE_VIDEO,
                str(OUT / output_name),
            )

    run(
        "-i",
        str(OUT / "Pyrenees-clean-hyperlapse-title-v6.mp4"),
        "-i",
        str(OUT / "01-train-v6.mp4"),
        "-filter_complex",
        "[0:v]setsar=1[a];[1:v]setsar=1[b];[a][b]concat=n=2:v=1:a=0[v]",
        "-map",
        "[v]",
        "-t",
        "10.176839",
        "-an",
        *HARDWARE_VIDEO,
        str(OUT / "Pyrenees-opening-picture-title-train-v6.mp4"),
    )

    run(
        "-hwaccel",
        "videotoolbox",
        "-ss",
        "9.009",
        "-t",
        "6.006",
        "-i",
        str(DRONE / "DJI_20240613101804_0014_D.MP4"),
        "-vf",
        "eq=brightness=0.025:contrast=1.06:saturation=1.03,format=nv12",
        "-an",
        *HARDWARE_VIDEO,
        str(OUT / "09-person-visible-pullback-v6.mp4"),
    )

    cat_zoom = (
        "setpts=(PTS-STARTPTS)/1.3,fps=30000/1001,"
        "zoompan="
        "z='if(lte(on,60),1,if(lte(on,105),1+0.25*(on-60)/45,"
        "1.25+0.35*(on-105)/44))':"
        "x='max(0,min(iw-iw/zoom,iw*0.76-iw/(2*zoom)))':"
        "y='max(0,min(ih-ih/zoom,ih*0.60-ih/(2*zoom)))':"
        "d=1:s=3840x2160:fps=30000/1001,"
        "eq=contrast=1.05:saturation=1.04,format=nv12"
    )
    run(
        "-hwaccel",
        "videotoolbox",
        "-t",
        "6.5",
        "-i",
        str(PHONE / "PXL_20240613_151657586.TS.mp4"),
        "-vf",
        cat_zoom,
        "-t",
        "5.005",
        "-an",
        *HARDWARE_VIDEO,
        str(OUT / "12-cat-delayed-zoom-v6.mp4"),
    )

    run(
        "-hwaccel",
        "videotoolbox",
        "-ss",
        "72",
        "-t",
        "5.005",
        "-i",
        str(PHONE / "PXL_20240613_162352481.mp4"),
        "-vf",
        f"fps={FPS},format=nv12",
        "-an",
        *HARDWARE_VIDEO,
        str(OUT / "13-chair-already-seated-v6.mp4"),
    )

    run(
        "-hwaccel",
        "videotoolbox",
        "-t",
        "14.014",
        "-i",
        str(PHONE / "PXL_20240614_062437598.mp4"),
        "-vf",
        f"fps={FPS},eq=contrast=1.04:saturation=1.05,format=nv12",
        "-an",
        *HARDWARE_VIDEO,
        str(OUT / "14-bird-natural-speed-v6.mp4"),
    )

    run(
        "-hwaccel",
        "videotoolbox",
        "-ss",
        "2",
        "-t",
        "2.5",
        "-i",
        str(PHONE / "PXL_20240615_064849842.mp4"),
        "-filter_complex",
        (
            "[0:v]crop=trunc(iw*0.58/2)*2:trunc(ih*0.58/2)*2:"
            "(iw-ow)/2:(ih-oh)/2,"
            "scale=3840:2160:force_original_aspect_ratio=increase:flags=lanczos,"
            "crop=3840:2160:(iw-ow)/2:(ih-oh)/2,setsar=1,"
            "setpts=2.4*(PTS-STARTPTS),fps=30000/1001,"
            "eq=contrast=1.06:saturation=1.04,format=nv12[v];"
            "[0:a]atempo=0.5,atempo=0.833333,aresample=48000,"
            "apad=whole_dur=6.006,atrim=duration=6.006,"
            "asetpts=PTS-STARTPTS[a]"
        ),
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-t",
        "6.006",
        *HARDWARE_VIDEO,
        "-c:a",
        "aac",
        "-b:a",
        "256k",
        str(OUT / "20-ram-slow-aligned-v6.mp4"),
    )

    run(
        "-hwaccel",
        "videotoolbox",
        "-ss",
        "1",
        "-t",
        "2",
        "-i",
        str(PHONE / "PXL_20240616_060029942.mp4"),
        "-hwaccel",
        "videotoolbox",
        "-ss",
        "3",
        "-t",
        "1",
        "-i",
        str(PHONE / "PXL_20240616_060029942.mp4"),
        "-filter_complex",
        (
            "[0:v]scale=3840:2160:force_original_aspect_ratio=decrease,"
            "pad=3840:2160:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            "fps=30000/1001,format=nv12[a];"
            "[1:v]crop=trunc(iw*0.65/2)*2:trunc(ih*0.65/2)*2:"
            "(iw-ow)/2:(ih-oh)/2,"
            "scale=3840:2160:force_original_aspect_ratio=increase:flags=lanczos,"
            "crop=3840:2160:(iw-ow)/2:(ih-oh)/2,setsar=1,"
            "setpts=2*(PTS-STARTPTS),"
            "fps=30000/1001,eq=contrast=1.06:saturation=1.04,"
            "format=nv12[b];[a][b]concat=n=2:v=1:a=0[v]"
        ),
        "-map",
        "[v]",
        "-t",
        "4.004",
        "-an",
        *HARDWARE_VIDEO,
        str(OUT / "22-deer-late-slowdown-v6.mp4"),
    )

    run(
        "-i",
        str(V2 / "27-horse-natural-neigh-v2.mov"),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "copy",
        "-af",
        "volume=1.40,acompressor=threshold=0.12:ratio=2.5:attack=8:release=120",
        "-c:a",
        "aac",
        "-b:a",
        "256k",
        "-movflags",
        "+faststart",
        str(OUT / "27-horse-neigh-boost-v6.mov"),
    )

    cow_zoom = (
        "setpts=(PTS-STARTPTS)/2.6666667,fps=30000/1001,"
        "zoompan="
        "z='if(lte(on,30),1.11-0.11*on/30,1)':"
        "x='max(0,min(iw-iw/zoom,iw*0.55-iw/(2*zoom)))':"
        "y='max(0,min(ih-ih/zoom,ih*0.52-ih/(2*zoom)))':"
        "d=1:s=3840x2160:fps=30000/1001,"
        "eq=contrast=1.05:saturation=1.04,format=nv12"
    )
    run(
        "-hwaccel",
        "videotoolbox",
        "-t",
        "16",
        "-i",
        str(PHONE / "PXL_20240618_131816951.mp4"),
        "-filter_complex",
        (
            f"[0:v]{cow_zoom}[v];"
            "[0:a]atrim=0:6,asetpts=PTS-STARTPTS,volume=1.55,"
            "acompressor=threshold=0.10:ratio=3:attack=5:release=100,"
            "aresample=48000[a]"
        ),
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-t",
        "6.006",
        *HARDWARE_VIDEO,
        "-c:a",
        "aac",
        "-b:a",
        "256k",
        str(OUT / "29-cow-zoom-out-dialogue-v6.mp4"),
    )

    run(
        "-hwaccel",
        "videotoolbox",
        "-ss",
        "3",
        "-t",
        "7.007",
        "-i",
        str(DRONE / "DJI_20240702131315_0058_D.MP4"),
        "-vf",
        "eq=brightness=0.012:contrast=1.035:saturation=1.02,format=nv12",
        "-an",
        *HARDWARE_VIDEO,
        str(OUT / "36-person-cloud-pullback-trimmed-v6.mp4"),
    )

    fixed_drone = (
        (
            "38-drone-c52-v6.mp4",
            "DJI_20240702155455_0069_D.MP4",
            6.0,
            5.0,
            6.239566,
        ),
        (
            "46-drone-c74-v6.mp4",
            "DJI_20240714152543_0104_D.MP4",
            0.0,
            3.0,
            5.005,
        ),
    )
    for output_name, source_name, source_start, source_duration, target_duration in fixed_drone:
        playback_rate = source_duration / target_duration
        run(
            "-hwaccel",
            "videotoolbox",
            "-ss",
            f"{source_start:.6f}",
            "-t",
            f"{source_duration:.6f}",
            "-i",
            str(DRONE / source_name),
            "-vf",
            (
                f"setpts=(PTS-STARTPTS)/{playback_rate:.9f},"
                f"fps={FPS},format=nv12"
            ),
            "-t",
            f"{target_duration:.6f}",
            "-an",
            *HARDWARE_VIDEO,
            str(OUT / output_name),
        )

    train = PHONE / "PXL_20240612_092451722.mp4"
    opening = V5 / "Pyrenees-ocean-to-train-opening-v5.wav"
    run(
        "-i",
        str(opening),
        "-i",
        str(train),
        "-filter_complex",
        (
            "[0:a]atrim=0:1,asetpts=PTS-STARTPTS,"
            "afade=t=out:st=0.70:d=0.30[ocean];"
            "anullsrc=r=48000:cl=stereo:d=3.170833[silence];"
            "[1:a]atrim=0:6.006,asetpts=PTS-STARTPTS,"
            "afade=t=in:st=0:d=0.20[train];"
            "[ocean][silence][train]concat=n=3:v=0:a=1,"
            "aresample=48000[a]"
        ),
        "-map",
        "[a]",
        "-t",
        "10.176839",
        "-c:a",
        "pcm_s24le",
        str(OUT / "Pyrenees-opening-ocean-title-train-v6.wav"),
    )


if __name__ == "__main__":
    build()
