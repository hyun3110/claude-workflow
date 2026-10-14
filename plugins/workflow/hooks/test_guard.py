"""guard-dangerous-bash.py 시험 — 명령 문자열을 훅 stdin 에 넣고 종료코드만 본다(명령은 실행하지 않는다)."""
import json
import os
import subprocess
import sys

GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard-dangerous-bash.py")

BLOCK = [
    "rm -rf /tmp/a", "rm -r -f /tmp/a", "rm -f -r x", "rm -R -f x", "rm -fR x", "rm -fr x",
    "rm --recursive --force /tmp/a", "rm --force --recursive x", "rm -r --force x",
    "/bin/rm -rf /tmp/a", "sudo rm -rf x", "cd x && rm -rf y", "find . | xargs rm -rf",
    "echo $(rm -rf x)", "(rm -rf x)",
    "git push --force", "git push -f", "git -C /tmp/a reset --hard", "git -c x=y push --force",
    "git push origin main -f", "git push --force-with-lease", "git push origin +main",
    "git --git-dir=/x/.git reset --hard HEAD", "/usr/bin/git push --force",
    "git clean -fd", "git clean -xdf", "git branch -D x", "git branch --delete --force x",
    "npm uninstall x", "pnpm uninstall x", "pip uninstall x", "pip3 uninstall x",
    "echo git push --force",  # 보수적 오탐(따옴표·인자 해석 안 함) — 차단으로 남긴다
    "cd x\nrm -rf y",
    "\\rm -rf x", 'bash -c "rm -rf x"', "sh -c 'git reset --hard'",
    "shutdown now", "sudo reboot", "mkfs.ext4 /dev/sda1", "dd if=a of=/dev/sda", "chmod -R 777 x",
]
ALLOW = [
    "rm -r x", "rm -f x", "rm file.txt", "git push", "git push origin feature-fix",
    "git reset --soft HEAD~1", "git status", "echo hello", "npm install x",
    "git clean -n", "git branch -d x", "ls -rf", "rm -r a; ls -f", "git log --format=%H",
    "",
]


def run(cmd, tool="Bash"):
    data = json.dumps({"tool_name": tool, "tool_input": {"command": cmd}}).encode()
    return subprocess.run([sys.executable, GUARD], input=data, capture_output=True).returncode


cases = [(c, 2) for c in BLOCK] + [(c, 0) for c in ALLOW]
cases.append(("rm -rf /tmp/a", 0, "Read"))  # Bash 아닌 도구는 통과
fail = 0
for case in cases:
    cmd, want, *tool = case
    got = run(cmd, *tool)
    if got != want:
        fail += 1
        print(f"실패: {cmd!r} 기대 {want} 실제 {got}")

# 차단 메시지의 명령 줄은 200자에서 자른다
long_cmd = "rm -rf x " + "A" * 500
p = subprocess.run([sys.executable, GUARD], input=json.dumps({"tool_name": "Bash", "tool_input": {"command": long_cmd}}).encode(), capture_output=True)
line = [l for l in p.stderr.decode("utf-8").splitlines() if "차단된 명령:" in l][0]
total = len(cases) + 1
if "A" * 300 in line:
    fail += 1
    print("실패: 긴 명령이 200자에서 잘리지 않음")

print(f"{total - fail}/{total} 통과")
sys.exit(1 if fail else 0)
