"""End-to-end smoke: connect WS, speak, expect tts + result. No device needed."""
import asyncio, json, math, struct, sys, time
import websockets

sys.path.insert(0, ".")
from app import opus_codec  # noqa: E402

TOKEN = "dev-token"
URL = "ws://127.0.0.1:8443/v1/voice"


async def main() -> int:
    t0 = time.monotonic()
    async with websockets.connect(URL, subprotocols=["sortinghat.voice.v1"],
                                  additional_headers={"Authorization": f"Bearer {TOKEN}"}) as ws:
        print("connected in %.0f ms" % ((time.monotonic() - t0) * 1000))
        ready = json.loads(await ws.recv())
        print("ready:", ready["sid"], ready["audio"])
        await ws.send(json.dumps({"type": "listen", "state": "start"}))
        pcm = b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 300 * i / 16000)))
                       for i in range(960))
        frame = opus_codec.encode_pcm(pcm) or b"\x00" * 20
        await ws.send(b"\x01" + (0).to_bytes(4, "big") + frame)
        print("opus available:", opus_codec.available(), "frame bytes:", len(frame))
        await ws.send(json.dumps({"type": "vad", "ev": "speech_end"}))
        t1 = time.monotonic()
        frames, result = 0, None
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            if isinstance(msg, bytes):
                frames += 1
                continue
            d = json.loads(msg)
            if d["type"] == "tts" and d["state"] == "start":
                print("tts start %.0f ms" % ((time.monotonic() - t1) * 1000))
            elif d["type"] == "result":
                result = d
                print("result:", d["house"], d["reasons"], "host_ms=", d["latency"]["host_ms"],
                      "announce=", d.get("announce"))
                break
        print("audio frames:", frames)
        return 0 if result and frames > 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
