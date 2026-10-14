#!/usr/bin/env python3
"""
PreToolUse(EnterPlanMode) 훅 — 플랜 가독성 가이드 주입
계획 작성 시 "거절한 대안·수정 이력 제외, 한 스텝 한 동작, 파일 경로 앵커, 간결한 동작 위주"를 강제.
등록: settings.json > hooks > PreToolUse, matcher "EnterPlanMode"
"""
import json
import sys

# stdin 소비 (훅 프로토콜 요구, 내용은 미사용)
try:
    json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    pass

guidance = (
    "Plan readability guidance: "
    "Keep the problem statement - omit decision history "
    "(rejected approaches, revision rationale, prior iterations). "
    "On plan revisions, rewrite the entire plan clean - "
    "do not append revision notes or annotate what changed. "
    "Use one action per step with file paths as anchors (e.g., src/auth.ts:42). "
    "Favor terse action steps over explanatory prose."
)

output = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": guidance
    }
}

print(json.dumps(output))
sys.exit(0)
