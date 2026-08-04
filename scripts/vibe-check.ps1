# Vibe Check Script - Oykos Newsletter Engine
# Run all quality gates. CI runs this same script.
# Usage: .\scripts\vibe-check.ps1

$ErrorActionPreference = "Stop"

$py = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }

Write-Host "=== Oykos Vibe Check ===" -ForegroundColor Cyan

# 1. Lint
Write-Host "`n[1/5] Linting with ruff..." -ForegroundColor Yellow
& $py -m ruff check src/ tests/
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: Lint errors found" -ForegroundColor Red; exit 1 }
Write-Host "PASS" -ForegroundColor Green

# 2. Format drift (advisory)
# Not a hard gate: `ruff format` would explode the source registry and the ORM
# table declarations, which are deliberately one entry per line. Import order and
# line length are already enforced by `ruff check` above.
Write-Host "`n[2/5] Format drift (advisory)..." -ForegroundColor Yellow
& $py -m ruff format --check src/ tests/ 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "INFO: formatter would reflow some files (not a gate)" -ForegroundColor DarkGray }
else { Write-Host "PASS" -ForegroundColor Green }

# 3. Type check
Write-Host "`n[3/5] Type checking with pyright..." -ForegroundColor Yellow
& $py -m pyright src/
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: Type errors found" -ForegroundColor Red; exit 1 }
Write-Host "PASS" -ForegroundColor Green

# 4. Tests with coverage
Write-Host "`n[4/5] Running tests with coverage..." -ForegroundColor Yellow
& $py -m pytest tests/ --cov=src/oykos --cov-report=term-missing --cov-fail-under=65 -q
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: Tests failed or coverage below 65%" -ForegroundColor Red; exit 1 }
Write-Host "PASS" -ForegroundColor Green

# 5. Security audit
Write-Host "`n[5/5] Security scan..." -ForegroundColor Yellow
& $py -m ruff check src/ --select S
if ($LASTEXITCODE -ne 0) { Write-Host "WARN: Security findings (review manually)" -ForegroundColor Yellow }
else { Write-Host "PASS" -ForegroundColor Green }

Write-Host "`n=== All gates passed ===" -ForegroundColor Cyan
