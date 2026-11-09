# 一键启动前后端开发服务
#
# 用法：
#   cd E:\ai-agent-study\code
#   .\dev.ps1
#
# 会在两个新的 PowerShell 窗口里分别启动后端和前端，
# 关掉对应窗口（或按 Ctrl+C）即可停止。

$ErrorActionPreference = 'Stop'

$root    = $PSScriptRoot
$backend = Join-Path $root 'agent-lab'
$frontend = Join-Path $root 'agent-lab-web'

Write-Host ''
Write-Host '=== agent-lab 开发环境 ===' -ForegroundColor Cyan

# --- 前置检查 ---
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host '✗ 未找到 uv，请先安装：' -ForegroundColor Red
    Write-Host '  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"' -ForegroundColor Yellow
    exit 1
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host '✗ 未找到 npm，请先安装 Node.js 20+' -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
    Write-Host '! 前端依赖未安装，正在执行 npm install ...' -ForegroundColor Yellow
    Push-Location $frontend
    npm install
    Pop-Location
}

# --- 端口占用检查 ---
foreach ($port in 8001, 5173) {
    $used = netstat -ano | Select-String ":$port\s+.*LISTENING"
    if ($used) {
        Write-Host "! 端口 $port 已被占用，启动可能失败：" -ForegroundColor Yellow
        $used | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
        Write-Host "  清理：taskkill /PID <PID> /T /F" -ForegroundColor DarkGray
    }
}

# --- 启动 ---
Write-Host '→ 启动后端 (8001) ...' -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    '-NoExit',
    '-Command',
    "cd '$backend'; Write-Host 'agent-lab backend' -ForegroundColor Cyan; uv run python run.py"
)

Start-Sleep -Seconds 2

Write-Host '→ 启动前端 (5173) ...' -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    '-NoExit',
    '-Command',
    "cd '$frontend'; Write-Host 'agent-lab web' -ForegroundColor Cyan; npm run dev"
)

Write-Host ''
Write-Host '已启动，等待几秒后访问：' -ForegroundColor Cyan
Write-Host '  前端  http://127.0.0.1:5173'
Write-Host '  文档  http://127.0.0.1:8001/docs'
Write-Host ''
Write-Host '停止：在各自窗口按 Ctrl+C' -ForegroundColor DarkGray
