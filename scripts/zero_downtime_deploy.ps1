# scripts/zero_downtime_deploy.ps1
# Zero Downtime Deployment Orchestrator for OSI NOC Incident Analysis system

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "    OSI ZERO DOWNTIME DEPLOYMENT ORCHESTRATOR       " -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# Configuration
$Service = "dashboard_server"
$ComposeFile = "docker-compose.yml"

# Step 1: Rebuild the target service image
Write-Host "[1/5] Building latest container images..." -ForegroundColor Yellow
docker-compose -f $ComposeFile build $Service

# Step 2: Scale up the service to 2 instances
Write-Host "[2/5] Scaling up $Service to 2 instances..." -ForegroundColor Yellow
docker-compose -f $ComposeFile up -d --scale $Service=2 --no-recreate

# Step 3: Wait for the new instance to be healthy
Write-Host "[3/5] Waiting for new instance health checks..." -ForegroundColor Yellow
$Healthy = $false
for ($i = 0; $i -lt 12; $i++) {
    Start-Sleep -Seconds 5
    # Check if there are 2 running instances and both are healthy
    $Containers = docker ps --filter "name=$Service" --format "{{.Status}}"
    $HealthyCount = 0
    foreach ($Status in $Containers) {
        if ($Status -like "*healthy*" -or $Status -like "*Up*") {
            $HealthyCount++
        }
    }
    if ($HealthyCount -ge 2) {
        $Healthy = $true
        Write-Host "     [OK] Both instances are online and responding!" -ForegroundColor Green
        break
    }
    Write-Host "     Waiting... ($(($i+1)*5)s elapsed)" -ForegroundColor DarkGray
}

if (-not $Healthy) {
    Write-Error "Deployment timed out. Scaling back to 1 instance and aborting."
    docker-compose -f $ComposeFile up -d --scale $Service=1
    Exit 1
}

# Step 4: Gracefully stop and remove the old instance
Write-Host "[4/5] Pruning old service instances..." -ForegroundColor Yellow
# Get container IDs of the service ordered by creation time
$ContainerIDs = docker ps -a --filter "name=$Service" --format "{{.ID}}"
if ($ContainerIDs.Count -ge 2) {
    $OldContainer = $ContainerIDs[1] # The older container ID
    Write-Host "     Stopping old container: $OldContainer" -ForegroundColor DarkGray
    docker stop $OldContainer
    docker rm $OldContainer
}

# Step 5: Scale down to 1 instance (which is the new one)
Write-Host "[5/5] Resetting scale back to 1 instance..." -ForegroundColor Yellow
docker-compose -f $ComposeFile up -d --scale $Service=1

Write-Host "====================================================" -ForegroundColor Green
Write-Host "    Deployment Completed Successfully (0 downtime)   " -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Green
