#!/usr/bin/env python3
"""
SessionStart 훅 — 세션 시작 시 현재 상태를 3~5줄로 주입
등록: workflow 플러그인 hooks/hooks.json > SessionStart, matcher "startup|resume|compact"
표시 항목: ① 마지막 일일보고 ② 최근 메모리 변경 ③ 백업 상태
경로 하드코딩 없이 $HOME 기준 + cwd 기반 메모리 자동 탐지.
"""
import glob
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")  # 윈도우 기본(cp949)으로 내보내면 한글이 깨지고 ⚠️ 는 예외가 난다

HOME = os.path.expanduser("~")
DAILY_ROOT = os.path.join(HOME, "daily-logs")          # 일일보고 폴더 (본인 컨벤션에 맞게 수정)
BACKUP_DIR = os.path.join(HOME, "claude-backups")      # 백업 저장 폴더
# Claude Code 와 같은 규칙 — CLAUDE_CONFIG_DIR 이 있으면 그쪽
PROJECTS_ROOT = os.path.join(os.path.abspath(os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude"))), "projects")

# stdin(JSON)에서 cwd 추출 — 실패 시 현재 위치로 폴백
cwd = None
try:
    payload = json.load(sys.stdin)
    cwd = payload.get("cwd") or None
except (json.JSONDecodeError, ValueError):
    pass
if not cwd:
    cwd = os.getcwd()


def format_age(mtime):
    diff = time.time() - mtime
    if diff < 3600:
        return f"{int(diff // 60)}분 전"
    if diff < 86400:
        return f"{int(diff // 3600)}시간 전"
    return f"{int(diff // 86400)}일 전"


def latest_file(pattern, exclude=None):
    files = [f for f in glob.glob(pattern, recursive=True)
             if not exclude or os.path.basename(f) != exclude]
    return max(files, key=os.path.getmtime) if files else None


lines = ["[세션 컨텍스트]"]

# 1. 마지막 일일보고
if os.path.isdir(DAILY_ROOT):
    latest = latest_file(os.path.join(DAILY_ROOT, "**", "*.md"))
    if latest:
        name = os.path.splitext(os.path.basename(latest))[0]
        lines.append(f"- 일일보고: {name} ({format_age(os.path.getmtime(latest))})")

# 2. 메모리 최근 변경 — cwd를 projects 인코딩 규칙(영숫자 외 → '-')으로 변환,
#    상위로 거슬러 올라가며 projects/<인코딩>/memory 가 있는 첫 폴더 사용.
probe = cwd
while probe:
    encoded = re.sub(r"[^A-Za-z0-9]", "-", probe)
    candidate = os.path.join(PROJECTS_ROOT, encoded, "memory")
    if os.path.isdir(candidate):
        recent = latest_file(os.path.join(candidate, "*.md"), exclude="MEMORY.md")
        if recent:
            lines.append(
                f"- 메모리 최근: {os.path.basename(recent)} "
                f"({format_age(os.path.getmtime(recent))}, {os.path.basename(probe)})"
            )
        break
    parent = os.path.dirname(probe)
    if not parent or parent == probe:
        break
    probe = parent

# 3. 백업 상태
if os.path.isdir(BACKUP_DIR):
    last = latest_file(os.path.join(BACKUP_DIR, "claude-backup-*.tar.gz"))
    if last:
        age_days = (time.time() - os.path.getmtime(last)) / 86400
        warn = " ⚠️" if age_days > 8 else ""
        lines.append(f"- 백업: {format_age(os.path.getmtime(last))}{warn}")

print("\n".join(lines))
