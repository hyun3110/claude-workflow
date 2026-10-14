#!/usr/bin/env python3
"""설치 점검 — "스킬 확인해" 가 돌린다. 고치지 않는다(읽기·실행 확인만).

✓ 통과 / ✗ 실패 / △ 선택 항목 미충족(실패로 세지 않음). ✗ 가 있으면 종료코드 1.

    python3 check.py            # 기본 점검
    python3 check.py --listing  # + 새 claude 세션의 스킬 목록 대조 (1~2분 더)

설정 폴더는 Claude Code 와 같은 규칙: CLAUDE_CONFIG_DIR 이 있으면 그것, 없으면 ~/.claude.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CLAUDE = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser().resolve()
rows = []


def check(name, ok, detail="", optional=False):
    rows.append(("✓" if ok else ("△" if optional else "✗"), name, detail))


def run(cmd, stdin=None, timeout=120):
    try:
        p = subprocess.run(cmd, input=stdin, capture_output=True, timeout=timeout,
                           stdin=None if stdin is not None else subprocess.DEVNULL,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, "", str(e)


def http(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 — 꺼져 있으면 무엇이든 실패다
        return 0, str(e)


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


manifest = load_json(ROOT / "manifest.json") or {}

# 1. python3 가 진짜 파이썬인가 (플러그인 훅이 python3 로 돈다 — 윈도우 MS 스토어 스텁이면 조용히 죽는다)
rc, out, _ = run(["python3", "-c", "import sys;print(sys.version.split()[0])"])
check("python3 실행", rc == 0 and bool(out.strip()), out.strip() or "없음/스토어 스텁 — 설치 스크립트의 python3 별칭 단계")

# 2. 작업 규칙 연결
rules = CLAUDE / "workflow-rules.md"
try:
    linked = any(l.strip() == "@workflow-rules.md" for l in (CLAUDE / "CLAUDE.md").read_text(encoding="utf-8").splitlines())
except OSError:
    linked = False
check("작업 규칙 연결", rules.exists() and linked,
      "workflow-rules.md·@ 줄 있음" if rules.exists() and linked else
      " · ".join(m for m, bad in (("workflow-rules.md 없음", not rules.exists()), ("CLAUDE.md 에 @workflow-rules.md 줄 없음", not linked)) if bad))

# 3. 플러그인 설치·활성 — CLI 가 실제로 보는 상태(설치 + 켜짐). CLI 가 안 되면 설치 기록 파일로 대신 본다
want = manifest.get("plugins", [])
rc, out, _ = run([shutil.which("claude") or "claude", "plugin", "list", "--json"])
try:
    state = {p["id"]: p.get("enabled", True) for p in json.loads(out)}
    src = ""
except ValueError:
    state = {k: True for k in (load_json(CLAUDE / "plugins" / "installed_plugins.json") or {}).get("plugins", {})}
    src = " (claude CLI 실패 — 설치 기록만 봄, 켜짐 여부 미확인)"
miss = [p for p in want if p not in state]
off = [p for p in want if state.get(p) is False]
check("플러그인 설치·활성", bool(want) and not miss and not off,
      f"{len(want) - len(miss) - len(off)}/{len(want)}" + (f" 없음: {', '.join(miss)}" if miss else "")
      + (f" 꺼짐: {', '.join(off)}" if off else "") + src)

# 4. 로컬 스킬
ls = manifest.get("local_skills", {})
# github = {"owner/repo": [스킬...]}, git = {스킬: {...}} — _comment·allow_model_invocation 은 무시
names = [n for v in ls.get("github", {}).values() for n in v] + list(ls.get("git", {}))
miss = [n for n in names if not (CLAUDE / "skills" / n / "SKILL.md").exists()]
check("로컬 스킬", bool(names) and not miss, f"{len(names) - len(miss)}/{len(names)}" + (f" 없음: {', '.join(miss)}" if miss else ""))

# 5. 숨김·합침 유지 (플러그인 업데이트로 풀리는지) — 같은 파이썬·같은 환경변수
rc, out, err = run([sys.executable, str(HERE / "trim-descriptions.py"), "--check"])
counts = re.findall(r"(숨김|합침) (\d+)/(\d+)", out)
summ = " · ".join(f"{k} {a}/{b}" for k, a, b in counts)
first_bad = next((l.strip() for l in out.splitlines() if "✗" in l), "")
empty = not any(int(b) for _, _, b in counts)  # 대상 0 = 플러그인이 안 깔려 점검할 게 없다
check("숨김·합침 유지", rc == 0 and not empty,
      ("점검 대상 0 — 플러그인 미설치" if empty and rc == 0 else summ or (out or err).strip()[-120:])
      + (f" · {first_bad}" if first_bad else ""))

# 6. 위험 명령 차단 훅이 실제로 막나
guard = ROOT / "hooks" / "guard-dangerous-bash.py"
if guard.exists():
    rc, _, _ = run([sys.executable, str(guard)], stdin=b'{"tool_name":"Bash","tool_input":{"command":"rm -rf /tmp/x"}}')
    check("위험 명령 차단 훅", rc == 2, f"rm -rf → rc={rc} (2=차단)")
else:
    check("위험 명령 차단 훅", False, f"{guard.name} 없음")

# 7. 기본 모델·강도
cfg = load_json(CLAUDE / "settings.json") or {}
model, effort = cfg.get("model"), cfg.get("effortLevel")
check("기본 모델·강도", bool(model and effort), f"model={model or '-'} · effortLevel={effort or '-'}", optional=True)

# 8. (선택) codex CLI
codex = shutil.which("codex")
check("codex CLI", bool(codex), "있음" if codex else "없음 — 2패스 리뷰는 Claude 단독", optional=True)

# 9. (선택) claude-mem 워커 (Bun 필요)
port = (load_json(Path.home() / ".claude-mem" / "settings.json") or {}).get("CLAUDE_MEM_WORKER_PORT", "37777")
st, body = http(f"http://127.0.0.1:{port}/api/health")
check("claude-mem 워커", st == 200, f"port {port}" if st == 200 else "응답 없음 — Bun 설치·Claude 재시작", optional=True)

# 10. (--listing) 새 세션이 실제로 보는 스킬 목록 — 숨긴 것이 빠지고 대표가 남았나
if "--listing" in sys.argv:
    trims = load_json(HERE / "trims.json") or {}
    # 윈도우의 claude 는 npm 의 claude.CMD — 확장자 없이 부르면 subprocess 가 못 찾는다
    rc, out, _ = run([shutil.which("claude") or "claude", "-p", "--model", "haiku",
                      "Output ONLY the exact names of every skill you can invoke via the Skill tool, one per line, no commentary."],
                     timeout=300)
    seen = {l.strip().strip("`- ") for l in out.splitlines() if l.strip()}
    leaf = {s.split(":")[-1] for s in seen}
    # _hide·_merge 값은 이름 목록(list) 또는 이름을 키로 둔 dict — 둘 다 이름을 순회한다
    hid = [f"{k}:{n}" if k != "_local" else n for k, v in trims.get("_hide", {}).items() if isinstance(v, (list, dict)) for n in v]
    bases = [f"{k}:{b}" if k != "_local" else b for k, v in trims.get("_merge", {}).items() if isinstance(v, (list, dict)) for b in v]
    leak = [h for h in hid if h in seen]
    lost = [b for b in bases if b not in seen and b.split(":")[-1] not in leaf
            and not (b == "taste-skill:design-taste-frontend" and "taste-skill:taste-skill" in seen)]
    # 이 점검 스킬 자신도 목록에 있어야 "스킬 확인해" 로 불린다 (SKILL.md frontmatter 가 깨지면 조용히 빠진다)
    if "skill-check" not in leaf:
        lost.append("workflow:skill-check")
    check("새 세션 스킬 목록", rc == 0 and bool(seen) and not leak and not lost,
          f"{len(seen)}줄" + (f" · 숨김 노출 {leak}" if leak else "") + (f" · 대표 빠짐 {lost}" if lost else "")
          + (f" · claude 실행 실패 rc={rc}" if rc != 0 else ""))

w = max(len(r[1]) for r in rows)
for mark, name, detail in rows:
    print(f"{mark} {name.ljust(w)}  {detail}")
bad = sum(r[0] == "✗" for r in rows)
print(f"\n{len(rows) - bad}/{len(rows)} 통과" + (" — ✗ 항목은 README 의 문제 해결 절을 본다" if bad else ""))
sys.exit(1 if bad else 0)
