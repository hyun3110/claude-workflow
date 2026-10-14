#!/usr/bin/env python3
"""claude-workflow 설치 — 윈도우·맥·리눅스 공통. install.ps1 / install.sh 가 부른다.

여러 번 돌려도 안전하다(멱등). 받는 사람의 기존 설정은 덮어쓰지 않는다:
  - 모델·강도는 비어 있을 때만 넣는다
  - 원래 있던 로컬 스킬은 받지도, 패치하지도 않는다(이 스크립트가 설치한 것만 패치)
  - CLAUDE.md 는 `@workflow-rules.md` 한 줄만 덧붙인다
  - workflow-rules.md·worker.md 를 사용자가 고쳤으면 덮어쓰지 않고 `.new` 로 옆에 둔다
설치 기록은 <설정 폴더>/.claude-workflow.json 에 남는다.
설정 폴더는 Claude Code 와 같은 규칙 — CLAUDE_CONFIG_DIR 이 있으면 그쪽, 없으면 ~/.claude.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.version_info < (3, 9):
    sys.exit(f"✗ Python 3.9 이상이 필요하다 (지금 {sys.version.split()[0]}).")
sys.stdout.reconfigure(encoding="utf-8")  # 윈도우 콘솔(cp949)에서 한글이 깨지지 않게

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "workflow"
CFG = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser().resolve()
MAN = json.loads((PLUGIN / "manifest.json").read_text(encoding="utf-8"))
STATE_PATH = CFG / ".claude-workflow.json"
OFFICIAL = ("claude-plugins-official", "anthropics/claude-plugins-official")
DMI = "disable-model-invocation: true"
# git·claude 가 로그인 창을 띄우고 멈추지 않게 — 실패는 실패로 돌려받는다
ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
failed = []


def say(msg):
    print(msg, flush=True)


def run(cmd, timeout=600):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              stdin=subprocess.DEVNULL, timeout=timeout, env=ENV)
    except (OSError, subprocess.TimeoutExpired) as e:
        return subprocess.CompletedProcess(cmd, -1, "", f"{type(e).__name__}: {e}")


def claude(*args):
    # 윈도우의 claude 는 npm 의 claude.CMD — 확장자 없이 부르면 subprocess 가 못 찾는다
    return run([shutil.which("claude") or "claude", "plugin", *args])


def claude_json(*args):
    r = claude(*args, "--json")
    try:
        return json.loads(r.stdout)
    except ValueError:
        raise RuntimeError(f"`claude plugin {' '.join(args)} --json` 실패: {(r.stderr or r.stdout).strip()[-200:]}")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def load_state():
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_json(path, data):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)  # 쓰다가 끊겨도 원본이 반쯤 깨지지 않게


def source_arg(src):
    return {"github": lambda s: s["repo"], "git": lambda s: s["url"],
            "directory": lambda s: s["path"]}[src["source"]](src)


def plugins_step(state):
    say("[1/5] 플러그인 마켓플레이스·플러그인 설치")
    have = {m["name"] for m in claude_json("marketplace", "list")}
    wanted = [(n, source_arg(v["source"])) for n, v in MAN["marketplaces"].items()]
    wanted += [OFFICIAL, ("claude-workflow", str(REPO))]
    for name, src in wanted:
        if name in have:
            continue
        r = claude("marketplace", "add", src)
        say(f"  마켓플레이스 {name}: {'추가' if r.returncode == 0 else '실패'}")
        if r.returncode != 0:
            failed.append(f"marketplace {name}: {(r.stderr or r.stdout).strip()[-300:]}")
    installed = {p["id"] for p in claude_json("list")}
    for pid in MAN["plugins"]:
        if pid in installed:
            continue
        r = claude("install", pid)
        say(f"  플러그인 {pid}: {'설치' if r.returncode == 0 else '실패'}")
        if r.returncode != 0:
            failed.append(f"plugin {pid}: {(r.stderr or r.stdout).strip()[-300:]}")


def copy_skill(src_dir, name, only=None):
    dst = CFG / "skills" / name
    if not (src_dir / "SKILL.md").exists():
        return "원본 없음"
    # 임시 이름으로 다 복사한 뒤 한 번에 바꿔 단다 — 중간에 실패하면 반쪽 폴더가 남지 않는다
    tmp = dst.with_name(f".{name}.installing")
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        tmp.mkdir(parents=True)
        for item in (only or [p.name for p in src_dir.iterdir()]):
            p = src_dir / item
            if p.is_dir():
                shutil.copytree(p, tmp / item)
            elif p.exists():
                shutil.copy2(p, tmp / item)
        os.replace(tmp, dst)
    except OSError:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return "설치"


def skills_step(state):
    say("[2/5] 로컬 스킬 (원 저장소에서 받는다)")
    ls = MAN["local_skills"]
    mine = set(state.setdefault("skills_installed", []))
    jobs = {}  # 저장소 하나는 한 번만 받는다
    for repo, names in ls["github"].items():
        jobs.setdefault(f"https://github.com/{repo}.git", []).extend((n, f"skills/{n}", None) for n in names)
    for name, spec in ls["git"].items():
        jobs.setdefault(spec["repo"], []).append((name, spec["path"], spec.get("copy")))
    foreign = [n for items in jobs.values() for n, _, _ in items
               if (CFG / "skills" / n).exists() and n not in mine]
    if foreign:
        say(f"  △ 원래 있던 같은 이름의 스킬은 그대로 둔다: {', '.join(foreign)}")
        say("    (단 이 이름들은 아래 숨김·합침 대상이다 — README '설치가 바꾸는 것')")
    with tempfile.TemporaryDirectory() as tmp:
        for i, (url, items) in enumerate(jobs.items()):
            todo = [it for it in items if not (CFG / "skills" / it[0]).exists()]
            if not todo:
                continue
            work = Path(tmp) / str(i)
            r = run(["git", "clone", "-q", "--depth", "1", url, str(work)])
            if r.returncode != 0:
                failed.append(f"git clone {url}: {r.stderr.strip()[-300:]}")
                continue
            for name, path, only in todo:
                try:
                    res = copy_skill(work / path, name, only)
                except OSError as e:
                    res = f"실패 ({e})"
                say(f"  {name}: {res}")
                if res == "설치":
                    mine.add(name)
                else:
                    failed.append(f"skill {name}: {res if res != '원본 없음' else f'{url} 에 {path}/SKILL.md 가 없다'}")
    state["skills_installed"] = sorted(mine)


def patch_skills(state):
    say("[3/5] 스킬 패치 (이 스크립트가 설치한 스킬만)")
    mine = set(state.get("skills_installed", []))
    # 업스트림이 자동 호출을 막아 배포한 것 — 작업 규칙의 라우팅 표에서 쓰므로 푼다
    for name in MAN["local_skills"].get("allow_model_invocation", []):
        f = CFG / "skills" / name / "SKILL.md"
        if name in mine and f.exists() and DMI in f.read_text(encoding="utf-8"):
            lines = [l for l in f.read_text(encoding="utf-8").splitlines(True) if l.strip() != DMI]
            f.write_text("".join(lines), encoding="utf-8")
            say(f"  자동 호출 허용: {name}")
    # arena: 하위 에이전트 16~100개를 띄우므로 사용자 호출 전용으로. 윈도우는 python3 대신 python
    f = CFG / "skills" / "arena" / "SKILL.md"
    if "arena" in mine and f.exists():
        t = f.read_text(encoding="utf-8")
        new = t
        if os.name == "nt":
            new = new.replace('python3 "${CLAUDE_SKILL_DIR}/bracket.py"', 'python "${CLAUDE_SKILL_DIR}/bracket.py"')
        if DMI not in new:
            new = new.replace("\nargument-hint:", f"\n{DMI}\nargument-hint:", 1)
        if new != t:
            f.write_text(new, encoding="utf-8")
            say("  arena: 사용자 호출 전용" + (" · python 호출" if os.name == "nt" else ""))


def install_owned(src, dst, key, state):
    """우리 파일을 놓는다. 지난번에 놓은 그대로면 새 판으로 바꾸고, 사용자가 고쳤으면 .new 로 옆에 둔다."""
    hashes = state.setdefault("hashes", {})
    cur, new = sha(dst), sha(src)
    if cur == new:
        hashes[key] = new
        return "최신"
    if cur is None or cur == hashes.get(key):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        hashes[key] = new
        return "설치" if cur is None else "갱신"
    shutil.copy2(src, dst.with_name(dst.name + ".new"))
    return f"고친 흔적이 있어 그대로 둠 — 새 판은 {dst.name}.new"


def rules_step(state):
    say("[4/5] 작업 규칙 · worker 에이전트 · 기본 모델")
    CFG.mkdir(parents=True, exist_ok=True)
    say("  workflow-rules.md: " + install_owned(REPO / "rules" / "workflow-rules.md", CFG / "workflow-rules.md", "rules", state))
    md = CFG / "CLAUDE.md"
    text = md.read_text(encoding="utf-8-sig") if md.exists() else ""
    if not any(l.strip() == "@workflow-rules.md" for l in text.splitlines()):
        sep = "" if not text or text.endswith("\n") else "\n"
        md.write_text(text + sep + "\n# claude-workflow 작업 규칙 (설치 스크립트가 넣은 줄)\n@workflow-rules.md\n", encoding="utf-8")
        say("  CLAUDE.md 에 @workflow-rules.md 추가")
    say("  worker 에이전트: " + install_owned(REPO / "agents" / "worker.md", CFG / "agents" / "worker.md", "worker", state))
    p = CFG / "settings.json"
    try:
        s = json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {}  # 메모장·PowerShell 이 붙인 BOM 도 읽는다
    except ValueError as e:
        raise RuntimeError(f"settings.json 을 읽지 못했다 — 기본 모델 단계만 건너뜀 ({e})")
    added = {k: v for k, v in MAN["settings_defaults"].items() if k not in s}
    if added:
        s.update(added)
        write_json(p, s)
        say(f"  기본값 추가: {added}")


def trims_step(state):
    say("[5/5] 겹치는 스킬 숨김·합침")
    r = run([sys.executable, str(PLUGIN / "scripts" / "trim-descriptions.py"), "--all", "--apply"])
    for l in [l for l in r.stdout.splitlines() if l.strip()][-3:]:
        say(f"  {l}")
    if r.returncode != 0:
        failed.append(f"trim-descriptions: {(r.stderr or r.stdout).strip()[-300:]}")


def main():
    say(f"설정 폴더: {CFG}\n저장소: {REPO}\n")
    for tool in ("claude", "git"):
        if not shutil.which(tool):
            say(f"✗ `{tool}` 가 없다 — 먼저 설치한다 (README 의 선행 조건).")
            return 1
    CFG.mkdir(parents=True, exist_ok=True)
    state = load_state()
    for step in (plugins_step, skills_step, patch_skills, rules_step, trims_step):
        try:
            step(state)  # 한 단계가 실패해도 나머지는 돈다
        except Exception as e:  # noqa: BLE001 — 실패 목록에 남기고 계속
            failed.append(f"{step.__name__}: {type(e).__name__}: {e}")
        write_json(STATE_PATH, state)
    if failed:
        say("\n✗ 실패한 단계 (고친 뒤 다시 돌리면 이어서 한다):")
        for f in failed:
            say(f"  - {f}")
    say("\n다음: Claude Code 를 완전히 껐다 켠 뒤 \"스킬 확인해\" 라고 말한다.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
