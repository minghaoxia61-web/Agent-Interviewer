# 用 headless Chrome 按指定视口逐屏截图（P3R 前端视觉走查）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\shot.ps1 [-W 390 -H 844 -Tag mobile]
param(
  [int]$W = 1440,
  [int]$H = 900,
  [double]$Dsf = 1,
  [string]$Tag = ''
)
$ErrorActionPreference = 'Stop'
$chrome = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$base = 'http://localhost:5173'
$out = Join-Path $PSScriptRoot '..\frontend\shots'
if ($Tag) { $out = Join-Path $out $Tag }
New-Item -ItemType Directory -Force -Path $out | Out-Null
$out = (Resolve-Path $out).Path
Get-ChildItem -Path $out -Filter *.png -ErrorAction SilentlyContinue | Remove-Item -Force

$screens = @(
  @{ hash = 'dashboard'; name = '01_dashboard' },
  @{ hash = 'diagnosis'; name = '02_diagnosis' },
  @{ hash = 'interview'; name = '03_interview' },
  @{ hash = 'questions'; name = '04_questions' },
  @{ hash = 'board';     name = '05_board' },
  @{ hash = 'archive';   name = '06_archive' },
  @{ hash = 'report/276dafa7fb19'; name = '07_report' }
)

foreach ($s in $screens) {
  $url = "$base/#$($s.hash)"
  $png = Join-Path $out "$($s.name).png"
  $udir = Join-Path $env:TEMP ("chrome-headless-rai-" + $s.name)
  $proc = Start-Process -FilePath $chrome -PassThru -Wait -WindowStyle Hidden -ArgumentList @(
    '--headless=new', '--disable-gpu', '--no-sandbox', "--force-device-scale-factor=$Dsf", "--user-data-dir=$udir",
    "--window-size=$W,$H", '--virtual-time-budget=9000', "--screenshot=$png", $url
  )
  Start-Sleep -Milliseconds 800
  if (Test-Path $png) { Write-Output "OK  $($s.name).png" } else { Write-Output "FAIL $($s.name) exit=$($proc.ExitCode)" }
}
Write-Output '=== done ==='
