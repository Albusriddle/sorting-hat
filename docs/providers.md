# Provider 切换手册（mock ↔ AWS）

三个 adapter 共用同一契约（`host/app/providers.py`），换供应商只改 `.env` 一行。

| 环节 | mock（默认） | AWS（已实现） | 状态 |
|---|---|---|---|
| ASR | `MockASR`（按传入文本） | `TranscribeASR`（`start_stream_transcription`, zh-CN） | 代码就绪，**需先接 Opus→PCM 解码** |
| LLM | `MockLLM`（关键词打分） | `BedrockLLM`（`converse` + JSON 解析/校验） | 代码就绪，需凭证 |
| TTS | `MockTTS`（220 Hz 正弦，验证链路） | `PollyTTS`（`synthesize_speech` pcm 16 kHz） | 代码就绪，**只做过桥句，不宣布学院** |

## 1. 开启 AWS

```bash
export ASR_PROVIDER=aws LLM_PROVIDER=aws TTS_PROVIDER=aws
export AWS_REGION=ap-northeast-1
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
export BEDROCK_MODEL_ID=anthropic.claude-haiku
python -m app.run
python tasks.py preheat      # 必须 ok:true，providers 步骤逐个报 health
```

最小 IAM 策略：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect": "Allow", "Action": ["transcribe:StartStreamTranscription"], "Resource": "*"},
    {"Effect": "Allow", "Action": ["bedrock:Converse", "bedrock:InvokeModel"], "Resource": "*"},
    {"Effect": "Allow", "Action": ["polly:SynthesizeSpeech"], "Resource": "*"}
  ]
}
```

## 2. 三条硬规则

1. **宣布学院用预录**（`host/assets/preroll/{house}-{1..3}.opus`），`PollyTTS` 永远不朗读宣布句——它的中文只有 `Zhiyu` 女声，会把"帽子是谁"换掉。
2. **`house` 不由模型输出**：Bedrock 只返回 `evidence/scores/line`，`house = argmax` 由 `app/judge.py` 计算。
3. **结构化输出要预热**：Bedrock 新 schema 首编译最长 ~90 s，客户端读超时设 **150 s**；`preheat` 打真 schema，不要打样例。

## 3. ASR 的已知缺口

`TranscribeASR.final(text_hint, pcm=...)` 需要 16 kHz/16 bit PCM；当前网关**只统计 Opus 帧、不解码**，所以 `pcm=None` 会抛 `AsrUnavailable` → 引擎标记 `asr_unavailable` 并降级为提示句。

补齐方式（二选一）：
- 网关装 `opuslib`（需系统 libopus），把 `0x01` 帧解成 PCM 再调 `final(pcm=...)`；
- 或设备侧同时上传一路 16 kHz PCM 仅供 ASR（带宽 ×4，但零解码）。

## 4. 测试

```bash
python -m pytest -q            # 21 passed（含 parse/validate/chunk/factory）
python tasks.py up &           # mock 模式
python tasks.py preheat
python tasks.py smoke          # result 里应带 announce.variant
```
