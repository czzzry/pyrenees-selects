#!/usr/bin/env python3
"""Build the v11 Pyrenees audio correction and conservative visual refinements."""

from __future__ import annotations

import subprocess
from pathlib import Path


FFMPEG = Path("/usr/local/bin/ffmpeg")
PHONE = Path(
    "/Users/cezarybaraniecki/Documents/AI project/AI Video Editor/"
    "raw_footage/phone_pyrenees_2024"
)
OUT = Path(
    "/Users/cezarybaraniecki/Library/Application Support/"
    "Pyrenees Selects/revisions_v11"
)
MUSIC = Path(
    "/Users/cezarybaraniecki/Desktop/"
    "Bonobo Cirrus [Extended Video] - Tuntex Aussco (128k).mp3"
)
FPS = "30000/1001"
PICTURE_SECONDS = 10242 * 1001 / 30000
AUDIO_SECONDS = PICTURE_SECONDS + (1001 / 30000) / 2
MUSIC_OFFSET = 350.720 - PICTURE_SECONDS
VIDEO_CODEC = [
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


def run(*arguments: str) -> None:
    subprocess.run(
        [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", *arguments],
        check=True,
    )


def duck(start: float, end: float, depth: float, ramp: float = 0.28) -> str:
    before = start - ramp
    after = end + ramp
    return (
        f"if(lt(t,{before:.6f}),1,"
        f"if(lt(t,{start:.6f}),1-(1-{depth:.4f})*(t-{before:.6f})/{ramp:.6f},"
        f"if(lt(t,{end:.6f}),{depth:.4f},"
        f"if(lt(t,{after:.6f}),{depth:.4f}+(1-{depth:.4f})"
        f"*(t-{end:.6f})/{ramp:.6f},1))))"
    )


def build_music() -> None:
    # The original is about -12 LUFS. A 0.50 base multiplier places the normal
    # music near -18 LUFS, with short dialogue dips around -29 to -30 LUFS.
    opening = (
        "if(lt(t,5.45),0.18,"
        "if(lt(t,6.35),0.18+0.82*(t-5.45)/0.90,1))"
    )
    dips = (
        # 07-phone: brief spoken fragment at the head; only a modest dip.
        duck(26.026, 28.126, 0.48),
        # "It is cold" occupies the final 2.75 s of this five-second clip.
        duck(105.353, 108.108, 0.28),
        # Ram comment / call.
        duck(116.116, 121.900, 0.28),
        # Horse greeting, then neigh; restore music between and immediately after.
        duck(165.165, 166.115, 0.28, 0.20),
        duck(167.615, 169.415, 0.28, 0.20),
        # Feature only "cow traffic jam", not the remaining background recording.
        duck(180.380, 182.480, 0.28),
    )
    multiplier = "*".join((opening, *dips))
    fade_start = PICTURE_SECONDS - 3.5
    run(
        "-ss",
        f"{MUSIC_OFFSET:.9f}",
        "-i",
        str(MUSIC),
        "-af",
        (
            f"atrim=duration={PICTURE_SECONDS:.9f},"
            "asetpts=PTS-STARTPTS,"
            f"volume='0.50*({multiplier})':eval=frame,"
            f"afade=t=out:st={fade_start:.9f}:d=3.5,"
            f"apad=whole_dur={AUDIO_SECONDS:.9f},"
            "aresample=48000"
        ),
        "-t",
        f"{AUDIO_SECONDS:.9f}",
        "-c:a",
        "pcm_s24le",
        str(OUT / "Pyrenees-Cirrus-dialogue-aware-v11c.wav"),
    )


def portrait_fill(
    output: str,
    source: str,
    start: float,
    source_duration: float,
    target_duration: float,
) -> None:
    rate = source_duration / target_duration
    run(
        "-ss",
        f"{start:.6f}",
        "-t",
        f"{source_duration:.6f}",
        "-i",
        str(PHONE / source),
        "-filter_complex",
        (
            "[0:v]split=2[background][foreground];"
            "[background]"
            "scale=3840:2160:force_original_aspect_ratio=increase:flags=lanczos,"
            "crop=3840:2160:(iw-ow)/2:(ih-oh)/2,"
            "boxblur=luma_radius=45:luma_power=2,"
            "eq=brightness=-0.15:saturation=0.72[background_ready];"
            "[foreground]"
            "scale=3840:2160:force_original_aspect_ratio=decrease:flags=lanczos,"
            "setsar=1[foreground_ready];"
            "[background_ready][foreground_ready]"
            "overlay=(W-w)/2:(H-h)/2,"
            f"setpts=(PTS-STARTPTS)/{rate:.9f},"
            f"fps={FPS},format=nv12[video]"
        ),
        "-map",
        "[video]",
        "-an",
        "-t",
        f"{target_duration:.6f}",
        *VIDEO_CODEC,
        str(OUT / output),
    )


def build_morning() -> None:
    # A stronger but still believable dawn grade: warmer highlights/midtones,
    # restrained blue reduction, and slightly richer saturation/contrast.
    run(
        "-ss",
        "4",
        "-t",
        "8",
        "-i",
        str(PHONE / "PXL_20240615_052909649.mp4"),
        "-vf",
        (
            f"fps={FPS},"
            "scale=3840:2160:force_original_aspect_ratio=decrease:flags=lanczos,"
            "pad=3840:2160:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,"
            "eq=contrast=1.065:saturation=1.20:brightness=0.010:gamma=1.020,"
            "colorchannelmixer=rr=1.055:gg=1.010:bb=0.945,"
            "format=nv12"
        ),
        "-an",
        "-t",
        "8.008",
        *VIDEO_CODEC,
        str(OUT / "C111-morning-warmer-rosier-v11.mp4"),
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    build_music()
    portrait_fill(
        "C105-flower-soft-fill-v11.mp4",
        "PXL_20240614_152820904.mp4",
        4.0,
        8.0,
        8.008,
    )
    portrait_fill(
        "C115-bridge-soft-fill-v11.mp4",
        "PXL_20240615_101435912.mp4",
        8.0,
        8.0,
        8.008,
    )
    build_morning()


if __name__ == "__main__":
    main()
