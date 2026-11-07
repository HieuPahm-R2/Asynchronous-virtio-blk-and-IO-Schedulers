# build_pdf.ps1 — sinh PDF tuần 3 từ Markdown (W3-I02).
#
# Nguồn sự thật là file .md; PDF chỉ là đầu ra dẫn xuất. Không sửa tay PDF.
# Yêu cầu: pandoc >= 3.1 và Chrome/Edge (headless). Chạy từ repo root:
#
#   powershell -ExecutionPolicy Bypass -File docs\week03\tools\build_pdf.ps1
#   powershell -ExecutionPolicy Bypass -File docs\week03\tools\build_pdf.ps1 -All
#
# Mặc định sinh proposal.pdf + report-hieu.pdf; -All sinh thêm interface.pdf
# và lifecycle-review.pdf.

param(
    [switch]$All
)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$weekDir = Join-Path $repoRoot 'docs\week03'
$css = Join-Path $PSScriptRoot 'print.css'

if (-not (Test-Path $css)) { throw "missing CSS: $css" }

$pandoc = (Get-Command pandoc -ErrorAction SilentlyContinue)
if (-not $pandoc) { throw 'pandoc not found in PATH (>= 3.1)' }
$pandoc = $pandoc.Source

$chromeCandidates = @(
    $env:CHROME_PATH,
    'C:\Program Files\Google\Chrome\Application\chrome.exe',
    'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
) | Where-Object { $_ -and (Test-Path $_) }
if (-not $chromeCandidates) { throw 'Chrome/Edge not found; set $env:CHROME_PATH' }
$chrome = $chromeCandidates[0]

$docs = @('proposal', 'report-hieu')
if ($All) { $docs = @('interface', 'lifecycle-review', 'proposal', 'report-hieu') }

$tmp = Join-Path $env:TEMP ('et4290-week03-pdf-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null

foreach ($name in $docs) {
    $md = Join-Path $weekDir "$name.md"
    $pdf = Join-Path $weekDir "$name.pdf"
    if (-not (Test-Path $md)) { throw "missing source: $md" }

    $html = Join-Path $tmp "$name.html"
    Write-Host "== pandoc: $name.md -> $name.html"
    & $pandoc $md -o $html --standalone --embed-resources --css $css `
        --metadata "lang=vi" --metadata "pagetitle=$name" --from markdown `
        "--resource-path=$weekDir"
    if ($LASTEXITCODE -ne 0) { throw "pandoc failed for $name" }

    $uri = ([System.Uri]$html).AbsoluteUri
    Write-Host "== chrome headless: $name.html -> $name.pdf"
    $errFile = Join-Path $tmp "$name.chrome.err"
    $args = @(
        '--headless=new',
        '--disable-gpu',
        '--no-pdf-header-footer',
        '--allow-file-access-from-files',
        '--virtual-time-budget=5000',
        "--print-to-pdf=$pdf",
        $uri
    )
    $proc = Start-Process -FilePath $chrome -ArgumentList $args -Wait -PassThru `
        -NoNewWindow -RedirectStandardError $errFile
    if ($proc.ExitCode -ne 0) {
        Get-Content $errFile -ErrorAction SilentlyContinue | Write-Host
        throw "chrome failed for $name (exit $($proc.ExitCode))"
    }
    if (-not (Test-Path $pdf)) { throw "chrome did not write $pdf" }
    $size = (Get-Item $pdf).Length
    Write-Host ("   OK {0} ({1} bytes)" -f (Split-Path $pdf -Leaf), $size)
}

# Đếm số trang để kiểm tra tiêu chí proposal 2-3 trang (nếu có pypdf).
$py = (Get-Command python -ErrorAction SilentlyContinue)
if ($py) {
    foreach ($name in $docs) {
        $pdf = Join-Path $weekDir "$name.pdf"
        $code = "import sys;from pypdf import PdfReader;r=PdfReader(sys.argv[1]);print('   pages:',len(r.pages))"
        & $py.Source '-c' $code $pdf
    }
}

Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
Write-Host '== done'
