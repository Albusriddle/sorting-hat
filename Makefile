.PHONY: up test ready preheat replay smoke tree clean
PY ?= python

up:
	cd host && $(PY) -m app.run

test:
	cd host && $(PY) -m pytest -q

ready:
	curl -s localhost:8080/readyz

preheat:
	curl -s -X POST localhost:8080/v1/preheat -H "X-Admin-Token: $${ADMIN_TOKEN:-dev-token}"

replay:
	curl -s -X POST localhost:8080/v1/replay -H "X-Admin-Token: $${ADMIN_TOKEN:-dev-token}" \
	  -H "Content-Type: application/json" -d '{"text":"我想赢，我要第一"}'

smoke:
	cd host && $(PY) tools/smoke_ws.py

tree:
	$(PY) tools/check_tree.py

clean:
	rm -rf host/var host/.pytest_cache
