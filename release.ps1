# release.ps1
# GitHub 릴리즈 생성 + exe 업로드 자동화 스크립트
# 사용법: .\release.ps1

param(
    [string]$Version = "",
    [string]$ExeName = "LineageHP",
    [string]$SpecFile = "LineageHP.spec"
)

$Owner = "Parkgeonu"
$Repo  = "gunnupark"
$Dir   = $PSScriptRoot

Set-Location $Dir
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ── 헬퍼 ────────────────────────────────────────────────────────────────────
function Write-Step { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Fail { param($msg) Write-Host "    [ERR] $msg" -ForegroundColor Red; exit 1 }

# ── 1. PAT 입력 ──────────────────────────────────────────────────────────────
Write-Step "GitHub Personal Access Token 입력"
$patSecure = Read-Host "PAT (입력 내용 숨김)" -AsSecureString
$pat = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
           [Runtime.InteropServices.Marshal]::SecureStringToBSTR($patSecure))
if (-not $pat) { Write-Fail "PAT가 입력되지 않았습니다." }

$headers = @{
    "Authorization" = "Bearer $pat"
    "Accept"        = "application/vnd.github+json"
    "User-Agent"    = "LineageReleaseScript/1.0"
    "X-GitHub-Api-Version" = "2022-11-28"
}

# ── 2. 버전 입력 ─────────────────────────────────────────────────────────────
Write-Step "릴리즈 버전 입력"
if (-not $Version) {
    $Version = Read-Host "버전 (예: 1.0.1)"
}
if (-not $Version) { Write-Fail "버전이 입력되지 않았습니다." }
$tag = "v$Version"
Write-OK "버전: $tag"

# ── 3. Git 초기화 & 코드 푸시 ────────────────────────────────────────────────
Write-Step "Git 저장소 설정 및 코드 푸시"

$gitPath = (Get-Command git -ErrorAction SilentlyContinue).Source
if (-not $gitPath) {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")
    $gitPath = (Get-Command git -ErrorAction SilentlyContinue).Source
    if (-not $gitPath) { Write-Fail "git을 찾을 수 없습니다." }
}

$isGitRepo = Test-Path (Join-Path $Dir ".git")
if (-not $isGitRepo) {
    Write-Host "    git init..."
    git init
    git config user.email "release@lineage.local"
    git config user.name  "Lineage Release"
}

$remoteUrl = "https://${pat}@github.com/${Owner}/${Repo}.git"
git remote remove origin 2>$null
git remote add origin $remoteUrl

git add .
git commit -m "release: $tag" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    # 변경사항 없으면 빈 커밋
    git commit --allow-empty -m "release: $tag"
}

git branch -M main
git push -u origin main --force
if ($LASTEXITCODE -ne 0) { Write-Fail "git push 실패" }
Write-OK "코드 푸시 완료"

# ── 4. PyInstaller exe 빌드 ──────────────────────────────────────────────────
Write-Step "PyInstaller 빌드: $SpecFile"
$specPath = Join-Path $Dir $SpecFile
if (-not (Test-Path $specPath)) { Write-Fail "$SpecFile 파일을 찾을 수 없습니다." }

python -m PyInstaller $specPath --noconfirm 2>&1 | Tail -20
if ($LASTEXITCODE -ne 0) { Write-Fail "빌드 실패" }

$exePath = Join-Path $Dir "dist\$ExeName.exe"
if (-not (Test-Path $exePath)) { Write-Fail "빌드된 exe를 찾을 수 없습니다: $exePath" }
$exeSize = (Get-Item $exePath).Length
Write-OK "빌드 완료: $exePath  ($([math]::Round($exeSize/1MB,1)) MB)"

# ── 5. GitHub 릴리즈 생성 ───────────────────────────────────────────────────
Write-Step "GitHub 릴리즈 생성: $tag"

# 기존 릴리즈/태그 삭제 (동일 태그 재사용 시)
try {
    $existing = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/$Owner/$Repo/releases/tags/$tag" `
        -Headers $headers -ErrorAction Stop
    Invoke-RestMethod `
        -Method Delete `
        -Uri "https://api.github.com/repos/$Owner/$Repo/releases/$($existing.id)" `
        -Headers $headers | Out-Null
    Write-Host "    기존 릴리즈 삭제됨"
} catch {}

try {
    $tagRes = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/$Owner/$Repo/git/refs/tags/$tag" `
        -Headers $headers -ErrorAction Stop
    Invoke-RestMethod `
        -Method Delete `
        -Uri "https://api.github.com/repos/$Owner/$Repo/git/refs/tags/$tag" `
        -Headers $headers | Out-Null
    Write-Host "    기존 태그 삭제됨"
} catch {}

$releaseBody = @{
    tag_name         = $tag
    target_commitish = "main"
    name             = "$ExeName $tag"
    body             = "## $ExeName $tag`n`n- 자동 업데이트 지원"
    draft            = $false
    prerelease       = $false
} | ConvertTo-Json

$release = Invoke-RestMethod `
    -Method Post `
    -Uri "https://api.github.com/repos/$Owner/$Repo/releases" `
    -Headers $headers `
    -Body $releaseBody `
    -ContentType "application/json"

Write-OK "릴리즈 생성: $($release.html_url)"

# ── 6. exe 업로드 ────────────────────────────────────────────────────────────
Write-Step "exe 파일 업로드: $ExeName.exe"

$uploadUrl = $release.upload_url -replace "\{\?name,label\}", ""
$uploadHeaders = $headers.Clone()
$uploadHeaders["Content-Type"] = "application/octet-stream"

$exeBytes = [System.IO.File]::ReadAllBytes($exePath)
$uploaded = Invoke-RestMethod `
    -Method Post `
    -Uri "${uploadUrl}?name=${ExeName}.exe" `
    -Headers $uploadHeaders `
    -Body $exeBytes

Write-OK "업로드 완료: $($uploaded.browser_download_url)"

# ── 7. 완료 ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host " 릴리즈 완료!" -ForegroundColor Yellow
Write-Host " URL : $($release.html_url)" -ForegroundColor Yellow
Write-Host " exe : $($uploaded.browser_download_url)" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "업데이트 테스트 방법:" -ForegroundColor White
Write-Host "  1. dist\$ExeName.exe 를 실행하면 자동으로 $tag 감지" -ForegroundColor Gray
Write-Host "  2. 또는: python test_update.py" -ForegroundColor Gray
