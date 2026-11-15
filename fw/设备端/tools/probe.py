# probe.py —— 扮演设备，手敲协议（今晚版）
import asyncio, json, websockets

URL = "ws://127.0.0.1:8443/v1/voice"
TOKEN = "dev-token"

def frame_pcm04(seq: int, pcm: bytes) -> bytes:
    return b"\x04" + seq.to_bytes(4, "big") + pcm

async def main():
    async with websockets.connect(
        URL,
        subprotocols=["sortinghat.voice.v1"],
        additional_headers={"Authorization": f"Bearer {TOKEN}"},
    ) as ws:
        # 1) 连上就收 ready
        ready = json.loads(await ws.recv())
        print("[READY]", json.dumps(ready, ensure_ascii=False))

        # 2) 发 listen start
        await ws.send(json.dumps({"type": "listen", "state": "start"}))
        print("[TX] listen start")

        # 3) 发 500 ms 假音频（0x04 + seq + PCM）
        for seq in range(25):                     # 25 × 20 ms = 500 ms
            await ws.send(frame_pcm04(seq, b"\x00\x00" * 320))
            await asyncio.sleep(0.02)
        print("[TX] 25 个 0x04 帧")

        # 4) 说完了
        await ws.send(json.dumps({"type": "vad", "ev": "speech_end"}))
        print("[TX] vad speech_end")

        # 5) 收下行
        bins = 0
        house = None
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=15)
            if isinstance(msg, bytes):
                bins += 1
                if bins <= 3:
                    print(f"[RX] BIN kind=0x{msg[0]:02X} seq={int.from_bytes(msg[1:5],'big')} "
                          f"payload={len(msg)-5}B")
                continue
            d = json.loads(msg)
            print("[RX]", json.dumps(d, ensure_ascii=False)[:220])
            if d["type"] == "result":
                house = d["house"]
                break

        print("\n===== 结论 =====")
        print("收到二进制帧数:", bins)
        print("判出学院:", house)
        print("学院映射:", {"courage": "赤翎", "ambition": "玄渊",
                            "wisdom": "星枢", "loyalty": "穗垣"}.get(house, "未知"))

asyncio.run(main())