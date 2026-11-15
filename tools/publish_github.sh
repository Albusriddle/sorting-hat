#!/usr/bin/env bash
# Publish this repo to a PRIVATE GitHub repo, after verifying the token's account.
# Usage:  GITHUB_TOKEN_FILE=~/.dsh/github_token.txt bash tools/publish_github.sh
set -euo pipefail

TOKEN_FILE="${GITHUB_TOKEN_FILE:-$HOME/.dsh/github_token.txt}"
REPO="${REPO:-sorting-hat}"
EXPECTED="${EXPECTED_LOGIN:-Albusriddle}"
API="https://api.github.com"

[ -f "$TOKEN_FILE" ] || { echo "ERROR: token file not found: $TOKEN_FILE"; exit 1; }
TOKEN="$(tr -d ' \r\n' < "$TOKEN_FILE")"
[ -n "$TOKEN" ] || { echo "ERROR: empty token"; exit 1; }

LOGIN="$(curl -s -H "Authorization: Bearer $TOKEN" "$API/user" \
  | python -c "import json,sys; print(json.load(sys.stdin).get('login',''))" 2>/dev/null || true)"
if [ "$LOGIN" != "$EXPECTED" ]; then
  echo "ACCOUNT MISMATCH: token belongs to '${LOGIN:-<unknown>}', expected '$EXPECTED'."
  echo "Refusing to push. Nothing was uploaded."
  exit 2
fi
echo "account verified: $LOGIN"

CODE="$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOKEN" "$API/repos/$LOGIN/$REPO")"
if [ "$CODE" = "404" ]; then
  curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
    "$API/user/repos" \
    -d "{\"name\":\"$REPO\",\"private\":true,\"description\":\"Sorting Hat (掂量帽) - host MVP\",\"license_template\":\"apache-2.0\",\"auto_init\":false}" \
    | python -c "import json,sys; d=json.load(sys.stdin); print('created:', d.get('full_name'), d.get('html_url') or d.get('message'))"
elif [ "$CODE" = "200" ]; then
  echo "repo exists: https://github.com/$LOGIN/$REPO"
else
  echo "ERROR: cannot query repo (HTTP $CODE)"; exit 3
fi

git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/$LOGIN/$REPO.git"
git -c http.extraheader="AUTHORIZATION: bearer $TOKEN" push -u origin main
git remote set-url origin "https://github.com/$LOGIN/$REPO.git"
echo "---- done ----"
git remote -v
git log --format='%h %an <%ae> %s' -1
