# 上位机 Runbook（90 秒上台）

1. `cd host && pip install -r requirements.txt`（首次）
2. `make up`（device 8443 / admin 8080）
3. `make preheat` → 必须 200 且 `ok:true`
4. `make ready` → 200
5. `make smoke` → 看到 `result:` 与 `audio frames > 0`
6. 设备上电 → 戴上 → 说 2 句

## 故障速查
- 设备连不上：手机热点？防火墙 8443？证书 SAN？
- 帽子不响：`/stats` 看 last.house；没有则看 WS 日志
- 延迟高：`/v1/sessions` 看 t1–t4 哪段超
