# Render every slide of a .pptx to PNG through PowerPoint COM (hidden instance started and closed by this script only).
param(
    [Parameter(Mandatory = $true)][string]$Deck,
    [Parameter(Mandatory = $true)][string]$OutDir,
    [string]$Prefix = "s"
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force $OutDir | Out-Null
Get-ChildItem $OutDir -Filter "$Prefix-*.png" | Remove-Item -Force -Confirm:$false

$before = @(Get-Process POWERPNT -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
$app = New-Object -ComObject PowerPoint.Application
$pres = $null
try {
    $pres = $app.Presentations.Open($Deck, $true, $false, $false)   # ReadOnly, Untitled=false, WithWindow=false
    $n = $pres.Slides.Count
    for ($i = 1; $i -le $n; $i++) {
        $file = Join-Path $OutDir ("{0}-{1:00}.png" -f $Prefix, $i)
        $pres.Slides.Item($i).Export($file, "PNG", 1600, 900)
    }
    Write-Output "exported $n slides to $OutDir"
}
finally {
    if ($pres -ne $null) { $pres.Close() }
    $app.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)
    [GC]::Collect(); [GC]::WaitForPendingFinalizers()
    # Close only PowerPoint processes that did not exist before this script started.
    Get-Process POWERPNT -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id } | ForEach-Object {
        try { Stop-Process -Id $_.Id -Force -Confirm:$false -ErrorAction Stop } catch {}
    }
}
