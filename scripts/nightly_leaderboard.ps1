# Nightly Leaderboard Script - Sofia V2
# Runs grid search on multiple strategies and creates leaderboard report

param(
    [string]$Mode = "backtest",  # backtest or live
    [string]$OutputDir = "reports",
    [switch]$Email = $false
)

$ErrorActionPreference = "Stop"
$timestamp = Get-Date -Format "yyyy-MM-dd"
$reportFile = "$OutputDir/leaderboard_$timestamp.json"
$csvFile = "$OutputDir/leaderboard_$timestamp.csv"

# Ensure output directory exists
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
New-Item -ItemType Directory -Force -Path logs | Out-Null

Write-Host "=== Sofia V2 Nightly Leaderboard ===" -ForegroundColor Cyan
Write-Host "Date: $timestamp"
Write-Host "Mode: $Mode"

# Activate virtual environment
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "Virtual environment not found. Creating..." -ForegroundColor Yellow
    python -m venv .venv
    & .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
}

# Define strategies to test
$strategies = @(
    @{
        Name = "sma_cross"
        DisplayName = "SMA Crossover"
        Params = @{
            fast = @(10, 20, 30, 40)
            slow = @(40, 50, 60, 80, 100)
        }
    },
    @{
        Name = "rsi_revert"
        DisplayName = "RSI Mean Reversion"
        Params = @{
            period = @(10, 14, 20)
            oversold = @(20, 25, 30, 35)
            overbought = @(65, 70, 75, 80)
        }
    },
    @{
        Name = "breakout"
        DisplayName = "Channel Breakout"
        Params = @{
            period = @(15, 20, 25, 30)
        }
    }
)

# Define test pairs
$pairs = @("BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT")

# Results collection
$leaderboard = @()
$startTime = Get-Date

Write-Host "`nStarting grid search for all strategies..." -ForegroundColor Green

foreach ($pair in $pairs) {
    Write-Host "`nTesting $pair..." -ForegroundColor Yellow
    
    foreach ($strategy in $strategies) {
        Write-Host "  Strategy: $($strategy.DisplayName)" -NoNewline
        
        # Prepare API request
        $body = @{
            symbol = $pair
            timeframe = "1h"
            start = (Get-Date).AddDays(-30).ToString("yyyy-MM-dd")
            end = (Get-Date).ToString("yyyy-MM-dd")
            strategy = $strategy.Name
            param_grid = $strategy.Params
        } | ConvertTo-Json -Depth 3
        
        try {
            # Call grid search API
            $response = Invoke-RestMethod -Uri "http://localhost:8000/api/backtest/grid" `
                -Method POST `
                -ContentType "application/json" `
                -Body $body `
                -TimeoutSec 60
            
            if ($response.best_params) {
                $result = @{
                    Timestamp = $timestamp
                    Pair = $pair
                    Strategy = $strategy.DisplayName
                    BestParams = $response.best_params
                    Sharpe = [math]::Round($response.best_sharpe, 3)
                    Return = [math]::Round($response.best_result.stats.total_return, 2)
                    MaxDD = [math]::Round($response.best_result.stats.max_drawdown, 2)
                    WinRate = [math]::Round($response.best_result.stats.win_rate, 2)
                    Trades = $response.best_result.stats.total_trades
                    Score = [math]::Round($response.best_sharpe * 100 - $response.best_result.stats.max_drawdown, 2)
                }
                
                $leaderboard += $result
                Write-Host " - Sharpe: $($result.Sharpe), Return: $($result.Return)%" -ForegroundColor Green
            } else {
                Write-Host " - No valid results" -ForegroundColor Red
            }
        } catch {
            Write-Host " - Error: $_" -ForegroundColor Red
        }
        
        # Rate limit
        Start-Sleep -Seconds 2
    }
}

# Sort leaderboard by score
$leaderboard = $leaderboard | Sort-Object -Property Score -Descending

Write-Host "`n=== LEADERBOARD TOP 10 ===" -ForegroundColor Cyan
$topResults = $leaderboard | Select-Object -First 10

$rank = 1
foreach ($entry in $topResults) {
    Write-Host "$rank. $($entry.Strategy) on $($entry.Pair)" -ForegroundColor Yellow
    Write-Host "   Score: $($entry.Score) | Sharpe: $($entry.Sharpe) | Return: $($entry.Return)% | MaxDD: $($entry.MaxDD)%"
    Write-Host "   Params: $($entry.BestParams | ConvertTo-Json -Compress)"
    $rank++
}

# Save JSON report
$report = @{
    timestamp = $timestamp
    mode = $Mode
    duration_minutes = [math]::Round(((Get-Date) - $startTime).TotalMinutes, 2)
    total_tests = $leaderboard.Count
    pairs_tested = $pairs
    strategies_tested = $strategies.Count
    leaderboard = $leaderboard
    top_performer = $leaderboard[0]
    summary = @{
        avg_sharpe = [math]::Round(($leaderboard | Measure-Object -Property Sharpe -Average).Average, 3)
        avg_return = [math]::Round(($leaderboard | Measure-Object -Property Return -Average).Average, 2)
        best_sharpe = ($leaderboard | Measure-Object -Property Sharpe -Maximum).Maximum
        best_return = ($leaderboard | Measure-Object -Property Return -Maximum).Maximum
    }
}

$report | ConvertTo-Json -Depth 5 | Out-File $reportFile
Write-Host "`nJSON report saved to: $reportFile" -ForegroundColor Green

# Save CSV for Excel
$leaderboard | Export-Csv -Path $csvFile -NoTypeInformation
Write-Host "CSV report saved to: $csvFile" -ForegroundColor Green

# Run paper trading with top strategy
if ($Mode -eq "live") {
    Write-Host "`nStarting paper trading with top strategy..." -ForegroundColor Cyan
    $topEntry = $leaderboard[0]
    
    $paperBody = @{
        session = $topEntry.Strategy.ToLower().Replace(" ", "_")
        symbol = $topEntry.Pair
        params = $topEntry.BestParams
    } | ConvertTo-Json
    
    try {
        $paperResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/paper/start" `
            -Method POST `
            -ContentType "application/json" `
            -Body $paperBody
        
        Write-Host "Paper trading started: $($paperResponse.status)" -ForegroundColor Green
    } catch {
        Write-Host "Failed to start paper trading: $_" -ForegroundColor Red
    }
}

# Email report (if enabled)
if ($Email) {
    Write-Host "`nPreparing email report..." -ForegroundColor Yellow
    
    $emailBody = @"
Sofia V2 Nightly Leaderboard Report
====================================
Date: $timestamp
Duration: $($report.duration_minutes) minutes
Total Tests: $($report.total_tests)

TOP PERFORMER:
--------------
Strategy: $($report.top_performer.Strategy)
Pair: $($report.top_performer.Pair)
Score: $($report.top_performer.Score)
Sharpe: $($report.top_performer.Sharpe)
Return: $($report.top_performer.Return)%
Max Drawdown: $($report.top_performer.MaxDD)%

SUMMARY:
--------
Average Sharpe: $($report.summary.avg_sharpe)
Average Return: $($report.summary.avg_return)%
Best Sharpe: $($report.summary.best_sharpe)
Best Return: $($report.summary.best_return)%

Full report attached.
"@
    
    Write-Host $emailBody
    Write-Host "`nEmail functionality would send to configured recipients" -ForegroundColor Yellow
}

Write-Host "`n=== Leaderboard Complete ===" -ForegroundColor Green
Write-Host "Total time: $($report.duration_minutes) minutes"

# Schedule next run (Windows Task Scheduler)
$trigger = New-ScheduledTaskTrigger -Daily -At "02:00AM"
$action = New-ScheduledTaskAction -Execute "PowerShell.exe" `
    -Argument "-ExecutionPolicy Bypass -File `"$PSScriptRoot\nightly_leaderboard.ps1`" -Mode live"

if (-not (Get-ScheduledTask -TaskName "SofiaV2NightlyLeaderboard" -ErrorAction SilentlyContinue)) {
    Register-ScheduledTask -TaskName "SofiaV2NightlyLeaderboard" `
        -Trigger $trigger `
        -Action $action `
        -Description "Sofia V2 nightly strategy leaderboard and optimization" `
        -RunLevel Highest
    
    Write-Host "`nScheduled task created for nightly runs at 2:00 AM" -ForegroundColor Cyan
}