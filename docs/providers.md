# Provider 切换手册（mock → 真实供应商）

三个 adapter 共用同一契约（`host/app/providers.py`）：

```python
class Provider:
    async def health(self) -> bool: ...
    async def warmup(self) -> None: ...
# ASR:  async def final(text_hint) -> str
# LLM:  async def complete(text) -> {"evidence": [...], "scores": {...}, "line": "..."}
# TTS:  async def synth_async(text) -> list[bytes]   # 16 kHz / 16 bit / 60 ms PCM
```

**换供应商 = 改 `.env` 一行 + 新增一个类**，编排代码里不允许出现 `if vendor ==`。

## 1. ASR：AWS Transcribe Streaming

```python
# 伪代码（boto3，需 AWS 凭证与 ap-northeast-1）
client = boto3.client("transcribe", region_name="ap-northeast-1")
stream = await client.start_stream_transcription(
    LanguageCode="zh-CN", MediaSampleRateHertz=16000, MediaEncoding="pcm")
# 把 16k PCM 帧写进 AudioStream；PartialResults 稳定 2 帧后先喂 LLM（投机启动）
```
env：`ASR_PROVIDER=aws`、`AWS_REGION`、`AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`

## 2. LLM：Amazon Bedrock（结构化输出）

```python
client = boto3.client("bedrock-runtime", region_name="ap-northeast-1")
resp = client.converse(modelId="anthropic.claude-haiku", ...,
                       inferenceConfig={"maxTokens": 300, "temperature": 0.8})
```
- **预热要打真 schema**（新 schema 首编译最长 ~90 s；客户端读超时设 **150 s**）
- 输出只接受 `evidence` + `scores` + `line`；`house` 永远由代码 `argmax`

## 3. TTS：CosyVoice（instruction 音色）

```
wss://dashscope.aliyuncs.com/api-ws/v1/inference
```
- 音色用 instruction 描述（"七十岁、沙哑、慢、带戏谑"），**不克隆真人**
- 下行 24 kHz → 若设备只吃 16 kHz，网关重采样后再封帧
- 宣布句不用它：用 `host/assets/preroll/*.opus`（8 句预录）

## 4. 失败即降级

| provider | 超时 | 降级 |
|---|---|---|
| ASR | 600 ms | 用稳定 partial 当 final |
| LLM | 900 ms | 预合成模板首句（同音色） |
| TTS | 800 ms | 预录音色片段 |

## 5. 验收
```bash
ASR_PROVIDER=aws LLM_PROVIDER=bedrock TTS_PROVIDER=cosyvoice make up
make preheat && make smoke      # 必须仍看到 result 与 audio frames
```
