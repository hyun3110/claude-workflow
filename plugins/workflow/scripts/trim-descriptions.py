#!/usr/bin/env python3
"""겹치는 스킬을 대표 하나에 합치고(_merge) 흡수된 쪽을 모델 목록에서 숨긴다(_hide).
trims.json 에 description 축약안이 있으면 그것도 갈아끼운다(이 공유본은 대표 스킬의
"합친 기능" 설명만 둔다 — 나머지 description 은 원문 그대로).

스킬의 always-on 비용 = 이름 + description 이다. 본문은 호출할 때만 든다. 숨긴 스킬은
목록에서 빠지고 `/이름` 직접 호출은 그대로 된다.

⚠️ 플러그인을 업데이트하면 캐시가 새로 깔려 이 변경이 풀린다. 설치 스크립트를 다시
돌리면(= 이 스크립트 --all --apply) 다시 걸리고, 합침 블록의 절차 파일 경로도 새로
갱신된다. --check 는 숨김·합침 표시가 남아 있는지만 본다.

사용:
    python3 trim-descriptions.py --plugin claude-seo           # 미리보기
    python3 trim-descriptions.py --plugin claude-seo --apply   # 적용
    python3 trim-descriptions.py --plugin claude-seo --restore # 원문 복구
    python3 trim-descriptions.py --all --apply                 # trims.json 전부 (+ _hide)
    python3 trim-descriptions.py --check                       # _hide 가 걸려 있는지만 확인

원문은 스킬 폴더의 SKILL.md.orig-desc 에 남는다. --restore 가 그것을 되돌린다.

합침(_merge)·숨김(_hide, 2026-10-13~): 겹치거나 같이 쓰면 나은 스킬을 대표 하나에
합친다 — 대표 끝에 '합쳐진 기능' 절(작은 건 본문 통째, 큰 건 Read 경로)을 붙이고,
흡수된 쪽에는 `disable-model-invocation: true` 를 걸어 목록에서 뺀다. 무엇을 왜
합쳤는지는 저장소 README 의 "스킬 통합" 절에 있다.
"""

from __future__ import annotations  # `X | None` 표기를 Python 3.9 에서도 쓰게

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Claude Code 와 같은 규칙 — CLAUDE_CONFIG_DIR 이 있으면 그쪽(빈 폴더 설치 실험도 이걸로 한다)
CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser().resolve()
CACHE = CLAUDE_DIR / "plugins" / "cache"
TRIMS = Path(__file__).parent / "trims.json"
BACKUP_SUFFIX = ".orig-desc"

# description 필드: 한 줄 형태와 `>` / `|` 접힌 블록 둘 다 잡는다.
DESC_RE = re.compile(
    r"^description:[ \t]*(?:[>|][-+]?[ \t]*\n(?:[ \t]+.*\n)+|.*\n)",
    re.M,
)


def skill_dirs(plugin: str) -> list[Path]:
    """스킬의 SKILL.md 를 찾는다.

    `_local` 은 플러그인이 아니라 ~/.claude/skills/ 아래 로컬 스킬을 가리킨다
    (emilkowalski·web-quality 계열처럼 마켓플레이스가 아니라 직접 깐 것들).
    """
    if plugin == "_local":
        return sorted((CLAUDE_DIR / "skills").glob("*/SKILL.md"))
    hits = sorted(CACHE.glob(f"*/{plugin}/*/skills/*/SKILL.md"))
    if not hits:
        hits = sorted(CACHE.glob(f"*/{plugin}/skills/*/SKILL.md"))
    return hits


MERGE_KEY = "_merge"  # {"<플러그인>|_local": {"<대표 이름>": ["<플러그인>:<흡수 이름>", ...]}}
MERGE_BEGIN = "<!-- skill-merge:begin"
MERGE_END = "<!-- skill-merge:end -->"
MERGE_RE = re.compile(r"\n*<!-- skill-merge:begin.*?<!-- skill-merge:end -->\n?", re.S)
INLINE_MAX = 3000  # 이보다 작은 흡수 본문은 통째로 넣고, 큰 것은 필요할 때 Read 하게 경로만 둔다


def split_frontmatter(text: str) -> tuple[str, str] | None:
    m = re.match(r"\A(---\s*\n)(.*?\n)(---[ \t]*\r?(?:\n|\Z))", text, re.S)  # 끝 줄바꿈 없는 파일도
    if not m:
        return None
    return m.group(2), text[m.end(2) :]


def ensure_backup(path: Path, text: str) -> None:
    """원문을 .orig-desc 로 남긴다. 이 도구는 frontmatter 만 고치므로, 본문이 백업과 다르면
    재설치로 새 원문이 깔린 것이다 — 낡은 백업으로 복구해 새 내용을 날리지 않게 갈아 둔다."""
    backup = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    text = MERGE_RE.sub("", text)  # 우리가 붙인 합침 블록은 원문이 아니다
    if backup.exists():
        old = split_frontmatter(backup.read_text(encoding="utf-8", errors="replace"))
        new = split_frontmatter(text)
        if old and new and old[1].rstrip() == new[1].rstrip():  # 합침 블록을 떼면 끝 줄바꿈이 줄어든다
            return
    backup.write_text(text, encoding="utf-8")


def apply_one(path: Path, new_desc: str, dry: bool) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = split_frontmatter(text)
    if not parts:
        return "프론트매터 없음"
    fm, _rest = parts
    if not DESC_RE.search(fm):
        return "description 필드 없음"

    # YAML 안전: 한 줄 큰따옴표 스칼라로 넣고 내부 따옴표만 이스케이프
    escaped = new_desc.replace("\\", "\\\\").replace('"', '\\"')
    new_fm = DESC_RE.sub(f'description: "{escaped}"\n', fm, count=1)
    if new_fm == fm:
        return "변경 없음"

    if dry:
        return "적용 예정"
    ensure_backup(path, text)
    path.write_text(text.replace(fm, new_fm, 1), encoding="utf-8")
    return "적용됨"


def restore_one(path: Path) -> str:
    backup = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    if not backup.exists():
        return "백업 없음"
    path.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
    backup.unlink()
    return "복구됨"


HIDE_KEY = "_hide"  # {"<플러그인>|_local": ["스킬 이름", ...]}
DMI_RE = re.compile(r"^disable-model-invocation:.*\n(?:[ \t]+.*\n)*", re.M)  # 여러 줄 값까지
DMI_ON = re.compile(r"^disable-model-invocation:[ \t]*true\b", re.M | re.I)  # CRLF·뒤 주석 허용
DMI_LINE = "disable-model-invocation: true\n"


def command_files(plugin: str) -> list[Path]:
    """commands/*.md — 커맨드도 frontmatter 의 disable-model-invocation 을 따른다 (codex 커맨드가 실례)."""
    if plugin == "_local":
        return sorted((CLAUDE_DIR / "commands").glob("*.md"))
    return sorted(CACHE.glob(f"*/{plugin}/*/commands/*.md")) or sorted(CACHE.glob(f"*/{plugin}/commands/*.md"))


def names_of(path: Path) -> set[str]:
    if path.parent.name == "commands":
        return {path.stem}
    head = path.read_text(encoding="utf-8", errors="replace")[:2000]
    m = re.search(r"^name:\s*(.+)$", head, re.M)
    name = re.sub(r"\s+#.*$", "", m.group(1)).strip().strip("\"'") if m else path.parent.name
    return {path.parent.name, name}


def hide_one(path: Path, dry: bool) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = split_frontmatter(text)
    if parts:
        fm = parts[0]
        if DMI_ON.search(fm):
            return "이미 숨김"
        new_fm = DMI_RE.sub(DMI_LINE, fm, count=1) if DMI_RE.search(fm) else fm + DMI_LINE
        new_text = text.replace(fm, new_fm, 1)
    elif text.startswith("---"):  # 있는데 못 읽은 frontmatter 를 감싸면 메타데이터가 본문이 된다
        return "프론트매터 해석 실패 (건너뜀)"
    else:  # 프론트매터 없는 커맨드
        new_text = "---\n" + DMI_LINE + "---\n" + text
    if dry:
        return "숨길 예정"
    ensure_backup(path, text)
    path.write_text(new_text, encoding="utf-8")
    return "숨김"


def hide_targets(trims: dict) -> tuple[list[tuple[Path, str]], list[str]]:
    """_hide 목록을 (SKILL.md 경로, 표시명) 으로 푼다. 폴더명과 name: 둘 다 맞춰 본다."""
    found, missing = [], []
    for plugin, names in trims.get(HIDE_KEY, {}).items():
        if not isinstance(names, list):  # _주석
            continue
        paths = skill_dirs(plugin) + command_files(plugin)
        for want in names:
            hits = [p for p in paths if want in names_of(p)]
            found += [(p, f"{plugin}:{want}") for p in hits]
            if not hits:
                missing.append(f"{plugin}:{want}")
    return found, missing


def run_hide(trims: dict, apply: bool) -> int:
    found, missing = hide_targets(trims)
    print(f"\n=== {HIDE_KEY} (모델 목록에서 숨김, /이름 호출은 유지)")
    for path, label in found:
        print(f"  {label:44} {hide_one(path, dry=not apply)}")
    for label in missing:
        print(f"  {label:44} 못 찾음 (설치 안 됨?)")
    return len(found)


def check_hidden(trims: dict) -> int:
    found, missing = hide_targets(trims)
    def hidden(path: Path) -> bool:
        parts = split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        return bool(parts and DMI_ON.search(parts[0]))

    loose = [label for path, label in found if not hidden(path)]
    for label in loose:
        print(f"  ✗ 숨김 풀림: {label}  → trim-descriptions.py --all --apply")
    for label in missing:
        print(f"  ? 못 찾음: {label}")
    print(f"  숨김 {len(found) - len(loose)}/{len(found)} 유지")
    return 1 if loose else 0



def find_skill_files(plugin: str, name: str) -> list[Path]:
    return [p for p in skill_dirs(plugin) + command_files(plugin) if name in names_of(p)]


def merge_block(specs: list[str]) -> str:
    """흡수할 스킬들의 원문으로 '합쳐진 기능' 절을 만든다. 원문은 축약·숨김 전 백업을 쓴다."""
    out = [MERGE_BEGIN + " 2026-10-13 스킬 통합 — trim-descriptions.py 가 만든다. 직접 고치지 말고 trims.json 의 _merge 를 고친다 -->",
           "## 합쳐진 기능", "",
           "이 스킬이 아래 스킬들을 흡수했다. 요청이 해당하면 이 절의 절차를 따른다 — 흡수된 스킬은 따로 부르지 않는다.", ""]
    for spec in specs:
        plugin, _, name = spec.partition(":")
        hits = find_skill_files(plugin, name)
        if not hits:
            out += [f"### {name} — (이 PC에 설치 안 됨)", ""]
            continue
        p = max(hits, key=lambda h: h.stat().st_mtime)  # 캐시에 버전이 여럿이면 설치본
        b = p.with_suffix(p.suffix + BACKUP_SUFFIX)
        text = (b if b.exists() else p).read_text(encoding="utf-8", errors="replace")
        parts = split_frontmatter(text)
        fm, body = (parts[0], parts[1]) if parts else ("", text)
        body = re.sub(r"\A---[ \t]*\r?\n?", "", body).strip()
        m = re.search(r"^description:[ \t]*(?:[>|][-+]?[ \t]*\n)?((?:.*\n?)(?:[ \t]+.*\n?)*)", fm, re.M)
        desc = " ".join((m.group(1) if m else "").split()).strip("\"'")[:180]
        out.append(f"### {name} — {desc}")
        if len(body) <= INLINE_MAX:
            out += ["", body, ""]
        else:
            out += ["", f"절차 전문은 `{p}` 를 Read 해서 따른다 (그 파일의 상대 링크는 그 폴더 기준).", ""]
    out.append(MERGE_END)
    return "\n".join(out) + "\n"


def merge_one(path: Path, block: str, dry: bool) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    new_text = MERGE_RE.sub("", text).rstrip("\n") + "\n\n" + block
    if new_text == text:
        return "이미 합침"
    if dry:
        return "합칠 예정"
    ensure_backup(path, text)
    path.write_text(new_text, encoding="utf-8")
    return "합침"


def merge_targets(trims: dict):
    for plugin, bases in trims.get(MERGE_KEY, {}).items():
        if not isinstance(bases, dict):  # _주석
            continue
        for base, specs in bases.items():
            yield plugin, base, specs, find_skill_files(plugin, base)


def run_merge(trims: dict, apply: bool) -> int:
    print(f"\n=== {MERGE_KEY} (대표 스킬 안에 흡수한 스킬의 절차를 넣는다)")
    n = 0
    for plugin, base, specs, paths in merge_targets(trims):
        if not paths:
            print(f"  {plugin}:{base:38} 대표를 못 찾음 (설치 안 됨?)")
            continue
        block = merge_block(specs)
        for p in paths:
            print(f"  {plugin}:{base:38} ← {len(specs)}개  {merge_one(p, block, dry=not apply)}")
            n += 1
    return n


def check_merged(trims: dict) -> int:
    allp = [(f"{plugin}:{base}", p) for plugin, base, _s, paths in merge_targets(trims) for p in paths]
    loose = [label for label, p in allp if MERGE_BEGIN not in p.read_text(encoding="utf-8", errors="replace")]
    for label in loose:
        print(f"  ✗ 합침 풀림: {label}  → trim-descriptions.py --all --apply")
    print(f"  합침 {len(allp) - len(loose)}/{len(allp)} 유지")
    return 1 if loose else 0


def selftest() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "SKILL.md"
        orig = "---\nname: x\ndescription: y\n---\nbody\n"
        p.write_text(orig, encoding="utf-8")
        assert hide_one(p, dry=False) == "숨김"
        assert hide_one(p, dry=False) == "이미 숨김"  # 멱등
        assert p.read_text(encoding="utf-8") == "---\nname: x\ndescription: y\n" + DMI_LINE + "---\nbody\n"
        p.write_text(orig.replace("y\n", "y\ndisable-model-invocation: false\n", 1), encoding="utf-8")
        Path(str(p) + BACKUP_SUFFIX).unlink()
        hide_one(p, dry=False)
        assert p.read_text(encoding="utf-8").count("disable-model-invocation") == 1
        assert restore_one(p) == "복구됨" and "false" in p.read_text(encoding="utf-8")
        c = Path(d) / "commands" / "cmd.md"
        c.parent.mkdir()
        c.write_text("no frontmatter\n", encoding="utf-8")
        assert names_of(c) == {"cmd"}
        assert hide_one(c, dry=False) == "숨김"
        assert c.read_text(encoding="utf-8") == "---\n" + DMI_LINE + "---\nno frontmatter\n"
        # 리뷰 반영(2026-10-13): CRLF·뒤 주석·여러 줄 값·끝 줄바꿈 없음·재설치 후 낡은 백업
        for fm in ("disable-model-invocation: true # x\n", "disable-model-invocation: true\r\n"):
            p.write_bytes(("---\nname: x\n" + fm + "---\nb\n").encode("utf-8"))  # 줄바꿈 그대로 (3.9 호환)
            assert hide_one(p, dry=False) == "이미 숨김"
        p.write_text("---\nname: x\ndisable-model-invocation:\n  false\n---\nb\n", encoding="utf-8")
        hide_one(p, dry=False)
        assert "false" not in p.read_text(encoding="utf-8")
        e = c.parent / "eof.md"
        e.write_text("---\ndescription: d\n---", encoding="utf-8")
        hide_one(e, dry=False)
        assert e.read_text(encoding="utf-8") == "---\ndescription: d\n" + DMI_LINE + "---"
        Path(str(p) + BACKUP_SUFFIX).unlink()
        p.write_text("---\nname: x\n---\nold\n", encoding="utf-8")
        hide_one(p, dry=False)
        p.write_text("---\nname: x\n---\nnew\n", encoding="utf-8")  # 재설치로 새 원문
        hide_one(p, dry=False)
        restore_one(p)
        assert p.read_text(encoding="utf-8").endswith("new\n")
        # 합침: 멱등, 백업은 합침 블록 없는 원문, 복구하면 원문
        q = Path(d) / "base.md"
        q.write_text("---\nname: b\n---\nbase\n", encoding="utf-8")
        blk = MERGE_BEGIN + " x -->\n## 합쳐진 기능\nA\n" + MERGE_END + "\n"
        assert merge_one(q, blk, dry=False) == "합침"
        assert merge_one(q, blk, dry=False) == "이미 합침"
        assert q.read_text(encoding="utf-8").count(MERGE_BEGIN) == 1
        hide_one(q, dry=False)  # 합친 뒤 숨김이 와도 백업은 원문 그대로
        assert restore_one(q) == "복구됨" and q.read_text(encoding="utf-8") == "---\nname: b\n---\nbase\n"
    print("selftest ok")
    return 0


def run(plugin: str, table: dict, apply: bool, restore: bool) -> int:
    # 커맨드는 축약안이 있을 때만 (revise-claude-md 처럼 합친 대표가 커맨드인 경우)
    paths = skill_dirs(plugin) + [c for c in command_files(plugin) if restore or c.stem in table]
    if not paths:
        print(f"  {plugin}: 캐시에서 스킬을 못 찾음 (설치 안 됨?)")
        return 0

    before = after = 0
    touched = 0
    for path in paths:
        name = path.stem if path.parent.name == "commands" else path.parent.name
        if restore:
            print(f"  {name:24} {restore_one(path)}")
            continue
        # 폴더명과 SKILL.md 의 name 이 다를 수 있다 (image-to-code-skill vs image-to-code)
        new_desc = next((table[n] for n in sorted(names_of(path)) if n in table), None)
        if not new_desc:
            print(f"  {name:24} 건너뜀 (축약안 없음)")
            continue
        old = path.read_text(encoding="utf-8", errors="replace")
        m = DESC_RE.search(old)
        old_len = len(m.group(0)) if m else 0
        before += old_len
        after += len(new_desc)
        status = apply_one(path, new_desc, dry=not apply)
        if status in ("적용됨", "적용 예정"):
            touched += 1
        print(f"  {name:24} {old_len:>4}자 → {len(new_desc):>3}자  {status}")

    if not restore:
        saved = max(before - after, 0)
        print(f"\n  {plugin}: {touched}개 처리 · 문구 {before}자 → {after}자 "
              f"(약 {saved // 4}토큰 절감 추정)")
    return touched


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin", help="대상 플러그인 이름")
    ap.add_argument("--all", action="store_true", help="trims.json의 모든 플러그인")
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다 (없으면 미리보기)")
    ap.add_argument("--restore", action="store_true", help="원문으로 되돌린다")
    ap.add_argument("--check", action="store_true", help="_hide 가 걸려 있는지만 본다 (풀렸으면 종료코드 1)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not TRIMS.exists():
        print(f"축약안 파일이 없다: {TRIMS}", file=sys.stderr)
        return 1
    trims = json.loads(TRIMS.read_text(encoding="utf-8"))
    if args.check:
        return check_hidden(trims) | check_merged(trims)

    # `_` 로 시작하는 키는 메타(_주석·_hide)다. 단 `_local` 은 로컬 스킬 대상이라 포함한다.
    targets = ([k for k in trims if not k.startswith("_") or k == "_local"]
               if args.all else ([args.plugin] if args.plugin else []))
    if not targets:
        print("--plugin 또는 --all 이 필요하다. 가능한 값:", ", ".join(trims))
        return 1
    if args.all and args.restore:  # 숨김·합침만 걸린 플러그인도 원문으로
        targets += [k for key, typ in ((HIDE_KEY, list), (MERGE_KEY, dict))
                    for k, v in trims.get(key, {}).items() if isinstance(v, typ) and k not in targets]

    total = 0
    for plugin in targets:
        print(f"\n=== {plugin}")
        total += run(plugin, trims.get(plugin, {}), args.apply, args.restore)
    if args.all and not args.restore:
        total += run_hide(trims, args.apply)
        total += run_merge(trims, args.apply)

    if not args.apply and not args.restore:
        print("\n미리보기였다. 실제로 쓰려면 --apply 를 붙인다.")
    elif args.apply:
        print("\n클로드 코드를 새로 켜야 반영된다. 확인: claude plugin details <plugin>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
