# 掂量帽 / Sorting Hat —— 交付仓库

三层分工：`hw/`（硬件）、`fw/`（下位机 ESP32-S3）、`host/`（上位机 Python）。

## 快速开始（只跑上位机）
```bash
cd host
pip install -r requirements.txt
python tasks.py test         # 单测（15 passed）
python tasks.py up           # device :8443 / admin :8080
# 另开一个终端
python tasks.py preheat      # 六步预热，必须 ok:true
python tasks.py smoke        # 端到端冒烟，看到 result + audio frames
```
> Windows 上没有 `make`：用 `python tasks.py`；macOS/Linux 可用 `make`。

## 约定
- 线协议 `snake_case`，`type` 作信封键；`stt` / `abort` 对齐 xiaozhi。
- 判决 `house = argmax(scores)` + 连续 3 次同院 ×0.85 + 引原话校验（编辑距离 ≤2）。
- 宣布句只许预录（`host/assets/preroll/*.opus`）。
- 8 个时间戳：`t_arm/t0/t1/t2/t3/t4/t5a/t5b`；`TTFC = t5b − t0`。
