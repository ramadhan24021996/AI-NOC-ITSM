# Multi-Platform Compilation Script for OSI AI System (Fase 16)
# Compiles all Go services for Windows x64/ARM64 and Linux x64/ARM64 using reproducible flags

param (
    [Parameter(Mandatory=$false)]
    [string]$OutDir = "release_binaries"
)

$ProjectRoot = Split-Path -Parent -Path $PSScriptRoot
$ReleaseDir = Join-Path $ProjectRoot $OutDir

$Targets = @(
    @{ OS = "windows"; Arch = "amd64"; Ext = ".exe" },
    @{ OS = "windows"; Arch = "arm64"; Ext = ".exe" },
    @{ OS = "linux";   Arch = "amd64"; Ext = "" },
    @{ OS = "linux";   Arch = "arm64"; Ext = "" }
)

$Services = @(
    @{ Name = "ingestion_server"; Source = "SERVER/go_core/main.go" },
    @{ Name = "dashboard_server"; Source = "portal" },
    @{ Name = "agent";            Source = "CLIENT_DISTRIBUSI_GO/agent/main.go";   OnlyWindows = $true },
    @{ Name = "installer";        Source = "CLIENT_DISTRIBUSI_GO/installer/main.go"; OnlyWindows = $true },
    @{ Name = "updater";          Source = "CLIENT_DISTRIBUSI_GO/updater/main.go";   OnlyWindows = $true },
    @{ Name = "launcher";         Source = "LAUNCHER_SERVICE_GO/main.go";          OnlyWindows = $true }
)

Write-Host "====================================================" -ForegroundColor Green
Write-Host "   OSI AI SYSTEM MULTI-PLATFORM COMPILER" -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Green

if (-not (Test-Path $ReleaseDir)) {
    New-Item -ItemType Directory -Path $ReleaseDir | Out-Null
}

$GoBin = "C:\Program Files\Go\bin\go.exe"

foreach ($target in $Targets) {
    $os = $target.OS
    $arch = $target.Arch
    $ext = $target.Ext
    
    $TargetDir = Join-Path $ReleaseDir "${os}_${arch}"
    if (-not (Test-Path $TargetDir)) {
        New-Item -ItemType Directory -Path $TargetDir | Out-Null
    }
    
    Write-Host "[BUILD] Compiling for Target: OS=$os Arch=$arch..." -ForegroundColor Cyan
    
    foreach ($svc in $Services) {
        # Some services (like Windows Registry Watcher or subprocess controllers) are Windows specific
        if ($svc.OnlyWindows -and $os -ne "windows") {
            continue
        }
        
        $outputName = $svc.Name + $ext
        $outputPath = Join-Path $TargetDir $outputName
        $sourcePath = Join-Path $ProjectRoot $svc.Source
        
        Write-Host "  -> Building $($svc.Name)..." -ForegroundColor Yellow
        
        $env:GOOS = $os
        $env:GOARCH = $arch
        
        # Build with -trimpath for reproducible builds and -ldflags="-s -w" to shrink binary size
        & $GoBin build -trimpath -ldflags="-s -w" -o $outputPath $sourcePath
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "     [OK] Written: $outputName" -ForegroundColor Green
        } else {
            Write-Host "     [FAILED] Compilation error for $($svc.Name)" -ForegroundColor Red
        }
    }
}

Write-Host "====================================================" -ForegroundColor Green
Write-Host "   Multi-platform compilation task completed!" -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Green
