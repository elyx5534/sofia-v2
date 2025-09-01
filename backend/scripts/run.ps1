# Sofia V2 Realtime DataHub - Windows PowerShell Runner
# One-command startup script for Windows 11

param(
    [Parameter(Mandatory=$false)]
    [string]$Environment = "development",
    
    [Parameter(Mandatory=$false)]
    [switch]$InstallDeps,
    
    [Parameter(Mandatory=$false)]
    [switch]$CreateEnv,
    
    [Parameter(Mandatory=$false)]
    [switch]$Service,
    
    [Parameter(Mandatory=$false)]
    [switch]$Stop
)

# Configuration
$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
$VENV_PATH = Join-Path $PROJECT_ROOT ".venv"
$ACTIVATE_SCRIPT = Join-Path $VENV_PATH "Scripts\Activate.ps1"
$APP_MODULE = "app.main:app"
$DEFAULT_HOST = "0.0.0.0"
$DEFAULT_PORT = 8000

# Colors for output
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"
$Blue = "Cyan"

function Write-ColoredOutput {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

function Test-PythonInstallation {
    try {
        $pythonVersion = python --version 2>$null
        if ($pythonVersion -match "Python 3\.(\d+)\.") {
            $minorVersion = [int]$matches[1]
            if ($minorVersion -ge 8) {
                Write-ColoredOutput "✓ Python found: $pythonVersion" $Green
                return $true
            } else {
                Write-ColoredOutput "✗ Python 3.8+ required, found: $pythonVersion" $Red
                return $false
            }
        }
    }
    catch {
        Write-ColoredOutput "✗ Python not found. Please install Python 3.8+" $Red
        return $false
    }
    return $false
}

function Test-VirtualEnvironment {
    if (Test-Path $ACTIVATE_SCRIPT) {
        Write-ColoredOutput "✓ Virtual environment found" $Green
        return $true
    } else {
        Write-ColoredOutput "! Virtual environment not found" $Yellow
        return $false
    }
}

function New-VirtualEnvironment {
    Write-ColoredOutput "Creating virtual environment..." $Blue
    try {
        python -m venv $VENV_PATH
        if (Test-Path $ACTIVATE_SCRIPT) {
            Write-ColoredOutput "✓ Virtual environment created" $Green
            return $true
        }
    }
    catch {
        Write-ColoredOutput "✗ Failed to create virtual environment" $Red
        return $false
    }
    return $false
}

function Install-Dependencies {
    Write-ColoredOutput "Installing dependencies..." $Blue
    
    # Activate virtual environment
    & $ACTIVATE_SCRIPT
    
    # Upgrade pip
    python -m pip install --upgrade pip
    
    # Install requirements
    $requirementsPath = Join-Path $PROJECT_ROOT "requirements.txt"
    if (Test-Path $requirementsPath) {
        python -m pip install -r $requirementsPath
        if ($LASTEXITCODE -eq 0) {
            Write-ColoredOutput "✓ Dependencies installed successfully" $Green
            return $true
        } else {
            Write-ColoredOutput "✗ Failed to install dependencies" $Red
            return $false
        }
    } else {
        Write-ColoredOutput "✗ requirements.txt not found" $Red
        return $false
    }
}

function Test-Configuration {
    Write-ColoredOutput "Validating configuration..." $Blue
    
    # Check for .env file
    $envPath = Join-Path $PROJECT_ROOT ".env"
    if (-not (Test-Path $envPath)) {
        $envTemplatePath = Join-Path $PROJECT_ROOT ".env.tpl"
        if (Test-Path $envTemplatePath) {
            Write-ColoredOutput "! .env not found, copying from template..." $Yellow
            Copy-Item $envTemplatePath $envPath
            Write-ColoredOutput "✓ .env created from template" $Green
        } else {
            Write-ColoredOutput "✗ .env and .env.tpl not found" $Red
            return $false
        }
    }
    
    # Check for config.yml
    $configPath = Join-Path $PROJECT_ROOT "config.yml"
    if (Test-Path $configPath) {
        Write-ColoredOutput "✓ config.yml found" $Green
    } else {
        Write-ColoredOutput "✗ config.yml not found" $Red
        return $false
    }
    
    return $true
}

function Start-DataHub {
    param([string]$Mode = "development")
    
    Write-ColoredOutput "Starting Sofia V2 DataHub..." $Blue
    
    # Activate virtual environment
    & $ACTIVATE_SCRIPT
    
    # Set environment variables
    $env:PYTHONPATH = $PROJECT_ROOT
    
    # Start based on mode
    if ($Mode -eq "development") {
        # Development mode with reload
        uvicorn $APP_MODULE --host $DEFAULT_HOST --port $DEFAULT_PORT --reload --log-level info
    } else {
        # Production mode
        uvicorn $APP_MODULE --host $DEFAULT_HOST --port $DEFAULT_PORT --workers 1 --log-level info
    }
}

function Stop-DataHub {
    Write-ColoredOutput "Stopping Sofia V2 DataHub..." $Blue
    
    # Find and kill uvicorn processes
    $processes = Get-Process | Where-Object { $_.ProcessName -like "*uvicorn*" -or $_.CommandLine -like "*app.main*" }
    
    if ($processes) {
        foreach ($process in $processes) {
            try {
                Stop-Process -Id $process.Id -Force
                Write-ColoredOutput "✓ Stopped process: $($process.ProcessName) (PID: $($process.Id))" $Green
            }
            catch {
                Write-ColoredOutput "! Could not stop process: $($process.ProcessName)" $Yellow
            }
        }
    } else {
        Write-ColoredOutput "No running DataHub processes found" $Yellow
    }
    
    # Also try to kill by port
    try {
        $netstat = netstat -ano | Select-String ":$DEFAULT_PORT"
        if ($netstat) {
            $pids = $netstat | ForEach-Object { ($_.ToString().Split())[-1] } | Sort-Object -Unique
            foreach ($pid in $pids) {
                if ($pid -match '^\d+$') {
                    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                    Write-ColoredOutput "✓ Stopped process on port $DEFAULT_PORT (PID: $pid)" $Green
                }
            }
        }
    }
    catch {
        # Ignore errors
    }
}

function Show-Usage {
    Write-ColoredOutput @"

Sofia V2 Realtime DataHub - Windows Runner

USAGE:
    .\run.ps1 [OPTIONS]

OPTIONS:
    -Environment <env>    Set environment (development/production) [default: development]
    -InstallDeps         Install Python dependencies
    -CreateEnv           Create virtual environment
    -Service             Install/start as Windows service
    -Stop                Stop running DataHub

EXAMPLES:
    .\run.ps1                           # Start in development mode
    .\run.ps1 -CreateEnv -InstallDeps   # Setup environment and dependencies
    .\run.ps1 -Environment production    # Start in production mode
    .\run.ps1 -Stop                     # Stop DataHub
    .\run.ps1 -Service                  # Install as Windows service

"@ $Blue
}

# Main execution
function Main {
    Write-ColoredOutput "`n🚀 Sofia V2 Realtime DataHub - Windows Runner" $Blue
    Write-ColoredOutput "=" * 50 $Blue
    
    # Handle stop command
    if ($Stop) {
        Stop-DataHub
        return
    }
    
    # Check Python installation
    if (-not (Test-PythonInstallation)) {
        Write-ColoredOutput "Please install Python 3.8+ from https://python.org" $Red
        exit 1
    }
    
    # Handle service installation
    if ($Service) {
        $serviceScript = Join-Path $PSScriptRoot "install_service.ps1"
        if (Test-Path $serviceScript) {
            & $serviceScript
        } else {
            Write-ColoredOutput "✗ Service installer not found: $serviceScript" $Red
            exit 1
        }
        return
    }
    
    # Create virtual environment if requested or missing
    if ($CreateEnv -or -not (Test-VirtualEnvironment)) {
        if (-not (New-VirtualEnvironment)) {
            exit 1
        }
    }
    
    # Install dependencies if requested
    if ($InstallDeps) {
        if (-not (Install-Dependencies)) {
            exit 1
        }
    }
    
    # Validate configuration
    if (-not (Test-Configuration)) {
        Write-ColoredOutput "`nPlease check your configuration files and try again." $Red
        exit 1
    }
    
    # Check if virtual environment has required packages
    & $ACTIVATE_SCRIPT
    $uvicornCheck = python -c "import uvicorn" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-ColoredOutput "! Required packages missing, installing..." $Yellow
        if (-not (Install-Dependencies)) {
            exit 1
        }
    }
    
    Write-ColoredOutput "`n✓ All checks passed! Starting DataHub..." $Green
    Write-ColoredOutput "Environment: $Environment" $Blue
    Write-ColoredOutput "Host: $DEFAULT_HOST" $Blue
    Write-ColoredOutput "Port: $DEFAULT_PORT" $Blue
    Write-ColoredOutput "`nPress Ctrl+C to stop`n" $Yellow
    
    # Start the DataHub
    try {
        Start-DataHub -Mode $Environment
    }
    catch {
        Write-ColoredOutput "`n✗ DataHub stopped unexpectedly" $Red
        Write-ColoredOutput "Error: $($_.Exception.Message)" $Red
        exit 1
    }
}

# Show usage if no parameters
if ($args.Count -eq 0 -and -not $PSBoundParameters.Count) {
    Show-Usage
}

# Run main function
Main