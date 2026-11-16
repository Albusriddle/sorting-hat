# 上游锁定

| 项 | 值 |
|---|---|
| 上游仓库 | **无**（本项目自建 Arduino 工程，不再依赖 xiaozhi） |
| 第三方库 | ArduinoJson、arduinoWebSockets（随 Arduino 库管理器安装） |
| 赛期规则 | 不升级库、不改板子包版本；要升级先跑 `python 设备端/tools/check_build.py` 与上位机 34 条测试 |

> 11-15 设计稿曾计划用 `78/xiaozhi-esp32`；11-16 实物改为 WROOM-32D + 幻尔模块后已放弃该路线，`docs/design/` 里的相关描述属历史。
