#!/usr/bin/env bash
# claude-workflow 한 줄 설치 (맥·리눅스)
#   curl -fsSL https://raw.githubusercontent.com/hyun3110/claude-workflow/main/install/get.sh | bash
# 홈 폴더에 저장소를 받고(이미 있으면 git pull) install.sh 를 이어서 돌린다.
set -eu
repo="https://github.com/hyun3110/claude-workflow.git"
dir="${CLAUDE_WORKFLOW_DIR:-$HOME/claude-workflow}"

miss=0
hint() { echo "  - $1"; miss=1; }
command -v claude  >/dev/null 2>&1 || hint "Claude Code CLI: https://code.claude.com/docs/en/setup 의 설치 명령 (설치 후 claude 를 한 번 실행해 로그인)"
command -v git     >/dev/null 2>&1 || hint "Git: 맥은 xcode-select --install"
command -v python3 >/dev/null 2>&1 || hint "Python 3.10+: 맥은 brew install python"
if [ "$miss" = 1 ]; then
  echo "↑ 먼저 설치한 뒤, 터미널을 새로 열고 같은 한 줄을 다시 붙여 넣으세요."
  exit 1
fi

if [ -d "$dir/.git" ]; then
  echo "업데이트: $dir"
  git -C "$dir" pull --ff-only
elif [ -e "$dir" ]; then
  echo "✗ $dir 가 이미 있는데 git 저장소가 아닙니다. 옮기거나 CLAUDE_WORKFLOW_DIR 로 다른 위치를 지정하세요."
  exit 1
else
  git clone "$repo" "$dir"
fi

bash "$dir/install/install.sh"
echo
echo "설치 폴더: $dir  — 지우거나 옮기지 마세요 (플러그인이 이 폴더를 직접 읽습니다)."
