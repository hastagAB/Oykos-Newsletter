# Vibe Check Script - Oykos Newsletter Engine
# Run all quality gates. CI runs this same script.
# Usage: .\scripts\vibe-check.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== Oykos Vibe Check ===" -ForegroundColor Cyan

# 1. Lint
Write-Host "`n[1/5] Linting with ruff..." -ForegroundColor Yellow
ruff check src/ tests/
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: Lint errors found" -ForegroundColor Red; exit 1 }
Write-Host "PASS" -ForegroundColor Green

# 2. Format check
Write-Host "`n[2/5] Format check with ruff..." -ForegroundColor Yellow
ruff format --check src/ tests/
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: Formatting issues found" -ForegroundColor Red; exit 1 }
Write-Host "PASS" -ForegroundColor Green

# 3. Type check
Write-Host "`n[3/5] Type checking with pyright..." -ForegroundColor Yellow
pyright src/
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: Type errors found" -ForegroundColor Red; exit 1 }
Write-Host "PASS" -ForegroundColor Green

# 4. Tests with coverage
Write-Host "`n[4/5] Running tests with coverage..." -ForegroundColor Yellow
pytest tests/ --cov=src/oykos --cov-report=term-missing --cov-fail-under=90 -q
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: Tests failed or coverage below 90%" -ForegroundColor Red; exit 1 }
Write-Host "PASS" -ForegroundColor Green

# 5. Security audit
Write-Host "`n[5/5] Security scan..." -ForegroundColor Yellow
ruff check src/ --select S
if ($LASTEXITCODE -ne 0) { Write-Host "WARN: Security findings (review manually)" -ForegroundColor Yellow }
else { Write-Host "PASS" -ForegroundColor Green }

Write-Host "`n=== All gates passed ===" -ForegroundColor Cyan
