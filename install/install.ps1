# claude-workflow 설치 (윈도우)
# 사용: 저장소 폴더에서  powershell -ExecutionPolicy Bypass -File install\install.ps1
# 실제 설치는 install.py 가 한다. 여기서는 선행 조건과 윈도우 전용 python3 보정만 한다.
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

foreach ($t in 'git', 'claude') {
  if (-not (Get-Command $t -ErrorAction SilentlyContinue)) {
    Write-Host "✗ '$t' 가 없습니다 — README 의 선행 조건을 먼저 설치하세요." -ForegroundColor Red; exit 1
  }
}
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if ($py) { & python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>$null }
if (-not $py -or $LASTEXITCODE -ne 0) {
  Write-Host "✗ Python 3.9 이상이 없습니다 (python.org 설치본 권장, 설치 때 'Add to PATH' 체크)." -ForegroundColor Red; exit 1
}

# 플러그인 훅은 python3 로 돈다. 윈도우의 python3 는 흔히 MS 스토어 안내용 스텁이라 훅이 조용히 실패한다.
# 이미 되면 손대지 않고, 안 되면 진짜 python 옆에 python3.exe 사본을 둔다.
& python3 -c "import sys" 2>$null
if ($LASTEXITCODE -ne 0) {
  if ($py -notmatch 'WindowsApps') {
    $py3 = Join-Path (Split-Path $py) 'python3.exe'
    try { Copy-Item $py $py3 -ErrorAction Stop; Write-Host "python3.exe 생성: $py3" }
    catch { Write-Host "  python3.exe 를 만들지 못했습니다(권한): $py3" -ForegroundColor Yellow }
  }
  & python3 -c "import sys" 2>$null
}
$py3ok = ($LASTEXITCODE -eq 0)

& $py (Join-Path $here 'install.py')
$rc = $LASTEXITCODE
if (-not $py3ok) {
  Write-Host ""
  Write-Host "✗ 'python3' 가 동작하지 않습니다 — 이대로면 위험 명령 차단 훅이 돌지 않습니다." -ForegroundColor Red
  Write-Host "  설정 > 앱 > 고급 앱 설정 > 앱 실행 별칭에서 python3 를 끄거나(스토어 스텁), 관리자 PowerShell 에서 이 스크립트를 다시 실행하세요." -ForegroundColor Red
  exit 1
}
exit $rc
