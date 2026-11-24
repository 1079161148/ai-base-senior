# 31 日志与指标监控

## 一句话结论

容器的日志默认躺在 `/var/lib/docker/containers/<id>/<id>-json.log` 里**无限增长**——不配轮转，迟早撑爆磁盘。指标方面 `docker stats` 够看单机，要多机/历史就上 cAdvisor + Prometheus + Grafana。

## 最小可运行案例

```bash
# 日志轮转（生产必配）
docker run -d --name api \
  --log-opt max-size=10m --log-opt max-file=3 \
  --log-driver json-file \
  myapp:1.0

# 看指标
docker stats --no-stream
docker stats --no-stream --format "{{.Name}} {{.CPUPerc}} {{.MemUsage}}"
```

## 怎么跑

```powershell
cd "07-生产与AI实战\31-日志与指标监控\examples"
uv run python verify.py
```

## 本机实测（19/19）

| 断言 | 实测 |
| --- | --- |
| 默认日志驱动 | `json-file` |
| 日志文件路径 | `.../<id>-json.log` |
| `docker logs` | 能看到 stdout |
| stdout/stderr | 内容都不丢（stderr 走 CLI 的 stderr） |
| `--tail 1` | 只返回 1 行 |
| `--timestamps` | 每行前缀 RFC3339 时间 |
| `--since 10m` | 能过滤历史 |
| `--log-driver none` | `docker logs` 报 `does not support reading` |
| `--log-opt max-size/max-file` | 记录进 `HostConfig.LogConfig.Config` |
| 5MB 突发输出 + `max-size=1m` | 仍可正常读取（按大小滚动） |
| `docker stats --format json` | 逐行 JSON，含 `CPUPerc` |
| 死循环容器 | `CPUPerc ≠ 0.00%`（真实采样） |
| `--memory 64m` | `MemUsage` 上限显示 `64MiB` |
| `docker events` | 取到 `start` / `die` 事件 |
| 监控栈 compose | `config -q` 通过，三服务齐全 |

> 监控栈（cAdvisor/Prometheus/Grafana 约 1GB 镜像）本章**只做配置校验**，不自动拉起；需要时 `docker compose -f monitoring/compose.yaml up -d`。

## 日志驱动怎么选

| 驱动 | 去处 | 适用 |
| --- | --- | --- |
| `json-file`（默认） | 宿主文件，`docker logs` 可读 | 单机、开发 |
| `local` | 宿主文件，二进制+自动轮转 | 单机、想省磁盘 |
| `journald` | systemd journal | 已用 systemd 的统一日志 |
| `syslog` | 远程 syslog | 旧式集中日志 |
| `fluentd` / `fluent-bit` | 转发到采集器 | 云原生主流 |
| `gelf` | Graylog | 已有 Graylog |
| `awslogs` / `gcplogs` | 云日志服务 | 公有云 |
| `none` | 丢弃 | 高频无意义日志 |

`local` 驱动值得单独提：**自带轮转、压缩率高**，但不支持 `docker logs`（要用 `docker logs` 调试就得留在 json-file）。

## 轮转配置

```yaml
# compose
services:
  api:
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

等效于 `docker run --log-opt max-size=10m --log-opt max-file=3`。

要点：

| 项 | 说明 |
| --- | --- |
| 默认值 | **无限**（0），不配就一直长 |
| `max-size` | 单个文件上限，超了滚动 |
| `max-file` | 保留几个文件，超出删最旧 |
| 总量估算 | `max-size × max-file × 容器数` |
| 生效方式 | 创建时写入配置，**改了要重建容器** |

守护进程级默认值（对所有新容器生效）：

```json
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
```

## 常用日志命令

```bash
docker logs -f --tail 100 <容器>
docker logs --since 30m --until 5m <容器>
docker logs --timestamps <容器> | head
docker logs -t <容器> 2>&1 | grep -i error
docker compose logs -f --tail=200 api db
docker inspect -f '{{.LogPath}}' <容器>       # 日志文件在宿主的真实路径
docker inspect -f '{{json .HostConfig.LogConfig}}' <容器>
```

注意两个容易误解的点：

1. **`docker logs` 只能读驱动支持读取的日志**（`none`/`local`/`syslog` 不支援）。
2. **stderr 走 CLI 的 stderr**，重定向时 `2>&1` 别漏，否则"日志丢了"。

## 指标：三条路线

| 路线 | 工具 | 适合 | 成本 |
| --- | --- | --- | --- |
| 临时看 | `docker stats` | 排障、单机 | 0 |
| 单机历史 | cAdvisor + Prometheus + Grafana | 单机/小集群 | 中 |
| 集群 | K8s metrics-server + Prometheus Operator | 多节点 | 高 |

`docker stats` 的坑：默认实时刷新，脚本里一定加 `--no-stream`，否则挂住。

```bash
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
docker stats --no-stream --format "{{json .}}" | jq -s 'sort_by(.CPUPerc) | reverse | .[0:5]'
```

## 监控栈结构

```text
cAdvisor ──/metrics──► Prometheus ──查询──► Grafana
（采集容器指标）      （存储 TSDB）      （看板/告警）
```

| 组件 | 端口 | 作用 |
| --- | --- | --- |
| cAdvisor | 8080 | 采集容器 CPU/内存/网络/磁盘 |
| Prometheus | 9090 | 拉取 + 存储 + PromQL |
| Grafana | 3000 | 看板（默认 admin/admin） |

cAdvisor 需要挂宿主 `/`、`/var/run`、`/sys`、`/var/lib/docker` 才能看到全部容器，**只读挂载**。

关键 PromQL：

```promql
# 每个容器 CPU 使用率
rate(container_cpu_usage_seconds_total{name=~".+"}[1m])
# 内存使用（去掉 cache）
container_memory_working_set_bytes{name=~".+"}
# 网络接收速率
rate(container_network_receive_bytes_total[1m])
# 容器重启次数
changes(container_start_time_seconds[1h])
```

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 磁盘被日志吃满 | 没配 `max-size` | 配轮转 + daemon 默认值 |
| 改了轮转不生效 | 配置在创建时固化 | 重建容器 |
| `docker logs` 报不支持读取 | 驱动是 `none`/`local`/`syslog` | 换 json-file 或改用采集器 |
| 日志"少了 stderr" | stderr 走 CLI stderr | `2>&1` |
| 时间对不上 | 容器时区 UTC | 统一 UTC 存储，展示时转本地 |
| `docker stats` 空白 | 缺 `--no-stream` | 加参数 |
| cAdvisor 看不到容器 | 没挂 `/var/lib/docker` | 四项只读挂载补齐 |
| Prometheus 抓不到 | target 写成 `localhost:8080` | 容器内要用服务名 `cadvisor:8080` |
| Grafana 密码是 admin | 没设 `GF_SECURITY_ADMIN_PASSWORD` | 环境变量覆盖 |
| 日志里带敏感信息 | 打了密码/token | 应用侧脱敏，别指望 Docker 过滤 |

## 生产建议

| 项 | 建议 |
| --- | --- |
| 日志 | 全部输出到 stdout/stderr，结构化 JSON，配轮转 |
| 采集 | fluent-bit / Vector / Promtail 转发到 Loki/ES |
| 指标 | cAdvisor 或 K8s metrics；应用暴露 `/metrics` |
| 告警 | 基于 PromQL：重启次数、OOMKilled、错误率、P99 |
| 保留期 | 日志 7–30 天，指标 15 天起，按合规调整 |
| 成本 | 采样 + 分级（ERROR 全留，DEBUG 采样） |

## 毕业自查

- [ ] 19/19 通过
- [ ] 能说出 json-file 日志文件在哪、默认有多大上限
- [ ] 能写出日志轮转的 run 参数与 compose 写法
- [ ] 能解释为什么 `--log-driver none` 后 `docker logs` 失效
- [ ] 能用 `docker stats --format json` 写一行排序脚本
- [ ] 能画出 cAdvisor→Prometheus→Grafana 的数据流
- [ ] 知道 stderr 为什么要 `2>&1`
