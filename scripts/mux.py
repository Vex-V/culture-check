"""Join a video-only and an audio-only file into one .mp4, without re-encoding.

    python scripts/mux.py VIDEO AUDIO OUT

yt-dlp needs ffmpeg to merge the separate streams YouTube serves; PyAV
(already installed for vidra) does the same remux.
"""

import sys

import av


def mux(video: str, audio: str, out: str) -> None:
    with av.open(video) as vin, av.open(audio) as ain, av.open(out, "w") as o:
        vs, as_ = vin.streams.video[0], ain.streams.audio[0]
        ov, oa = o.add_stream_from_template(vs), o.add_stream_from_template(as_)
        for packet in vin.demux(vs):
            if packet.dts is not None:
                packet.stream = ov
                o.mux(packet)
        for packet in ain.demux(as_):
            if packet.dts is not None:
                packet.stream = oa
                o.mux(packet)


if __name__ == "__main__":
    mux(*sys.argv[1:4])
