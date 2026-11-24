# 31 日志与指标监控 · 完整版

## 0. 怎么用

跑 19/19。日志与指标是"上线之后"的两条命脉：出问题靠日志定位，容量与性能靠指标预判。本章前半段全部真实验收，后半段的监控栈只做配置校验（镜像约 1GB，不自动拉取）。

## 1. 日志去哪儿了

### 1.1 默认路径

```bash
docker inspect -f '{{.LogPath}}' <容器>
# /var/lib/docker/containers/<完整id>/<完整id>-json.log
```

Docker Desktop（Windows/macOS）上这个路径在 WSL2 虚拟机里，宿主机文件管理器看不到。想直接读：

```bash
docker run --rm -it -v /var/lib/docker:/host alpine ls /host/containers | head
```

### 1.2 默认大小

`max-size` 默认 **0 = 不限**。一个每秒打 1000 行日志的容器，几天就能吃掉几十 GB，然后 `dockerd` 开始报 `no space left on device`，**所有容器一起挂**。

这是 Docker 生产事故的经典成因之一，成本最低的预防就是配轮转。

## 2. 日志驱动

| 驱动 | 落盘位置 | `docker logs` | 说明 |
| --- | --- | --- | --- |
| `json-file` | 宿主单文件 | 支持 | 默认值 |
| `local` | 宿主，分块压缩 | **不支持** | 自带轮转，省磁盘 |
| `journald` | systemd journal | 视配置 | 与系统日志统一 |
| `syslog` | 远程 syslog | 不支持 | 老式集中 |
| `fluentd`/`fluent-bit` | 转发 | 不支持 | 云原生主流 |
| `gelf` | Graylog | 不支持 | 需 GELF 端点 |
| `awslogs`/`gcplogs` | 云 | 不支持 | 云托管 |
| `none` | 丢弃 | 不支持 | 实测报 `does not support reading` |

选型逻辑：

```text
要不要 docker logs 排障？
  是 → json-file（配轮转）
  否 → 要不要集中？
          要 → fluent-bit / vector
          不要 → local（省空间、自动轮转）
```

## 3. 轮转

### 3.1 三种配置位置

| 位置 | 写法 | 生效范围 |
| --- | --- | --- |
| 单容器 | `docker run --log-opt max-size=10m --log-opt max-file=3` | 该容器 |
| Compose | `logging: {driver, options}` | 该服务 |
| daemon | `/etc/docker/daemon.json` 的 `log-opts` | 所有新容器（默认值） |

daemon.json：

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3",
    "compress": "true"
  }
}
```

改完 `sudo systemctl reload docker`（或 Docker Desktop 重启）。**已经存在的容器不受影响**，需要重建。

### 3.2 实测

| 检查 | 结果 |
| --- | --- |
| `HostConfig.LogConfig.Config` | `{"max-file":"2","max-size":"1m"}` |
| 5MB 突发输出 + `max-size=1m` | 日志按大小滚动，`docker logs` 仍可读 |

轮转后的文件命名：

```text
<id>-json.log
<id>-json.log.1
<id>-json.log.2      ← max-file=3 时最多保留到这里
```

### 3.3 容量估算

```text
单容器上限 ≈ max-size × max-file
全机上限 ≈ 单容器上限 × 容器数
```

例：50 个容器 × (10MB × 3) = 1.5GB，可控。不配轮转则是"无上限"。

## 4. 日志读取与排障

```bash
docker logs --tail 100 <容器>                 # 最近 100 行
docker logs -f <容器>                          # 跟踪
docker logs --since 30m <容器>                 # 最近 30 分钟
docker logs --until 2026-11-24T12:00:00 <容器>
docker logs -t <容器>                          # 每行带时间戳
docker logs <容器> 2>&1 | grep -c ERROR        # stderr 必须重定向
```

实测发现的一个真实坑：`docker logs` 把容器 **stdout 写到 CLI 的 stdout，stderr 写到 CLI 的 stderr**。所以：

```python
# 只读 stdout 会漏掉应用打到 stderr 的日志（Java/Python 的异常栈就是 stderr）
proc.stdout          # ❌ 只有一半
proc.stdout + proc.stderr   # ✅ 完整
```

本章 `--tail 1` 的第一版断言就死在这儿：容器最后一行恰好在 stderr 里，`stdout` 为空，被判成"0 行"。

时间过滤的格式：

| 写法 | 含义 |
| --- | --- |
| `--since 10m` | 相对时长 |
| `--since 2026-11-24T10:00:00` | RFC3339 |
| `--since 1700000000` | Unix 秒 |

## 5. 指标：docker stats

```bash
docker stats --no-stream
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
docker stats --no-stream --format "{{json .}}" | jq -s 'sort_by(.MemPerc) | reverse'
```

字段含义：

| 字段 | 说明 | 注意 |
| --- | --- | --- |
| `CPUPerc` | 相对单核的百分比 | 多核可超 100% |
| `MemUsage` | 已用 / 上限 | 上限来自 `--memory`，未限则显示宿主总量 |
| `MemPerc` | 内存占用比 | 未设限时分母是宿主内存 |
| `NetIO` | 收 / 发字节 | 累计值 |
| `BlockIO` | 读 / 写字节 | 累计值 |
| `PIDs` | 进程/线程数 | 与 `pids_limit` 对照 |

实测：`--memory 64m` 的死循环容器，`MemUsage` 显示 `x / 64MiB`；`CPUPerc` 明显非 0。

`docker stats` 的局限：**只有当前值，没有历史，也不能告警**。要历史就上时序库。

## 6. docker events：事件流

```bash
docker events                                  # 实时
docker events --filter container=api           # 只看某容器
docker events --filter event=die --filter event=oom
docker events --since 1h --until 10m --format '{{json .}}'
```

常见事件：

| 事件 | 含义 |
| --- | --- |
| `create` / `start` / `die` | 生命周期 |
| `oom` | 内存超限被杀 |
| `health_status: healthy/unhealthy` | 健康检查状态变化 |
| `kill` / `stop` / `destroy` | 人为或清理 |
| `network connect/disconnect` | 网络变化 |

事件流是**告警的轻量替代**：容器重启、OOM 都能实时看到，不需要部署完整监控栈。

```bash
# 最实用的排障命令之一：盯着 OOM 与重启
docker events --filter event=oom --filter event=die
```

## 7. 监控栈（cAdvisor + Prometheus + Grafana）

### 7.1 数据流

```text
cAdvisor（每节点一个）──HTTP /metrics──► Prometheus（拉取、存储）──► Grafana（看板）
        ▲                                                              ▲
        └── 读 cgroups / docker.sock ── 得到容器级 CPU/内存/网络/磁盘 ──┘
```

### 7.2 cAdvisor 的关键挂载

```yaml
volumes:
  - /:/rootfs:ro
  - /var/run:/var/run:ro
  - /sys:/sys:ro
  - /var/lib/docker:/var/lib/docker:ro
```

| 挂载 | 作用 | 少了的后果 |
| --- | --- | --- |
| `/` | 文件系统使用率 | 无磁盘指标 |
| `/var/run` | docker.sock | 看不到容器元数据 |
| `/sys` | cgroup 层级 | 无 CPU/内存指标 |
| `/var/lib/docker` | 镜像/容器目录占用 | 无镜像层指标 |

**必须是只读**（`:ro`）。给 cAdvisor 写权限没有任何收益，只有风险。

### 7.3 Prometheus 配置要点

```yaml
scrape_configs:
  - job_name: cadvisor
    static_configs:
      - targets: ["cadvisor:8080"]   # 用服务名，不是 localhost
```

两个高频错误：

1. 写 `localhost:8080` —— Prometheus 容器里的 localhost 是它自己；
2. 忘记 `--storage.tsdb.retention.time=7d`，默认 15 天，磁盘会慢慢涨。

### 7.4 本章的验收范围

| 项 | 状态 |
| --- | --- |
| `compose.yaml` + `prometheus.yml` 配置 | **已做 `config -q` 校验** |
| 三镜像拉起并抓取 | 未自动执行（镜像约 1GB） |

需要真跑：

```bash
cd examples
docker compose -f monitoring/compose.yaml up -d
# 等 30 秒后
curl http://127.0.0.1:19090/-/ready
curl "http://127.0.0.1:19090/api/v1/query?query=container_cpu_usage_seconds_total"
# Grafana: http://127.0.0.1:13000 (admin / admin)
docker compose -f monitoring/compose.yaml down -v
```

### 7.5 常用 PromQL

```promql
# 单容器 CPU 核数（rate 1 分钟）
sum(rate(container_cpu_usage_seconds_total{name="api"}[1m]))

# 内存工作集（比 usage 更贴近真实占用）
container_memory_working_set_bytes{name=~".+"}

# 网络入向速率
rate(container_network_receive_bytes_total{name=~".+"}[1m])

# 1 小时内重启过的容器（>= 1 即异常）
changes(container_start_time_seconds[1h]) >= 1

# 容器数量
count(container_last_seen{name=~".+"})
```

## 8. 逐条验收解读（19 条）

| 组 | 覆盖内容 |
| --- | --- |
| 1–2 | 默认驱动与日志落盘路径 |
| 3–4 | stdout / stderr 都可读，且不混淆 |
| 5–7 | `--tail`、`--timestamps`、`--since` 真实过滤 |
| 8 | `none` 驱动不可读（能力边界） |
| 9–11 | 轮转参数写入配置、突发输出仍可读 |
| 12–14 | `stats` JSON 可消费、CPU 真实、内存上限可见 |
| 15–16 | `events` 的 `start` / `die` |
| 17–19 | 监控栈配置合法、三服务齐全、抓取目标正确 |

## 9. 坑与对策

| 现象 | 根因 | 对策 |
| --- | --- | --- |
| 磁盘满、`no space left` | 日志无上限 | 配 `max-size`/`max-file`，daemon 设默认值 |
| 改轮转不生效 | 配置创建时固化 | 重建容器 |
| `docker logs` 用不了 | 驱动不支持读取 | 换 json-file，或改用采集器 |
| 日志缺一半 | stderr 没重定向 | `2>&1` |
| 日志时间错乱 | 容器 UTC、本地时区 | 统一 UTC，展示层转换 |
| `docker stats` 卡住 | 缺 `--no-stream` | 加参数 |
| `stats` 内存上限异常 | 未设 `--memory` | 显式设限 |
| `events` 抓不到 | 时间窗口过窄 | `--since` 放宽 |
| cAdvisor 无指标 | 挂载缺失/非只读 | 四项挂载补齐 |
| Prometheus target down | `localhost` 或网络不通 | 用服务名 + 同网络 |
| Grafana 打不开 | 3000 端口被占 | 改映射端口 |

## 10. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Docker Docs：logging drivers / `docker logs` / `docker stats` / `docker events`；Prometheus 与 cAdvisor 官方文档 |
| `[r3]` | 实测 | 19/19；日志驱动行为、`--tail` 的 stderr 陷阱、轮转参数、`stats` 字段、`events` 内容均为本机实录；监控栈仅配置校验 |

## 11. 毕业自查

- [ ] 19/19 通过
- [ ] 能说出默认日志文件路径与默认大小上限
- [ ] 能写出三种层级的轮转配置
- [ ] 能解释 `docker logs` 为什么读不到 `local` 驱动的日志
- [ ] 能解释 stderr 与 stdout 在 CLI 侧的分离
- [ ] 能用 `docker stats --format json` 做排序统计
- [ ] 能说出 cAdvisor 四项挂载各自的作用
- [ ] 能写出至少三条有用的 PromQL

## 12. 下一章

第 32 章进入镜像安全与供应链：漏洞扫描（scout / trivy）、SBOM、不可变 digest、签名与准入。
