#!/usr/bin/env bash
# claude-workflow 한 줄 설치 (맥·리눅스)
#   curl -fsSL https://raw.githubusercontent.com/hyun3110/claude-workflow/main/install/get.sh | bash
# 빠진 준비물(Claude Code CLI·Git·Python)을 먼저 설치하고, 홈 폴더에 저장소를 받아(이미 있으면 git pull)
# install.sh 를 이어서 돌린다. 여러 번 붙여 넣어도 안전하다.
set -eu
repo="https://github.com/hyun3110/claude-workflow.git"
dir="${CLAUDE_WORKFLOW_DIR:-$HOME/claude-workflow}"
has() { command -v "$1" >/dev/null 2>&1; }
py_ok() { has python3 && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; }

# 1) 준비물 — 빠진 것만 설치
if ! has claude; then
  echo "설치 중: Claude Code CLI"
  curl -fsSL https://claude.ai/install.sh | bash || true
  export PATH="$HOME/.local/bin:$PATH"  # 공식 설치 위치 — 이 창에서 바로 보이게
fi
if ! has git || ! py_ok; then
  if [ "$(uname)" = Darwin ]; then
    # 맥: Git 과 python3 은 Command Line Tools 에 같이 들어 있다 — 시스템 설치 창이 뜬다
    if ! xcode-select -p >/dev/null 2>&1; then
      xcode-select --install >/dev/null 2>&1 || true
      echo "↑ 화면에 뜬 설치 창에서 '설치'를 누르세요. 끝나면 같은 한 줄을 다시 붙여 넣으세요."
      exit 1
    fi
    if ! py_ok && has brew; then brew install python; fi
  fi
fi
miss=""
has claude || miss="$miss\n  - Claude Code CLI: https://code.claude.com/docs/en/setup"
has git    || miss="$miss\n  - Git (리눅스: sudo apt install git)"
py_ok      || miss="$miss\n  - Python 3.9+ (맥: brew install python / 리눅스: sudo apt install python3)"
if [ -n "$miss" ]; then
  printf "자동으로 설치하지 못한 것이 있습니다. 직접 설치한 뒤 같은 한 줄을 다시 붙여 넣으세요:%b\n" "$miss"
  exit 1
fi

# 2) 저장소 받기 — 이미 있으면 업데이트
if [ -d "$dir/.git" ]; then
  echo "업데이트: $dir"
  git -C "$dir" pull --ff-only -q
elif [ -e "$dir" ]; then
  echo "✗ $dir 가 이미 있는데 git 저장소가 아닙니다. 옮기거나 CLAUDE_WORKFLOW_DIR 로 다른 위치를 지정하세요."
  exit 1
else
  git clone -q "$repo" "$dir"
fi

# 3) 설치
bash "$dir/install/install.sh"
echo
echo "설치 폴더: $dir  — 지우거나 옮기지 마세요 (플러그인이 이 폴더를 직접 읽습니다)."
echo "다음: Claude Code(또는 데스크톱 앱)를 켜서 — 처음이면 로그인 — \"스킬 확인해\" 라고 말하세요."
