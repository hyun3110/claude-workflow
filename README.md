# claude-workflow

Claude Code 를 이렇게 일하게 만드는 설정 묶음이다:

- **메인 세션은 총괄**, 독립 작업은 `worker` 하위 에이전트에 나눠 병렬로
- **손대기 전에 알리고**, 되돌리기 어려운 건 확인받고
- 작업마다 맞는 스킬을 쓰고 첫 줄에 `[스킬: X]` 로 밝히고
- 코드 리뷰·보안은 **codex + Claude 2패스**
- **"완료"는 실제로 눌러 보고 나서만**

규칙 원문은 [`rules/workflow-rules.md`](rules/workflow-rules.md).

## 설치 — 한 줄

```powershell
# 윈도우 (PowerShell)
irm https://raw.githubusercontent.com/hyun3110/claude-workflow/main/install/get.ps1 | iex
```

```bash
# 맥·리눅스 (터미널)
curl -fsSL https://raw.githubusercontent.com/hyun3110/claude-workflow/main/install/get.sh | bash
```

이 한 줄이 순서대로 한다:
1. **빠진 준비물을 설치** — Claude Code CLI(공식 설치 스크립트) · Git · Python 3.9+ (윈도우는 winget, 맥은 Command Line Tools 설치 창). 이미 있으면 건너뛴다
2. 홈 폴더의 `claude-workflow` 에 이 저장소를 받는다(이미 있으면 `git pull` = 업데이트)
3. 설치한다

받는 사람이 할 일: 윈도우는 Git 설치 때 **관리자 확인 창에서 "예"**, 맥은 처음 한 번 **Command Line Tools 설치 창에서 "설치"** 후 같은 한 줄을 다시 붙여 넣기. 끝나면 **Claude Code(데스크톱 앱이면 앱)를 켜서 — 처음이면 로그인 — "스킬 확인해"** → ✓/✗ 표가 나온다. 자동 설치가 안 된 준비물이 있으면 직접 설치 링크를 알려 주고 멈춘다.

데스크톱 앱만 쓰는 사람도 이 한 줄이 CLI 를 깔아 준다(데스크톱 앱은 터미널 `claude` 명령을 만들지 않는다). 설치 결과는 데스크톱 앱에도 그대로 적용된다.

> **`claude-workflow` 폴더는 지우거나 옮기지 않는다.** `workflow` 플러그인이 이 폴더를 직접 읽는다.

**준비물** (한 줄이 자동으로 설치 — 수동으로 할 때만 참고)

| 필요 | 수동 설치 |
|---|---|
| Claude Code **CLI** | 윈도우 `irm https://claude.ai/install.ps1 \| iex` · 맥 `curl -fsSL https://claude.ai/install.sh \| bash` |
| Git | 윈도우 `winget install Git.Git` (Claude Code 훅이 Git Bash 로 돈다) · 맥 `xcode-select --install` |
| Python 3.9+ | 윈도우 `winget install Python.Python.3.12` 또는 python.org(설치 때 *Add to PATH* 체크) · 맥은 Command Line Tools 의 python3 로 충분 |

**선택** (없어도 설치는 된다)

| 있으면 | 쓰는 곳 |
|---|---|
| [codex CLI](https://github.com/openai/codex) + 로그인 | 2패스 리뷰의 codex 쪽 (없으면 Claude 단독) |
| Bun (`npm i -g bun`) | `claude-mem` 세션 기억 워커 |
| ffmpeg · yt-dlp | `watch` 영상 분석 |
| Obsidian 볼트 | `km` 지식관리 |

**직접 받아서 설치** (한 줄 대신)

```bash
git clone https://github.com/hyun3110/claude-workflow.git ~/claude-workflow
cd ~/claude-workflow
powershell -ExecutionPolicy Bypass -File install\install.ps1   # 윈도우
bash install/install.sh                                        # 맥·리눅스
```

데스크톱 앱은 일반(로컬) 세션으로 쓴다 — WSL 세션에서는 플러그인이 동작하지 않는다(Claude Code 문서).

**업데이트**: 같은 한 줄을 다시 붙여 넣는다(= `git pull` 후 설치 스크립트 재실행). 여러 번 돌려도 안전하고, 중간에 실패해도 다시 돌리면 이어서 한다. 작업 규칙·`worker`·`workflow` 플러그인·스킬 통합 설정이 새 판으로 바뀐다. 다른 플러그인은 Claude Code 가 스스로 업데이트하고, 그때 숨김·합침이 풀리면 세션 시작 때 알림이 뜬다 → 설치 스크립트를 다시 돌린다.

## 설치가 바꾸는 것

설정 폴더(`~/.claude`, 또는 `CLAUDE_CONFIG_DIR`)에 쓴다. 윈도우만 예외로 python 폴더에 `python3.exe` 사본을 둔다.

| 무엇 | 어떻게 |
|---|---|
| 플러그인 20개 | 마켓플레이스 등록 후 `claude plugin install` — 목록은 [`plugins/workflow/manifest.json`](plugins/workflow/manifest.json). 이미 설치된 건 건너뛴다 |
| 로컬 스킬 23개 | 각 원 저장소에서 git 으로 받아 `skills/` 에 복사. **원래 있던 같은 이름 스킬은 받지도 패치하지도 않는다** — 단 아래 숨김·합침 대상 이름이면 그것도 숨겨진다(설치 때 △ 로 알려 준다) |
| 작업 규칙 | `workflow-rules.md` 를 놓고, `CLAUDE.md` 끝에 `@workflow-rules.md` 한 줄만 덧붙인다 |
| `worker` 에이전트 | `agents/worker.md` (opus·medium) |
| 기본 모델·강도 | `settings.json` 에 `model`·`effortLevel` 이 **없을 때만** opus·xhigh |
| 겹치는 스킬 정리 | 아래 "스킬 통합" — 흡수된 스킬에 `disable-model-invocation: true`, 대표 스킬 끝에 "합쳐진 기능" 절 |
| 설치 기록 | `.claude-workflow.json` — 이 스크립트가 설치한 스킬과, 놓은 규칙·worker 파일의 지문 |
| 윈도우만 | `python3` 가 안 되면 진짜 python 옆에 `python3.exe` 사본 (훅이 `python3` 으로 돈다) |

`workflow-rules.md`·`worker.md` 를 직접 고쳐 쓰고 있으면 다시 설치해도 덮어쓰지 않고 새 판을 `.new` 로 옆에 둔다.

`workflow` 플러그인(이 저장소)이 넣는 것: 위험 명령 차단 훅(`rm -rf`·`git push --force`·`git reset --hard`·`git clean -f`·`git branch -D` 등 → 사용자 확인 요구) · 플랜 가독성 가이드 · 세션 컨텍스트 · 숨김·합침이 풀리면 세션 시작 때 알림 · `skill-check`.

## 스킬 통합

겹치거나 같이 쓰면 나은 스킬을 **대표 하나에 합쳤다.** 대표를 부르면 흡수한 스킬의 절차가 대표 안("합쳐진 기능" 절)에 들어 있다. 흡수된 스킬은 모델 목록에서 빠지지만 `/이름` 으로 직접 치는 건 된다. 설정: [`plugins/workflow/scripts/trims.json`](plugins/workflow/scripts/trims.json) 의 `_merge`·`_hide`.

| 대표 (이것만 부른다) | 흡수한 것 |
|---|---|
| `superpowers:systematic-debugging` | investigate-first · surgical-patch |
| `superpowers:writing-plans` | claude-mem:make-plan · lean-build |
| `superpowers:subagent-driven-development` | dispatching-parallel-agents |
| `superpowers:verification-before-completion` | verify-and-stop |
| `understand-anything:understand` | understand-onboard · understand-domain |
| `understand-anything:understand-explain` | understand-chat |
| `web-quality-audit` | performance · core-web-vitals · accessibility · best-practices · seo |
| `claude-seo:seo` | seo-audit · seo-geo 등 하위 명령 25개 (`/claude-seo:seo <명령>`) |
| `review-animations` | improve-animations · find-animation-opportunities |
| `frontend-design` | emil-design-eng |
| `taste-skill:design-taste-frontend` | 스타일 프리셋 6종 · redesign |
| `ponytail:ponytail-audit` | ponytail-review · ponytail-debt |
| `claude-md-management:revise-claude-md` | claude-md-improver |
| `claude-mem:timeline-report` | weekly-digests |

합칠 가치가 없는 중복·사용자가 직접 치는 명령·추가 설정이 있어야 도는 것은 합치지 않고 목록에서만 뺐다(`_hide`).

> **플러그인이 업데이트되면 숨김·합침이 풀린다**(캐시가 새로 깔린다). 세션 시작 때 `[workflow] 스킬 숨김·합침이 풀렸습니다` 가 뜨면 설치 스크립트를 다시 돌린다.

## 문제 해결

"스킬 확인해" 표의 ✗ 별 조치:

| ✗ 항목 | 조치 |
|---|---|
| python3 실행 | 윈도우: 설치 스크립트가 `python3.exe` 를 만들지 못했거나 스토어 별칭이 앞선다 → 설정 > 앱 > 고급 앱 설정 > 앱 실행 별칭에서 python3 끄기 |
| 작업 규칙 연결 | 설치 스크립트 재실행 |
| 플러그인 설치·활성 | `/plugin` 에서 설치·켜기 → 그래도 없으면 설치 스크립트 재실행. 설치 로그에 `Filename too long`(윈도우 경로 길이 제한)이 보이면 `git config --global core.longpaths true` 후 재실행 |
| 로컬 스킬 | 설치 스크립트 재실행 (네트워크·GitHub 접근 확인) |
| 숨김·합침 유지 | 설치 스크립트 재실행 |
| 위험 명령 차단 훅 | `/plugin` 에서 `workflow` 재설치 |
| 새 세션 스킬 목록 | 숨김 재적용(설치 스크립트) 후 Claude Code 재시작 |

## 고쳐 쓰기

- 작업 방식: `rules/workflow-rules.md` → 설치 스크립트 재실행
- 플러그인·스킬 더하기/빼기: `plugins/workflow/manifest.json`
- 합치기·숨기기: `plugins/workflow/scripts/trims.json`

## 지우기

설정 폴더 = `~/.claude` (또는 `CLAUDE_CONFIG_DIR`).

1. 설정 폴더의 `CLAUDE.md` 에서 `@workflow-rules.md` 줄과 그 위 주석 줄을 지우고, `workflow-rules.md`·`agents/worker.md`·`.claude-workflow.json` 삭제
2. 로컬 스킬: `.claude-workflow.json` 의 `skills_installed` 에 적힌 폴더만 `skills/` 에서 삭제 (원래 있던 스킬은 거기 없다)
3. 숨김·합침 되돌리기(플러그인을 남길 때만): `python3 plugins/workflow/scripts/trim-descriptions.py --all --restore` — 그 뒤 업데이트된 플러그인이면 `/plugin` 에서 재설치하는 편이 깔끔하다
4. `/plugin` 에서 원하는 플러그인 제거 (`workflow` 포함)
5. 윈도우: python 폴더의 `python3.exe` 사본은 다른 곳에서 안 쓰면 지워도 된다(`settings.json` 의 `model`·`effortLevel` 도 원하면 지운다)

## 알아 둘 한계

- **외부 플러그인·스킬은 설치 때의 최신판을 받는다**(버전 고정 없음). 공개 저장소지만 검토 없이 바뀔 수 있다 — 민감한 환경이면 `manifest.json` 의 출처를 먼저 본다.
- 위험 명령 차단 훅은 문자열 규칙이라 보수적이다: 따옴표 안 문자열(`echo "rm -rf"`, 커밋 메시지 속 `git push -f`)도 막는다. 셸 변수·`eval` 로 꾸민 명령은 못 잡는다. 안전장치일 뿐 권한 설정을 대신하지 않는다.
- `--restore` 는 스킬을 처음 숨기기 전 사본으로 되돌린다. 그 사이 플러그인이 업데이트됐으면 옛 내용이 돌아올 수 있다.

## 출처

로컬 스킬과 플러그인은 이 저장소에 복사돼 있지 않다 — 설치 때 각 원 저장소에서 받으며, 각자의 라이선스를 따른다(`manifest.json` 에 출처). 이 저장소가 직접 담은 것은 작업 규칙, `workflow` 플러그인(훅·점검 스크립트), 설치 스크립트, 스킬 통합 설정이다.
