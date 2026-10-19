#Requires -Version 5.1
<#
.SYNOPSIS
    Cài môi trường phát triển ET4290 trên Windows: WSL2 + Ubuntu 24.04 + toolchain RISC-V/QEMU.

.DESCRIPTION
    Script tự động hoá đúng môi trường được dùng cho dự án (xem docs/environment.md):
      1. Kiểm tra WSL2 sẵn sàng.
      2. Tải Ubuntu 24.04 WSL rootfs từ cloud-images.ubuntu.com và kiểm tra SHA256.
      3. Import thành distro WSL2 (mặc định tên "Ubuntu-24.04", lưu ở E:\wsl\Ubuntu-24.04).
      4. Cấu hình user ubuntu + chạy scripts/setup-env.sh (gcc/binutils RISC-V, QEMU,
         gdb-multiarch, Python, công cụ đo).
      5. Chạy scripts/check-env.sh để build + boot thử xv6.

    Nếu distro cùng tên đã tồn tại, script bỏ qua bước tải/import và chỉ cài/kiểm tra
    package trong distro đó.

.PARAMETER DistroName
    Tên distro WSL. Mặc định "Ubuntu-24.04".

.PARAMETER InstallPath
    Thư mục lưu filesystem của distro (nên ở ổ còn nhiều dung lượng).

.PARAMETER DownloadDir
    Thư mục tải rootfs. Mặc định %TEMP%\et4290-wsl.

.PARAMETER SkipPackages
    Chỉ import + cấu hình, không apt-get install (hữu ích khi test script).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\wsl\import-ubuntu.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\wsl\import-ubuntu.ps1 -DistroName Ubuntu-ET4290 -InstallPath E:\wsl\Ubuntu-ET4290
#>
[CmdletBinding()]
param(
    [string]$DistroName = 'Ubuntu-24.04',
    [string]$InstallPath = 'E:\wsl\Ubuntu-24.04',
    [string]$DownloadDir = (Join-Path $env:TEMP 'et4290-wsl'),
    [switch]$SkipPackages
)

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$RootfsUrl = 'https://cloud-images.ubuntu.com/wsl/releases/24.04/current/ubuntu-noble-wsl-amd64-wsl.rootfs.tar.gz'
$SumsUrl = 'https://cloud-images.ubuntu.com/wsl/releases/24.04/current/SHA256SUMS'
$RootfsName = 'ubuntu-noble-wsl-amd64-wsl.rootfs.tar.gz'

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "    [ OK ] $Message" -ForegroundColor Green
}

function ConvertTo-WslPath([string]$WindowsPath) {
    $full = [System.IO.Path]::GetFullPath($WindowsPath)
    $drive = $full.Substring(0, 1).ToLowerInvariant()
    return "/mnt/$drive" + ($full.Substring(2) -replace '\\', '/')
}

function Invoke-WslScript {
    param(
        [string]$Distro,
        [string]$User,
        [string]$ScriptPath,
        [string[]]$Arguments = @()
    )
    $shellCommand = "bash " + "'$ScriptPath'"
    foreach ($a in $Arguments) {
        $shellCommand += " " + "'$a'"
    }
    if ($User) {
        wsl.exe -d $Distro -u $User -e bash -c $shellCommand
    }
    else {
        wsl.exe -d $Distro -e bash -c $shellCommand
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Lệnh trong WSL thất bại (exit $LASTEXITCODE): $ScriptPath"
    }
}

function Get-WslDistros {
    $raw = (wsl.exe -l -q) 2>$null
    return @($raw -replace "`0", '' | Where-Object { $_.Trim() -ne '' } | ForEach-Object { $_.Trim() })
}

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw 'Không tìm thấy wsl.exe. Bật WSL2 trước: mở PowerShell admin và chạy "wsl --install --no-distribution".'
}

Write-Step 'Kiểm tra WSL'
$wslStatus = (((wsl.exe --status) 2>&1 | Out-String) -replace "`0", '')
if ($wslStatus -match 'WSL version') {
    Write-Ok (($wslStatus -split "`n" | Where-Object { $_ -match 'WSL version|Kernel version' }) -join '; ')
}
else {
    Write-Host '    WSL2 chưa sẵn sàng. Chạy PowerShell quản trị: wsl --update' -ForegroundColor Yellow
}

$wslRepo = ConvertTo-WslPath $RepoRoot
Write-Host "    workspace Windows: $RepoRoot"
Write-Host "    workspace trong WSL: $wslRepo"

$distros = Get-WslDistros
$exists = $distros -contains $DistroName

if (-not $exists) {
    New-Item -ItemType Directory -Force -Path $DownloadDir | Out-Null
    $tarball = Join-Path $DownloadDir $RootfsName

    if (-not (Test-Path $tarball)) {
        Write-Step "Tải Ubuntu 24.04 WSL rootfs (~340 MiB) vào $DownloadDir"
        curl.exe -L --fail --retry 3 --retry-delay 2 -o $tarball $RootfsUrl
        if ($LASTEXITCODE -ne 0) { throw "Tải rootfs thất bại (curl exit $LASTEXITCODE)" }
    }
    else {
        Write-Ok "đã có sẵn $tarball"
    }

    Write-Step 'Kiểm tra SHA256'
    $content = (Invoke-WebRequest -Uri $SumsUrl -UseBasicParsing -TimeoutSec 120).Content
    if ($content -is [byte[]]) {
        $content = [System.Text.Encoding]::UTF8.GetString($content)
    }
    $expected = (($content -split "`n") | Where-Object { $_ -match [regex]::Escape($RootfsName) } | Select-Object -First 1) -split '\s+' | Select-Object -First 1
    $actual = (Get-FileHash -Path $tarball -Algorithm SHA256).Hash.ToLowerInvariant()
    if (-not $expected) { throw "Không tìm thấy checksum của $RootfsName trong SHA256SUMS" }
    if ($expected.ToLowerInvariant() -ne $actual) {
        throw "SHA256 không khớp! expected=$expected actual=$actual (xoá file tải lại)"
    }
    Write-Ok "SHA256 khớp ($actual)"

    Write-Step "Import distro '$DistroName' vào $InstallPath"
    New-Item -ItemType Directory -Force -Path $InstallPath | Out-Null
    wsl.exe --import $DistroName $InstallPath $tarball --version 2
    if ($LASTEXITCODE -ne 0) { throw "wsl --import thất bại (exit $LASTEXITCODE)" }

    # Lần khởi động đầu tiên có thể chậm; chờ distro trả lời trước khi cấu hình.
    Write-Step 'Khởi động thử distro lần đầu'
    for ($i = 0; $i -lt 20; $i++) {
        wsl.exe -d $DistroName -u root -e true 2>$null
        if ($LASTEXITCODE -eq 0) { break }
        Start-Sleep -Seconds 2
    }
    if ($LASTEXITCODE -ne 0) { throw "Không khởi động được distro '$DistroName'" }
    Write-Ok "đã import $DistroName"
}
else {
    Write-Ok "distro '$DistroName' đã tồn tại — bỏ qua tải/import"
}

Write-Step 'Cấu hình distro (default user, sudo, git safe.directory)'
Invoke-WslScript -Distro $DistroName -User 'root' -ScriptPath "$wslRepo/scripts/wsl/wsl-init.sh"
wsl.exe --terminate $DistroName | Out-Null

if (-not $SkipPackages) {
    Write-Step 'Cài toolchain RISC-V + QEMU + công cụ đo (apt)'
    Invoke-WslScript -Distro $DistroName -User 'root' -ScriptPath "$wslRepo/scripts/setup-env.sh"

    Write-Step 'Kiểm tra môi trường (build + boot smoke)'
    Invoke-WslScript -Distro $DistroName -User 'ubuntu' -ScriptPath "$wslRepo/scripts/check-env.sh"
}
else {
    Write-Host '    (bỏ qua cài package theo -SkipPackages)' -ForegroundColor Yellow
}

Write-Host ''
Write-Host '==> Hoàn tất. Dùng hằng ngày:' -ForegroundColor Cyan
Write-Host "    wsl -d $DistroName"
Write-Host "    cd $wslRepo"
Write-Host '    make qemu            # boot xv6 (Ctrl-A rồi X để thoát)'
Write-Host '    make test            # chạy test suite'
Write-Host '    make baseline        # ghi baseline stock vào results/baseline/'
