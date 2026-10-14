# claude-workflow 한 줄 설치 (윈도우 PowerShell)
#   irm https://raw.githubusercontent.com/hyun3110/claude-workflow/main/install/get.ps1 | iex
# 빠진 준비물(Claude Code CLI·Git·Python)을 먼저 설치하고, 홈 폴더에 저장소를 받아(이미 있으면 git pull)
# install.ps1 을 이어서 돌린다. 여러 번 붙여 넣어도 안전하다.
# irm | iex 로 돌기 때문에 exit 를 쓰지 않는다 — exit 는 사용자의 PowerShell 창을 닫는다.
& {
  [Console]::OutputEncoding = [Text.Encoding]::UTF8
  $repo = 'https://github.com/hyun3110/claude-workflow.git'
  $dir = if ($env:CLAUDE_WORKFLOW_DIR) { $env:CLAUDE_WORKFLOW_DIR } else { Join-Path $HOME 'claude-workflow' }

  function Update-SessionPath {
    # 방금 설치한 프로그램이 이 창에서 바로 보이게 — 창을 새로 열 필요 없음
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
    $lb = Join-Path $HOME '.local\bin'  # Claude Code 공식 설치 위치
    if ((Test-Path $lb) -and ($env:Path -notlike "*$lb*")) { $env:Path = "$lb;$env:Path" }
  }
  function Test-Cmd($c) { [bool](Get-Command $c -ErrorAction SilentlyContinue) }
  function Test-Python {
    if (-not (Test-Cmd python)) { return $false }
    & python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>$null  # 스토어 안내용 스텁이면 여기서 실패
    return ($LASTEXITCODE -eq 0)
  }
  function Install-Winget($id, $name) {
    if (-not (Test-Cmd winget)) { return }
    Write-Host "설치 중: $name  (관리자 확인 창이 뜨면 '예')" -ForegroundColor Cyan
    winget install -e --id $id --silent --accept-package-agreements --accept-source-agreements | Out-Host
    Update-SessionPath
  }

  # 1) 준비물 — 빠진 것만 설치
  if (-not (Test-Cmd claude)) {
    Write-Host "설치 중: Claude Code CLI" -ForegroundColor Cyan
    # 공식 설치 스크립트는 exit 를 쓰므로 파일로 받아 별도 프로세스로 돌린다 (이 창이 닫히지 않게)
    $cc = Join-Path $env:TEMP 'claude-code-install.ps1'
    try {
      Invoke-WebRequest -UseBasicParsing 'https://claude.ai/install.ps1' -OutFile $cc
      powershell -NoProfile -ExecutionPolicy Bypass -File $cc
    } catch { Write-Host "  Claude Code 설치 스크립트를 받지 못했습니다: $_" -ForegroundColor Yellow }
    Remove-Item $cc -ErrorAction SilentlyContinue
    Update-SessionPath
  }
  if (-not (Test-Cmd git)) { Install-Winget 'Git.Git' 'Git' }
  if (-not (Test-Python)) {
    Install-Winget 'Python.Python.3.12' 'Python 3.12'
    if (-not (Test-Python)) {
      # winget 이 PATH 에 안 넣었으면 설치 폴더를 찾아 사용자 PATH 앞에 넣는다 (훅이 다음 세션에도 python 을 찾게)
      $py = @("$env:LOCALAPPDATA\Programs\Python\Python312", "$env:ProgramFiles\Python312") | Where-Object { Test-Path "$_\python.exe" } | Select-Object -First 1
      if ($py) {
        $user = [Environment]::GetEnvironmentVariable('Path', 'User')
        [Environment]::SetEnvironmentVariable('Path', "$py;$py\Scripts;$user", 'User')
        Update-SessionPath
      }
    }
  }

  $miss = @()
  if (-not (Test-Cmd claude)) { $miss += 'Claude Code CLI — https://code.claude.com/docs/en/setup' }
  if (-not (Test-Cmd git)) { $miss += 'Git — https://git-scm.com/download/win' }
  if (-not (Test-Python)) { $miss += 'Python 3.9+ — https://www.python.org/downloads/  (설치 첫 화면에서 Add python.exe to PATH 체크)' }
  if ($miss.Count) {
    Write-Host "자동으로 설치하지 못한 것이 있습니다. 아래를 직접 설치한 뒤 PowerShell 을 새로 열고 같은 한 줄을 다시 붙여 넣으세요:" -ForegroundColor Yellow
    foreach ($m in $miss) { Write-Host "  - $m" }
    return
  }

  # 2) 저장소 받기 — 이미 있으면 업데이트
  if (Test-Path (Join-Path $dir '.git')) {
    Write-Host "업데이트: $dir"
    git -C $dir pull --ff-only -q
  } elseif (Test-Path $dir) {
    Write-Host "✗ $dir 가 이미 있는데 git 저장소가 아닙니다. 옮기거나 CLAUDE_WORKFLOW_DIR 로 다른 위치를 지정하세요." -ForegroundColor Red
    return
  } else {
    git clone -q $repo $dir
  }
  if ($LASTEXITCODE -ne 0) { Write-Host "✗ 저장소를 받지 못했습니다 (네트워크 확인)." -ForegroundColor Red; return }

  # 3) 설치
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $dir 'install\install.ps1')
  Write-Host ""
  Write-Host "설치 폴더: $dir  — 지우거나 옮기지 마세요 (플러그인이 이 폴더를 직접 읽습니다)."
  Write-Host "다음: Claude Code(또는 데스크톱 앱)를 켜서 — 처음이면 로그인 — `"스킬 확인해`" 라고 말하세요." -ForegroundColor Green
}
