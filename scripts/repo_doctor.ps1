# Ruff/Black/Mypy/Tests + Import-Linter + Deadcode raporu
& ..\.venv\Scripts\ruff check . --fix
& ..\.venv\Scripts\black src tests
& ..\.venv\Scripts\mypy src || Write-Host "mypy warnings"
& ..\.venv\Scripts\pytest -q
# deadcode yeniden üret (vulture veya ruff --extend-select=F401,F811 ile)
try {
  pip show vulture | Out-Null
} catch {
  pip install vulture | Out-Null
}
vulture src --min-confidence 70 > .\reports\deadcode.txt
Write-Host "Repo doktor tamam. reports\deadcode.txt güncellendi." -ForegroundColor Green
