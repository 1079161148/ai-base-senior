# 一键启动（Windows PowerShell）
#
# 做四件事：准备 .env → 拉起 Postgres → 播种演示数据 → 开后端 + 前端
#
# 用法：
#   .\scripts\start.ps1              # 完整启动
#   .\scripts\start.ps1 -NoSeed      # 不播种（数据已就绪时）
#   .\scripts\start.ps1 -NoFrontend  # 只起后端
#
# 之所以要这个脚本：这个项目有 SQLite + Postgres 两个库、两条进程、
# 还要先 seed 才好看。手动敲 6 条命令、顺序错了就报"pg pool 尚未创建"，
# 第一次跑的人很难一次成功。

param(
    [switch]$NoSeed,
    [switch]$NoFrontend,
    [int]$Port = 8001,
    [int]$WebPort = 9999
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$web = Join-Path (Split-Path -Parent $root) 'agent-lab-web'

Write-Host '== agent-lab 一键启动 ==' -ForegroundColor Cyan

# ---- 1. .env ----
$envFile = Join-Path $root '.env'
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $root '.env.example') $envFile
    Write-Host '  · 已从 .env.example 生成 .env'
    Write-Host '    注意：LLM_API_KEY 还是空的，先在 .env 里填上再继续。' -ForegroundColor Yellow
}

# 从 .env 读 PG_DSN，避免脚本里硬编码一份配置
$pgDsn = (Get-Content $envFile | Where-Object { $_ -match '^PG_DSN=' } | Select-Object -First 1) -replace '^PG_DSN=', ''
if (-not $pgDsn) { $pgDsn = 'postgresql://agent_lab:agent_lab@127.0.0.1:5433/agent_lab' }
$pgPort = if ($pgDsn -match ':(\d+)/') { $Matches[1] } else { '5433' }

# ---- 2. Postgres ----
$pgUp = (netstat -ano | Select-String ":$pgPort\s+.*LISTENING").Count -gt 0
if (-not $pgUp) {
    Write-Host "  · Postgres 未监听 $pgPort，尝试 docker compose up -d pg"
    Push-Location (Split-Path -Parent $root)
    try { docker compose up -d pg | Out-Null } catch { Write-Host '    docker 不可用，请手动启动 Postgres' -ForegroundColor Yellow }
    Pop-Location
    # 容器起来到能接受连接有几秒空窗，直接连会 connection refused
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 1
        if ((netstat -ano | Select-String ":$pgPort\s+.*LISTENING").Count -gt 0) { break }
    }
} else {
    Write-Host "  · Postgres 已在 $pgPort"
}

# ---- 3. 依赖 + 播种 ----
Push-Location $root
Write-Host '  · 同步依赖（uv sync）'
uv sync | Out-Null

if (-not $NoSeed) {
    Write-Host '  · 播种演示数据'
    uv run python scripts/seed.py
}
Pop-Location

# ---- 4. 起服务 ----
Write-Host "  · 后端 http://127.0.0.1:$Port"
Start-Process -FilePath 'uv' `
    -ArgumentList 'run', 'python', '-m', 'uvicorn', 'agent_lab.app.main:app', '--host', '127.0.0.1', '--port', $Port, '--reload' `
    -WorkingDirectory $root -WindowStyle Normal

if (-not $NoFrontend) {
    if (Test-Path $web) {
        Write-Host "  · 前端 http://127.0.0.1:$WebPort"
        # 首次跑要装依赖，有 node_modules 就跳过
        if (-not (Test-Path (Join-Path $web 'node_modules'))) {
            Push-Location $web; npm install | Out-Null; Pop-Location
        }
        Start-Process -FilePath 'npm' -ArgumentList 'run', 'dev' -WorkingDirectory $web -WindowStyle Normal
    } else {
        Write-Host "  ! 找不到 $web，跳过前端" -ForegroundColor Yellow
    }
}

Write-Host ''
Write-Host "启动完成后打开 http://127.0.0.1:$WebPort" -ForegroundColor Green
Write-Host '演示账号：demo / demo123'
Write-Host '停止：关掉那两个新开的窗口即可。'