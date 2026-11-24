# 30 运行时安全加固 · 完整版

## 0. 怎么用

跑 18/18。本章只关心一件事：**容器跑起来之后，攻击面有多大，怎么收窄**。镜像构建期的安全（非 root、最小基础镜像）在第 22 章，镜像供应链安全在第 32 章。

## 1. 威胁模型：容器边界在哪

| 攻击者位置 | 能做什么 | 依赖的缺口 |
| --- | --- | --- |
| 容器内普通进程 | 读挂载的文件、访问同网络服务 | 挂载过多、网络过宽 |
| 容器内 root | 写根文件系统、装后门、改系统配置 | 非只读根、未降权 |
| 带 `CAP_SYS_ADMIN` | mount、操作 namespace、逃逸 | 过度授权 |
| 带 `--privileged` | 几乎等同宿主 root | 图省事 |
| 挂 `docker.sock` | 创建特权容器、读宿主文件 | 直接放弃边界 |

加固的顺序就是**从下往上堵**：先别给特权，再降权，再收窄文件系统与系统调用，最后限资源。

## 2. capabilities：位图与实测

### 2.1 位图怎么读

```bash
docker run --rm alpine:3.20 grep CapEff /proc/self/status
# CapEff: 00000000a80425fb
```

把十六进制转二进制，第 n 位为 1 表示持有编号 n 的能力。`capsh --decode` 更直观：

```bash
capsh --decode=00000000a80425fb
# 0x00000000a80425fb=cap_chown,cap_dac_override,cap_fowner,cap_fsetid,...
```

### 2.2 本机三组实测值

| 配置 | CapEff | 含义 |
| --- | --- | --- |
| 默认 | `00000000a80425fb` | 14 项 Docker 默认能力 |
| `--cap-drop ALL` | `0000000000000000` | 一个都不给 |
| `--cap-drop ALL --cap-add NET_BIND_SERVICE` | `0000000000000400` | 只给一项（0x400） |
| `--privileged` | `000001ffffffffff` | 43 项全给 |

`NET_BIND_SERVICE` 是第 10 位（2^10 = 1024 = 0x400），位图能对上，说明这是真实的能力位而非"看起来像"。

### 2.3 默认集与危险能力

| 能力 | 默认 | 常见需求 | 建议 |
| --- | --- | --- | --- |
| `CHOWN` | 有 | 启动脚本要 chown 数据目录 | 保留或改构建期 chown |
| `SETUID`/`SETGID` | 有 | su-exec 降权 | 保留 |
| `NET_BIND_SERVICE` | 有 | 绑 80/443 | 保留（或反代） |
| `NET_RAW` | 有 | `ping`、抓包 | **纯 Web 服务可裁** |
| `SYS_CHROOT` | 有 | chroot | 多数可裁 |
| `MKNOD` | 有 | 建设备节点 | 可裁 |
| `SYS_ADMIN` | **无** | mount、部分 FUSE | 坚决不给 |
| `SYS_PTRACE` | **无** | 调试、性能分析 | 临时给，调完就摘 |
| `NET_ADMIN` | **无** | 改 iptables/路由 | 只有网络组件需要 |
| `SYS_MODULE` | **无** | 加载内核模块 | 永远不给 |

### 2.4 mount 被拒的实测

```bash
docker run --rm alpine:3.20 mount -t tmpfs none /mnt
# mount: permission denied (are you root?)
```

看起来是 root（UID 0），却没有 `CAP_SYS_ADMIN`——这就是"root 也要看能力"的直接证据，也是容器比 VM 更细粒度的地方。

## 3. 用户与文件系统

### 3.1 三个层次的降权

| 层次 | 做法 | 覆盖能力 |
| --- | --- | --- |
| 构建期 | `USER appuser` | 镜像默认 |
| 编排期 | `user: "10001:10001"` | 覆盖镜像 |
| 运行期 | `--user 10001:10001` | 覆盖一切 |

实测：`--user 10001:10001` 后 `id -u` 为 10001，`mkdir /forbidden` 失败（`/` 属主是 root、权限 755）。

### 3.2 只读根 + tmpfs

```bash
docker run --rm --read-only alpine:3.20 touch /blocked      # 失败
docker run --rm --read-only --tmpfs /tmp alpine:3.20 touch /tmp/ok   # 成功
```

`--tmpfs` 的参数能直接限大小：

```bash
docker run --rm --tmpfs /tmp:size=1m alpine:3.20 \
  sh -c "dd if=/dev/zero of=/tmp/big bs=1024 count=2048"
# dd: error writing '/tmp/big': No space left on device
```

这条顺带证明 **tmpfs 不占宿主磁盘、且 size 是硬限制**——防止应用写爆内存。

### 3.3 只读根下常见"需要写"的地方

| 路径 | 原因 | 解法 |
| --- | --- | --- |
| `/tmp` | 临时文件 | `--tmpfs /tmp` |
| `/run`、`/var/run` | pid、socket | `--tmpfs /run` |
| `/var/cache/nginx` | nginx 缓存 | 改配置或挂 tmpfs |
| `/var/log` | 应用写日志 | 改 stdout（第 31 章） |
| `/home/app/.cache` | pip/npm 缓存 | 构建期装好，运行期不需要 |
| Python 字节码 | `__pycache__` | `PYTHONDONTWRITEBYTECODE=1` |

## 4. no-new-privileges：防 setuid 提权

```bash
--security-opt no-new-privileges:true
```

作用：容器内进程**不能通过 setuid/setgid 程序或 capabilities 提升权限**。

典型场景：镜像里有 `sudo` 或被误设了 suid 位的二进制，攻击者拿到低权限 shell 后靠它提权。加上这个选项后，`sudo` 直接失效。

实测 `HostConfig.SecurityOpt` 里能看到该值，且容器正常运行——**成本几乎为零，收益明显**。

## 5. seccomp：系统调用白名单

Docker 默认启用 `builtin` profile（`docker info` 里能看到 `name=seccomp,profile=builtin`），它拦掉约 40 个危险 syscall（如 `kexec_load`、`create_module`、`bpf` 的部分操作）。

| 做法 | 风险 |
| --- | --- |
| 保持默认 | 低，推荐 |
| `seccomp=unconfined` | 高：所有 syscall 放开 |
| 自定义 JSON profile | 中：维护成本，容易漏 |
| `--security-opt seccomp=profile.json` | 需要逐项验证 |

自定义时从默认 profile 出发：

```bash
# 1. 拉出默认 profile 参考（官方 moby/profiles/seccomp/default.json）
# 2. 只把 target 加进 syscalls allow 列表
# 3. 用 strace 对照验证
docker run --rm --security-opt seccomp=./profile.json myapp:1.0
```

LSM 补充：

| 机制 | 命令 | 说明 |
| --- | --- | --- |
| AppArmor | `--security-opt apparmor=docker-default` | Ubuntu/Debian 默认 |
| SELinux | `--security-opt label=type:container_t` | RHEL 系 |
| no-new-privileges | `--security-opt no-new-privileges:true` | 跨平台通用 |

## 6. 资源限制

| 参数 | 防什么 | 实测 |
| --- | --- | --- |
| `--pids-limit 32` | fork 炸弹、进程泄漏 | 批量 `sleep &` 报 `Resource temporarily unavailable` |
| `--memory 256m` | 内存耗尽拖垮宿主 | 超限 OOMKilled |
| `--cpus 0.5` | CPU 抢占 | 配额调度 |
| `--ulimit nofile` | 文件描述符耗尽 | 需与系统 `fs.file-max` 协调 |
| `--blkio-weight` | IO 抢占 | 一般交给存储层 |

`--pids-limit` 的坑：**镜像正常运行时也需要足够进程数**。Java 线程算进程数（每个线程一个 task），`pids-limit` 太小会让 JVM 起不来；建议按"实测峰值 × 2"给。

```bash
# 观察某容器实际用到的进程数
docker exec <容器> ps -eLf | wc -l
docker stats --no-stream
```

## 7. 设备与内核面

| 需求 | 正确做法 | 错误做法 |
| --- | --- | --- |
| GPU | `--gpus all`（第 34 章） | `--privileged` |
| 访问串口/USB | `--device /dev/ttyUSB0` | 挂 `/dev` |
| 内核参数 | `sysctl`（命名空间内的） | `--privileged` + 改宿主 |
| 时间同步 | 宿主统一管理 | 容器内改宿主时钟 |
| 容器管理 | docker-socket-proxy | 直接挂 `docker.sock` |

`docker.sock` 是最容易被忽视的高危项：挂进去的容器可以创建 `--privileged` 容器并挂载宿主根目录，等于宿主机 root。

```yaml
# 只放开需要的那几个端点
services:
  proxy:
    image: tecnativa/docker-socket-proxy
    environment:
      CONTAINERS: 1
      IMAGES: 0
      EXEC: 0
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
```

## 8. 逐条验收解读（18 条）

| 组 | 证明了什么 |
| --- | --- |
| 1–2 | 默认能力集是裁剪过的，且不含 `SYS_ADMIN`（mount 失败） |
| 3–4 | `--cap-drop ALL` 与精确 `--cap-add` 的位图效果 |
| 5–6 | `no-new-privileges` 被记录且不影响启动 |
| 7–9 | 只读根、tmpfs 可写、tmpfs size 硬限制 |
| 10–11 | `--user` 生效且非 root 确实受限 |
| 12–14 | `pids-limit` 落到 HostConfig，且 fork 真被拦 |
| 15 | `--privileged` 的能力全开对比 |
| 16–18 | seccomp 可关但默认开启（`builtin` profile） |

## 9. 坑与对策

| 现象 | 根因 | 对策 |
| --- | --- | --- |
| `--read-only` 后应用崩 | 需要写临时/缓存目录 | `--tmpfs` 或改配置 |
| 非 root 启动失败 | 挂载目录属主 root | 命名卷 + 构建期 chown |
| 非 root 绑 80 失败 | 特权端口 | `CAP_NET_BIND_SERVICE` / 反代 |
| `cap-drop ALL` 后 `ping` 失败 | 缺 `NET_RAW` | 按需加回 |
| JVM 起不来 | `pids-limit` 太小 | 调大或不用 pids 限制 |
| OOMKilled 但内存看着够 | 运行时不知道 cgroup 限制 | 显式设堆大小 |
| seccomp 自定义后随机崩 | 拦掉需要的 syscall | 从默认 profile 增量改 |
| `chown` 失败 | 缺 `CAP_CHOWN` | 构建期 chown，运行期只读 |
| 健康检查失败但服务正常 | 检查命令依赖被裁掉的能力 | 换轻量检查方式 |
| 调试需要 `ptrace` | 默认不给 | 临时 `--cap-add SYS_PTRACE`，调完移除 |

## 10. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Docker Docs：`docker run` 安全选项、seccomp 默认 profile、capabilities 列表；NIST SP 800-190 容器安全指南 |
| `[r3]` | 实测 | 18/18；`CapEff` 三组位图、mount 被拒、tmpfs size、fork 被拦、`SecurityOptions` 均为本机实录 |

## 11. 毕业自查

- [ ] 18/18 通过
- [ ] 能解码 `a80425fb` 说出至少 5 项能力
- [ ] 能解释为什么容器内 root 也 mount 不了
- [ ] 能写出只读根 + tmpfs 的完整启动命令
- [ ] 能解释 `no-new-privileges` 与 `--cap-drop` 的互补关系
- [ ] 能说出 `--pids-limit` 与 JVM 线程数的冲突
- [ ] 能说明挂 `docker.sock` 为什么等于放弃隔离

## 12. 下一章

第 31 章进入可观测性：日志驱动与轮转、`docker stats`、cAdvisor + Prometheus + Grafana 的监控栈。
