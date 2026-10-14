#!/usr/bin/env bash
# claude-workflow 설치 (맥·리눅스)
# 사용: 저장소 폴더에서  bash install/install.sh
# 실제 설치는 install.py 가 한다. 여기서는 선행 조건만 본다.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
for t in git claude python3; do
  command -v "$t" >/dev/null 2>&1 || { echo "✗ '$t' 가 없습니다 — README 의 선행 조건을 먼저 설치하세요."; exit 1; }
done
exec python3 "$here/install.py"
