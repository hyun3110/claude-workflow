#!/usr/bin/env python3
"""
PreToolUse(Bash) 훅 — 비가역·위험 명령 차단
등록: workflow 플러그인 hooks/hooks.json > PreToolUse, matcher "Bash"
동작: 위험 패턴 매칭 시 exit 2 (실행 차단) + stderr에 사유 출력. 통과는 exit 0.
시험: 같은 폴더의 test_guard.py
"""
import json
import re
import sys

sys.stderr.reconfigure(encoding="utf-8")  # 윈도우 기본(cp949)으로 내보내면 클로드 쪽에서 한글이 깨진다

try:
    payload = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)

if payload.get("tool_name") != "Bash":
    sys.exit(0)

cmd = str(payload.get("tool_input", {}).get("command", ""))
if not cmd:
    sys.exit(0)

# 따옴표·백슬래시를 공백으로 — `bash -c "rm -rf x"`, `\rm -rf x` 도 잡는다.
# shortcut: 인자 안의 문자열(`echo "rm -rf"`, 커밋 메시지)도 차단되는 보수적 오탐. 셸 파서가 필요해지면 shlex 로 교체
normalized = re.sub(r"\s+", " ", re.sub(r"[\"'\\]", " ", cmd))

# 명령 경계: 줄 시작·공백·; & | ( ) 또는 $( 뒤. 선택적 경로 접두(/bin/rm 등) 허용
B = r"(?:^|[\s;&|()]|\$\()(?:\S*/)?"

RULES = [
    (B + r"(npm|yarn|pnpm)\s+uninstall\b",     "npm/yarn/pnpm uninstall 차단: 의존성 제거는 사용자 확인 필요"),
    (B + r"pip3?\s+uninstall\b",               "pip uninstall 차단: 의존성 제거는 사용자 확인 필요"),
    (B + r"shutdown\b",                        "shutdown 차단: 시스템 종료 명령은 사용자가 직접 실행"),
    (B + r"(reboot|poweroff|halt)\b",          "시스템 종료/재시작 차단: 사용자가 직접 실행"),
    (B + r"mkfs\b",                            "mkfs 차단: 파일시스템 포맷은 사용자가 직접 실행"),
    (B + r"dd\s+.*of=/dev/",                   "dd → /dev/* 차단: 디바이스 덮어쓰기는 사용자가 직접 실행"),
    (B + r"chmod\s+(-[a-zA-Z]+\s+)*777\b",     "chmod 777 차단: 과도한 권한 부여는 확인 필요"),
]

# 조각(; && || | & 로 나눈 단위) 안에서 명령 이름 뒤 나머지를 검사하는 규칙.
# shortcut: 따옴표·이스케이프를 해석하지 않는다(echo git push --force 도 차단되는 보수적 오탐). 오탐이 잦아지면 shlex 도입.
GIT = B + r"git(?:\s+(?:-[Cc]\s+\S+|--(?:git-dir|work-tree|namespace|super-prefix|config-env)(?:=\S+|\s+\S+)|-{1,2}[\w-]+(?:=\S+)?))*\s+"
RECURSIVE = r"\s(-[A-Za-z]*[rR]|--recursive\b)"
FORCE = r"\s(-[A-Za-z]*f|--force\b)"

SEG_RULES = [
    (B + r"rm(?=\s|$)",
     lambda r: re.search(RECURSIVE, r) and re.search(FORCE, r),
     "rm -rf 차단: 재귀·강제 삭제는 사용자 확인 필요"),
    (GIT + r"push\b",
     lambda r: re.search(r"\s(-[A-Za-z]*f\b|--force|\+\S)", r),  # --force-with-lease·+refspec 도 원격 덮어쓰기
     "git push --force 차단: 원격 히스토리 덮어쓰기는 사용자 확인 필요"),
    (GIT + r"reset\b",
     lambda r: re.search(r"\s--hard\b", r),
     "git reset --hard 차단: 작업물 손실 가능, 사용자 확인 필요"),
    (GIT + r"clean\b",
     lambda r: re.search(FORCE, r),
     "git clean -f 차단: 추적되지 않은 파일 손실 가능"),
    (GIT + r"branch\b",
     lambda r: re.search(r"\s-[A-Za-z]*D\b", r) or (re.search(r"\s(-[A-Za-z]*d|--delete\b)", r) and re.search(FORCE, r)),
     "git branch -D 차단: 머지 안 된 브랜치 강제 삭제는 확인 필요"),
]


def block(reason):
    shown = cmd if len(cmd) <= 200 else cmd[:200] + "…(생략)"  # 토큰·URL 이 길게 새지 않게
    print(f"[guard-dangerous-bash] {reason}", file=sys.stderr)
    print(f"[guard-dangerous-bash] 차단된 명령: {shown}", file=sys.stderr)
    print("[guard-dangerous-bash] 사용자에게 확인을 받고 직접 실행하세요.", file=sys.stderr)
    sys.exit(2)


for pattern, reason in RULES:
    if re.search(pattern, normalized):
        block(reason)

for seg in re.split(r"&&|\|\||[;|&]", normalized):
    for pattern, check, reason in SEG_RULES:
        for m in re.finditer(pattern, seg):
            if check(seg[m.end():]):
                block(reason)

sys.exit(0)
