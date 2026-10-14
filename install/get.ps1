# claude-workflow 한 줄 설치 (윈도우 PowerShell)
#   irm https://raw.githubusercontent.com/hyun3110/claude-workflow/main/install/get.ps1 | iex
# 홈 폴더에 저장소를 받고(이미 있으면 git pull) install.ps1 을 이어서 돌린다.
# irm | iex 로 돌기 때문에 exit 를 쓰지 않는다 — exit 는 사용자의 PowerShell 창을 닫는다.
& {
  [Console]::OutputEncoding = [Text.Encoding]::UTF8
  $repo = 'https://github.com/hyun3110/claude-workflow.git'
  $dir = if ($env:CLAUDE_WORKFLOW_DIR) { $env:CLAUDE_WORKFLOW_DIR } else { Join-Path $HOME 'claude-workflow' }

  $hints = [ordered]@{
    'claude' = 'Claude Code CLI:  irm https://claude.ai/install.ps1 | iex   (설치 후 새 창에서 claude 를 한 번 실행해 로그인)'
    'git'    = 'Git:  winget install Git.Git   (또는 https://git-scm.com)'
    'python' = 'Python 3.10+:  winget install Python.Python.3.12   (또는 python.org, 설치 때 Add to PATH 체크)'
  }
  $miss = @($hints.Keys | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
  if ($miss.Count) {
    Write-Host "먼저 설치가 필요합니다 (설치 후 PowerShell 을 새로 열고 같은 한 줄을 다시 붙여 넣으세요):" -ForegroundColor Yellow
    foreach ($m in $miss) { Write-Host "  - $($hints[$m])" }
    return
  }

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

  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $dir 'install\install.ps1')
  Write-Host ""
  Write-Host "설치 폴더: $dir  — 지우거나 옮기지 마세요 (플러그인이 이 폴더를 직접 읽습니다)."
}
