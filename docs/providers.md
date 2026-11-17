# Provider 切换手册（mock ↔ AWS）

三个 adapter 共用同一契约（`host/app/providers.py`），换供应商只改 `.env` 一行。

| 环节 | mock（默认） | AWS（已实现） | 现状 |
|---|---|---|---|
| ASR | `MockASR`（直接返回设备 `text`） | `TranscribeASR`（`start_stream_transcription`, zh-CN） | **text 通路为主**；Transcribe 仅在设备能上传真 PCM 时使用 |
| LLM | `MockLLM`（关键词→证据+分数） | `BedrockLLM`（`converse` + JSON 解析/校验/refuse） | 代码就绪，需凭证 |
| TTS | `MockTTS`（220 Hz 正弦） | `PollyTTS`（pcm 16 kHz） | 只念桥接句，**不宣布学院** |

## 1. 开启 AWS

```bash
export ASR_PROVIDER=aws LLM_PROVIDER=aws TTS_PROVIDER=aws
export AWS_REGION=ap-northeast-1
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
export BEDROCK_MODEL_ID=anthropic.claude-haiku
python tasks.py up
python tasks.py preheat      # 必须 ok:true；AWS 模式下 asr 预热会标 skipped
```

最小 IAM 策略：

```json
{"Version":"2012-10-17","Statement":[
 {"Effect":"Allow","Action":["transcribe:StartStreamTranscription"],"Resource":"*"},
 {"Effect":"Allow","Action":["bedrock:Converse","bedrock:InvokeModel"],"Resource":"*"},
 {"Effect":"Allow","Action":["polly:SynthesizeSpeech"],"Resource":"*"}]}
```

## 2. 三条硬规则

1. **宣布学院用设备本地 TTS 念院名**；host 的 Polly 只念桥接句（中文只有 `Zhiyu` 女声，会把"帽子是谁"换掉）。
2. **`house` 不由模型输出**：Bedrock 只返回 `evidence/scores/line`，`house = argmax` 由 `judge.py` 计算；`refuse` 会原样透传，不判院。
3. **结构化输出要预热**：Bedrock 新 schema 首编译最长 ~90 s，客户端读超时设 **150 s**。

## 3. ASR 的现状（重要）

设备端没有连续采音硬件，上行 `0x04` 是全零帧。因此：
- 演示路径 = 设备把"词条编号 → 预置台词"以 `{"type":"text"}` 发给 host；host 不再调 ASR。
- `TranscribeASR` 需要 16 kHz PCM；一旦补上 INMP441/USB 声卡，把 `0x04` 换成真 PCM 即可，代码不用改。
- 无 `text` 且无 PCM 时，引擎回"没听清"，不判院。

## 4. 测试

```bash
python -m pytest -q            # 48 passed
python tasks.py up &
python tasks.py preheat
python tasks.py smoke          # result 应带 scores / announce
```
