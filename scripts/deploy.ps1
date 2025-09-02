# Blue-Green Deployment Script for Sofia V2 (Windows/PowerShell)
# Safe deployment with health checks and rollback

param(
    [Parameter(Position=0)]
    [ValidateSet("deploy", "status", "rollback")]
    [string]$Action = "deploy"
)

# Configuration
$HEALTH_CHECK_RETRIES = 30
$HEALTH_CHECK_INTERVAL = 2
$API_BLUE_PORT = 8000
$API_GREEN_PORT = 8001

# Functions
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Test-Health {
    param(
        [string]$Url,
        [int]$Retries
    )
    
    Write-Info "Checking health at $Url"
    
    for ($i = 1; $i -le $Retries; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                Write-Success "Health check passed"
                return $true
            }
        } catch {
            Write-Info "Attempt $i/$Retries failed, waiting ${HEALTH_CHECK_INTERVAL}s..."
            Start-Sleep -Seconds $HEALTH_CHECK_INTERVAL
        }
    }
    
    Write-Error "Health check failed after $Retries attempts"
    return $false
}

function Get-CurrentDeployment {
    $blueRunning = docker ps --format "table {{.Names}}" | Select-String "sofia-api-blue"
    $greenRunning = docker ps --format "table {{.Names}}" | Select-String "sofia-api-green"
    
    if ($blueRunning) {
        return "blue"
    } elseif ($greenRunning) {
        return "green"
    } else {
        return "none"
    }
}

function Deploy-Target {
    param([string]$Target)
    
    Write-Info "Starting $Target deployment..."
    
    # Build new image
    Write-Info "Building Docker image..."
    docker compose build
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker build failed"
        return $false
    }
    
    # Start target deployment
    Write-Info "Starting $Target containers..."
    docker compose --profile $Target up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to start $Target containers"
        return $false
    }
    
    # Wait for health check
    $port = if ($Target -eq "blue") { $API_BLUE_PORT } else { $API_GREEN_PORT }
    
    if (-not (Test-Health "http://localhost:$port/api/health" $HEALTH_CHECK_RETRIES)) {
        Write-Error "Health check failed for $Target deployment"
        Write-Info "Rolling back..."
        docker compose --profile $Target down
        return $false
    }
    
    Write-Success "$Target deployment is healthy"
    return $true
}

function Switch-Traffic {
    param(
        [string]$From,
        [string]$To
    )
    
    Write-Info "Switching traffic from $From to $To..."
    
    # In production, update load balancer or DNS here
    # For this example, we just note the switch
    $port = if ($To -eq "blue") { $API_BLUE_PORT } else { $API_GREEN_PORT }
    
    Write-Success "Traffic switched to $To (port $port)"
}

function Retire-Deployment {
    param([string]$Deployment)
    
    Write-Info "Retiring $Deployment deployment..."
    
    # Graceful shutdown
    Write-Info "Sending stop signal to $Deployment containers..."
    docker compose --profile $Deployment stop
    
    # Wait for graceful shutdown
    Start-Sleep -Seconds 5
    
    # Remove containers
    docker compose --profile $Deployment down
    
    Write-Success "$Deployment deployment retired"
}

# Main deployment flow
function Main-Deploy {
    Write-Info "Starting Blue-Green Deployment"
    Write-Info "==============================="
    
    # Determine current and target deployments
    $current = Get-CurrentDeployment
    Write-Info "Current deployment: $current"
    
    if ($current -eq "blue") {
        $target = "green"
    } elseif ($current -eq "green") {
        $target = "blue"
    } else {
        # First deployment
        $target = "blue"
        Write-Info "No current deployment found, starting with $target"
    }
    
    Write-Info "Target deployment: $target"
    
    # Deploy new version
    if (-not (Deploy-Target $target)) {
        Write-Error "Deployment failed"
        exit 1
    }
    
    # Run smoke tests
    Write-Info "Running smoke tests..."
    $port = if ($target -eq "blue") { $API_BLUE_PORT } else { $API_GREEN_PORT }
    
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$port/api/dev/status" -UseBasicParsing
        if ($response.StatusCode -ne 200) {
            throw "Unexpected status code"
        }
    } catch {
        Write-Error "Smoke test failed: /api/dev/status"
        Retire-Deployment $target
        exit 1
    }
    
    Write-Success "Smoke tests passed"
    
    # Switch traffic if there was a previous deployment
    if ($current -ne "none") {
        Switch-Traffic $current $target
        
        # Monitor for issues
        Write-Info "Monitoring new deployment for 30 seconds..."
        Start-Sleep -Seconds 30
        
        # Final health check
        if (-not (Test-Health "http://localhost:$port/api/health" 3)) {
            Write-Error "Post-switch health check failed"
            Write-Warning "Rolling back to $current"
            Switch-Traffic $target $current
            Retire-Deployment $target
            exit 1
        }
        
        # Retire old deployment
        Retire-Deployment $current
    }
    
    Write-Success "==============================="
    Write-Success "Deployment completed successfully"
    Write-Success "Active deployment: $target"
    Write-Success "API available at: http://localhost:$port"
}

# Handle script arguments
switch ($Action) {
    "deploy" {
        Main-Deploy
    }
    "status" {
        $current = Get-CurrentDeployment
        if ($current -eq "none") {
            Write-Info "No active deployment"
        } else {
            Write-Info "Active deployment: $current"
            $port = if ($current -eq "blue") { $API_BLUE_PORT } else { $API_GREEN_PORT }
            Write-Info "API endpoint: http://localhost:$port"
        }
    }
    "rollback" {
        $current = Get-CurrentDeployment
        $target = if ($current -eq "blue") { "green" } else { "blue" }
        Write-Warning "Rolling back from $current to $target"
        Deploy-Target $target
        Switch-Traffic $current $target
        Retire-Deployment $current
    }
}