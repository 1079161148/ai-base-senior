# S8 · 数据备份（Windows）。
#
# 备份两样东西，缺一不可：
#   1. SQLite（会话/待办/计划/指标）—— 业务数据，丢了找不回来
#   2. pgvector（文档向量）—— 能重建，但要从零重新 embedding，很贵
#
# 用法：powershell -File scripts/backup.ps1
# 建议挂到计划任务，每天凌晨跑一次。

param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [int]$KeepDays = 7,
    [string]$PgContainer = "agent-lab-pg"
)

$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $Root "data\backups\$stamp"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

# --- 1. SQLite：用 VACUUM INTO 而不是直接复制 ---
# 直接 copy 一个正在被写入的 db 文件，可能拷到"中间状态"，恢复后可能损坏。
# VACUUM INTO 会生成一个一致性的快照。
Write-Host "备份 SQLite ..."
$dbPath = Join-Path $Root "data\app.db"
if (Test-Path $dbPath) {
    Push-Location $Root
    uv run python -c @"
import sqlite3, sys
src = sqlite3.connect(r'$dbPath')
dst = r'$dest\app.db'
src.execute('VACUUM INTO ?', (dst,))
src.close()
print('ok')
"@
    Pop-Location
} else {
    Write-Warning "未找到 $dbPath，跳过"
}

# --- 2. pgvector ---
# 用 docker exec 在容器内 pg_dump，避免宿主机没装 pg 客户端
Write-Host "备份 pgvector ..."
$dumpFile = Join-Path $dest "pgvector.sql"
$running = docker ps --filter "name=$PgContainer" --format "{{.Names}}"
if ($running) {
    docker exec $PgContainer pg_dump -U agent_lab -d agent_lab | Out-File -FilePath $dumpFile -Encoding utf8
} else {
    Write-Warning "容器 $PgContainer 未运行，跳过向量库备份"
}

# --- 3. 清理过期备份 ---
$cutoff = (Get-Date).AddDays(-$KeepDays)
Get-ChildItem (Join-Path $Root "data\backups") -Directory |
    Where-Object { $_.CreationTime -lt $cutoff } |
    ForEach-Object {
        Write-Host "清理过期备份：$($_.Name)"
        Remove-Item -Recurse -Force $_.FullName
    }

Write-Host "备份完成：$dest"
