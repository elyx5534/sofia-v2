param(
  [switch]$Apply = $false,
  [int]$MinFlagsPerFile = 3
)
$report = "reports\deadcode.txt"
if(-not (Test-Path $report)){
  Write-Host "Bulunamadı: $report (vulture raporunu önce üretin)" -ForegroundColor Yellow
  exit 1
}
$entries = Get-Content $report | Where-Object { $_ -match "unused " }
$files = @{}
foreach($line in $entries){
  if($line -match "^(?<path>.+?):\d+:\s+unused\s+(?<kind>\w+)\s+'(?<name>[^']+)'"){
    $p=$Matches["path"]; $n=$Matches["name"]
    if(-not $files.ContainsKey($p)){ $files[$p]=@() }
    $files[$p] += $n
  }
}
Write-Host "Aday dosya sayısı:" $files.Keys.Count
foreach($f in $files.Keys){
  $names = $files[$f] | Sort-Object -Unique
  $flagCount = $names.Count
  $isTest = ($f -like "*tests*") -or ($f -like "*__init__*")
  if($isTest){ continue }
  Write-Host ("`n[{0}] flags={1}" -f $f, $flagCount)
  # sembol isimleri başka yerde geçiyor mu?
  $externRefs = 0
  foreach($sym in $names){
    $hits = (Select-String -Path src\**\*.py -Pattern ("`b{0}`b" -f [regex]::Escape($sym)) -NotMatch ($f) ).Count
    if($hits -gt 0){ $externRefs++ }
  }
  Write-Host ("  external-refs: {0}" -f $externRefs)
  if(($flagCount -ge $MinFlagsPerFile) -and ($externRefs -eq 0)){
    $target = Join-Path "deprecated" (Split-Path $f -Leaf)
    if($Apply){
      New-Item -ItemType Directory -Force (Split-Path $target) | Out-Null
      Move-Item -Force $f $target
      Write-Host ("  -> Moved to deprecated\{0}" -f (Split-Path $f -Leaf)) -ForegroundColor Yellow
    } else {
      Write-Host ("  (dry-run) would move -> deprecated\{0}" -f (Split-Path $f -Leaf)) -ForegroundColor DarkYellow
    }
  } else {
    Write-Host "  keep (manual review)"
  }
}
