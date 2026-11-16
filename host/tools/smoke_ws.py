"""End-to-end smoke: connect WS, send text + PCM, expect result. No device needed."""
import asyncio, json, math, struct, sys, time
import websockets

TOKEN = "dev-token"
URL = "ws://127.0.0.1:8443/v1/voice"
TEXT = "我在乎身边的人，他们需要我的时候我不会缺席。"


async def main() -> int:
    t0 = time.monotonic()
    async with websockets.connect(URL, subprotocols=["sortinghat.voice.v1"],
                                  additional_headers={"Authorization": f"Bearer {TOKEN}"}) as ws:
        print("connected in %.0f ms" % ((time.monotonic() - t0) * 1000))
        ready = json.loads(await ws.recv())
        print("ready:", ready["sid"], ready["audio"])
        await ws.send(json.dumps({"type": "listen", "state": "start"}))
        await ws.send(json.dumps({"type": "text", "text": TEXT}))
        pcm = b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 300 * i / 16000)))
                       for i in range(960))
        await ws.send(b"\x04" + (0).to_bytes(4, "big") + pcm)
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
                print("tts start %.0f ms text=%r" % ((time.monotonic() - t1) * 1000, d.get("text")))
            elif d["type"] == "result":
                result = d
                print("result:", d["house"], d["reasons"], "host_ms=", d["latency"]["host_ms"],
                      "scores=", d.get("scores"), "announce=", d.get("announce"))
                break
        await ws.send(json.dumps({"type": "bye", "reason": "done",
                                  "dev_ts": {"t_arm": 1, "t0": 2, "t5a": 3, "t5b": 4}}))
        print("audio frames:", frames)
        return 0 if result and frames > 0 and result["house"] == "loyalty" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
