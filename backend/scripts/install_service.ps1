# Sofia V2 Realtime DataHub - Windows Service Installer
# Install and manage DataHub as Windows Service using NSSM

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("install", "uninstall", "start", "stop", "restart", "status")]
    [string]$Action = "install",
    
    [Parameter(Mandatory=$false)]
    [string]$ServiceName = "Sofia-DataHub",
    
    [Parameter(Mandatory=$false)]
    [switch]$Force
)

# Configuration
$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
$VENV_PATH = Join-Path $PROJECT_ROOT ".venv"
$PYTHON_EXE = Join-Path $VENV_PATH "Scripts\python.exe"
$APP_MODULE = "app.main:app"
$SERVICE_DESCRIPTION = "Sofia V2 Realtime Crypto DataHub Service"

# NSSM Configuration
$NSSM_URL = "https://nssm.cc/release/nssm-2.24.zip"
$NSSM_DIR = Join-Path $env:LOCALAPPDATA "Sofia-DataHub\nssm"
$NSSM_EXE = Join-Path $NSSM_DIR "win64\nssm.exe"

# Colors for output
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"
$Blue = "Cyan"

function Write-ColoredOutput {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Install-NSSM {
    if (Test-Path $NSSM_EXE) {
        Write-ColoredOutput "✓ NSSM already installed" $Green
        return $true
    }
    
    Write-ColoredOutput "Downloading NSSM..." $Blue
    
    try {
        # Create directory
        $nssmParentDir = Split-Path -Parent $NSSM_DIR
        if (-not (Test-Path $nssmParentDir)) {
            New-Item -ItemType Directory -Path $nssmParentDir -Force | Out-Null
        }
        
        # Download NSSM
        $tempZip = Join-Path $env:TEMP "nssm.zip"
        Invoke-WebRequest -Uri $NSSM_URL -OutFile $tempZip
        
        # Extract
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::ExtractToDirectory($tempZip, $NSSM_DIR)
        
        # Move files to correct location
        $extractedDir = Get-ChildItem -Path $NSSM_DIR -Directory | Where-Object { $_.Name -like "nssm-*" } | Select-Object -First 1
        if ($extractedDir) {
            $sourceDir = $extractedDir.FullName
            Get-ChildItem -Path $sourceDir -Recurse | Move-Item -Destination $NSSM_DIR -Force
            Remove-Item -Path $sourceDir -Recurse -Force
        }
        
        # Clean up
        Remove-Item -Path $tempZip -Force
        
        if (Test-Path $NSSM_EXE) {
            Write-ColoredOutput "✓ NSSM installed successfully" $Green
            return $true
        } else {
            Write-ColoredOutput "✗ NSSM installation failed" $Red
            return $false
        }
    }
    catch {
        Write-ColoredOutput "✗ Failed to download/install NSSM: $($_.Exception.Message)" $Red
        return $false
    }
}

function Test-ServiceExists {
    try {
        $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        return $service -ne $null
    }
    catch {
        return $false
    }
}

function Install-Service {
    Write-ColoredOutput "Installing Sofia V2 DataHub as Windows Service..." $Blue
    
    # Check if service already exists
    if (Test-ServiceExists) {
        if ($Force) {
            Write-ColoredOutput "Service exists, removing first..." $Yellow
            Uninstall-Service
        } else {
            Write-ColoredOutput "✗ Service '$ServiceName' already exists. Use -Force to reinstall." $Red
            return $false
        }
    }
    
    # Validate Python environment
    if (-not (Test-Path $PYTHON_EXE)) {
        Write-ColoredOutput "✗ Python executable not found: $PYTHON_EXE" $Red
        Write-ColoredOutput "Please run .\run.ps1 -CreateEnv -InstallDeps first" $Yellow
        return $false
    }
    
    try {
        # Install service using NSSM
        $uvicornPath = Join-Path $VENV_PATH "Scripts\uvicorn.exe"
        if (-not (Test-Path $uvicornPath)) {
            Write-ColoredOutput "✗ Uvicorn not found: $uvicornPath" $Red
            return $false
        }
        
        # Create service
        & $NSSM_EXE install $ServiceName $uvicornPath
        
        # Configure service parameters
        & $NSSM_EXE set $ServiceName Parameters "$APP_MODULE --host 0.0.0.0 --port 8000 --workers 1"
        & $NSSM_EXE set $ServiceName DisplayName "Sofia V2 DataHub"
        & $NSSM_EXE set $ServiceName Description $SERVICE_DESCRIPTION
        & $NSSM_EXE set $ServiceName Start SERVICE_AUTO_START
        
        # Set working directory
        & $NSSM_EXE set $ServiceName AppDirectory $PROJECT_ROOT
        
        # Set environment
        & $NSSM_EXE set $ServiceName AppEnvironmentExtra "PYTHONPATH=$PROJECT_ROOT"
        
        # Configure logging
        $logDir = Join-Path $PROJECT_ROOT "logs"
        if (-not (Test-Path $logDir)) {
            New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        }
        
        & $NSSM_EXE set $ServiceName AppStdout (Join-Path $logDir "service_stdout.log")
        & $NSSM_EXE set $ServiceName AppStderr (Join-Path $logDir "service_stderr.log")
        & $NSSM_EXE set $ServiceName AppRotateFiles 1
        & $NSSM_EXE set $ServiceName AppRotateOnline 1
        & $NSSM_EXE set $ServiceName AppRotateSeconds 86400  # Rotate daily
        & $NSSM_EXE set $ServiceName AppRotateBytes 10485760  # 10MB
        
        # Set service dependencies (optional)
        # & $NSSM_EXE set $ServiceName DependOnService "Tcpip"
        
        Write-ColoredOutput "✓ Service '$ServiceName' installed successfully" $Green
        Write-ColoredOutput "Logs will be written to: $logDir" $Blue
        
        # Ask to start service
        $startService = Read-Host "Start the service now? (y/N)"
        if ($startService -eq 'y' -or $startService -eq 'Y') {
            Start-ServiceInstance
        }
        
        return $true
    }
    catch {
        Write-ColoredOutput "✗ Failed to install service: $($_.Exception.Message)" $Red
        return $false
    }
}

function Uninstall-Service {
    Write-ColoredOutput "Uninstalling Sofia V2 DataHub service..." $Blue
    
    if (-not (Test-ServiceExists)) {
        Write-ColoredOutput "! Service '$ServiceName' does not exist" $Yellow
        return $true
    }
    
    try {
        # Stop service first
        Stop-ServiceInstance -Quiet
        
        # Remove service
        & $NSSM_EXE remove $ServiceName confirm
        
        Write-ColoredOutput "✓ Service '$ServiceName' uninstalled successfully" $Green
        return $true
    }
    catch {
        Write-ColoredOutput "✗ Failed to uninstall service: $($_.Exception.Message)" $Red
        return $false
    }
}

function Start-ServiceInstance {
    if (-not (Test-ServiceExists)) {
        Write-ColoredOutput "✗ Service '$ServiceName' does not exist" $Red
        return $false
    }
    
    Write-ColoredOutput "Starting service '$ServiceName'..." $Blue
    
    try {
        Start-Service -Name $ServiceName
        Start-Sleep -Seconds 2
        
        $service = Get-Service -Name $ServiceName
        if ($service.Status -eq 'Running') {
            Write-ColoredOutput "✓ Service started successfully" $Green
            Write-ColoredOutput "DataHub is now running at http://localhost:8000" $Blue
            return $true
        } else {
            Write-ColoredOutput "✗ Service failed to start (Status: $($service.Status))" $Red
            return $false
        }
    }
    catch {
        Write-ColoredOutput "✗ Failed to start service: $($_.Exception.Message)" $Red
        return $false
    }
}

function Stop-ServiceInstance {
    param([switch]$Quiet)
    
    if (-not (Test-ServiceExists)) {
        if (-not $Quiet) {
            Write-ColoredOutput "! Service '$ServiceName' does not exist" $Yellow
        }
        return $true
    }
    
    if (-not $Quiet) {
        Write-ColoredOutput "Stopping service '$ServiceName'..." $Blue
    }
    
    try {
        Stop-Service -Name $ServiceName -Force
        
        if (-not $Quiet) {
            Write-ColoredOutput "✓ Service stopped successfully" $Green
        }
        return $true
    }
    catch {
        if (-not $Quiet) {
            Write-ColoredOutput "✗ Failed to stop service: $($_.Exception.Message)" $Red
        }
        return $false
    }
}

function Restart-ServiceInstance {
    Write-ColoredOutput "Restarting service '$ServiceName'..." $Blue
    
    if (Stop-ServiceInstance -Quiet) {
        Start-Sleep -Seconds 2
        return Start-ServiceInstance
    }
    return $false
}

function Get-ServiceStatus {
    if (-not (Test-ServiceExists)) {
        Write-ColoredOutput "Service '$ServiceName' is not installed" $Yellow
        return
    }
    
    try {
        $service = Get-Service -Name $ServiceName
        Write-ColoredOutput "Service: $($service.Name)" $Blue
        Write-ColoredOutput "Status: $($service.Status)" $(if ($service.Status -eq 'Running') { $Green } else { $Red })
        Write-ColoredOutput "Start Type: $($service.StartType)" $Blue
        
        if ($service.Status -eq 'Running') {
            Write-ColoredOutput "DataHub is available at: http://localhost:8000" $Green
            Write-ColoredOutput "Health check: http://localhost:8000/health" $Blue
            Write-ColoredOutput "Metrics: http://localhost:8000/metrics" $Blue
        }
    }
    catch {
        Write-ColoredOutput "✗ Failed to get service status: $($_.Exception.Message)" $Red
    }
}

function Show-Usage {
    Write-ColoredOutput @"

Sofia V2 DataHub - Windows Service Manager

USAGE:
    .\install_service.ps1 [OPTIONS]

ACTIONS:
    install      Install DataHub as Windows service
    uninstall    Remove the Windows service
    start        Start the service
    stop         Stop the service
    restart      Restart the service
    status       Show service status

OPTIONS:
    -ServiceName <name>    Custom service name [default: Sofia-DataHub]
    -Force                 Force reinstall if service exists

EXAMPLES:
    .\install_service.ps1                    # Install and configure service
    .\install_service.ps1 -Action start      # Start the service
    .\install_service.ps1 -Action status     # Show service status
    .\install_service.ps1 -Action uninstall  # Remove service

NOTES:
    - Requires Administrator privileges
    - Automatically downloads and configures NSSM
    - Service logs are written to 'logs' directory
    - Service runs DataHub on http://localhost:8000

"@ $Blue
}

# Main execution
function Main {
    Write-ColoredOutput "`n🛠️  Sofia V2 DataHub - Service Manager" $Blue
    Write-ColoredOutput "=" * 50 $Blue
    
    # Check administrator privileges
    if (-not (Test-Administrator)) {
        Write-ColoredOutput "✗ Administrator privileges required" $Red
        Write-ColoredOutput "Please run PowerShell as Administrator" $Yellow
        exit 1
    }
    
    # Install NSSM if needed
    if (-not (Install-NSSM)) {
        exit 1
    }
    
    # Execute requested action
    switch ($Action.ToLower()) {
        "install" {
            if (Install-Service) {
                Write-ColoredOutput "`n✓ Service installation completed" $Green
            } else {
                exit 1
            }
        }
        
        "uninstall" {
            if (Uninstall-Service) {
                Write-ColoredOutput "`n✓ Service uninstallation completed" $Green
            } else {
                exit 1
            }
        }
        
        "start" {
            if (Start-ServiceInstance) {
                Write-ColoredOutput "`n✓ Service started successfully" $Green
            } else {
                exit 1
            }
        }
        
        "stop" {
            if (Stop-ServiceInstance) {
                Write-ColoredOutput "`n✓ Service stopped successfully" $Green
            } else {
                exit 1
            }
        }
        
        "restart" {
            if (Restart-ServiceInstance) {
                Write-ColoredOutput "`n✓ Service restarted successfully" $Green
            } else {
                exit 1
            }
        }
        
        "status" {
            Get-ServiceStatus
        }
        
        default {
            Write-ColoredOutput "✗ Unknown action: $Action" $Red
            Show-Usage
            exit 1
        }
    }
}

# Show usage if help requested
if ($args -contains "-h" -or $args -contains "--help" -or $args -contains "/?") {
    Show-Usage
    exit 0
}

# Run main function
Main