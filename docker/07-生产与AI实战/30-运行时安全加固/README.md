# 30 运行时安全加固

## 一句话结论

容器默认已经不是 root 全权限，但默认值远不够安全：生产容器该做的是 **`--cap-drop ALL` + 按需 `--cap-add`、非 root 用户、只读根文件系统 + `tmpfs`、`no-new-privileges`、pids/内存上限**，这五条能挡掉绝大部分容器逃逸与横向移动路径。

## 最小可运行案例

```bash
docker run -d --name api \
  --user 10001:10001 \
  --cap-drop ALL \
  --cap-add NET_BIND_SERVICE \
  --security-opt no-new-privileges:true \
  --read-only --tmpfs /tmp:size=64m \
  --pids-limit 200 \
  --memory 256m --cpus 0.5 \
  myapp:1.0
```

## 怎么跑

```powershell
cd "07-生产与AI实战\30-运行时安全加固\examples"
uv run python verify.py
```

## 本机实测（18/18）

| 加固项 | 实测 |
| --- | --- |
| 默认能力集 | `CapEff = 00000000a80425fb` |
| 默认能否 `mount` | 否（无 `CAP_SYS_ADMIN`，`permission denied`） |
| `--cap-drop ALL` | `CapEff = 0000000000000000` |
| `--cap-add NET_BIND_SERVICE` | `CapEff = 0000000000000400` |
| `no-new-privileges` | `HostConfig.SecurityOpt` 含该值 |
| `--read-only` 写 `/` | 失败 |
| `--read-only --tmpfs /tmp` | 写 `/tmp` 成功 |
| `--tmpfs /tmp:size=1m` 写 2MB | `No space left on device` |
| `--user 10001:10001` | `id -u` = 10001，`mkdir /x` 被拒 |
| `--pids-limit 32` | `HostConfig.PidsLimit=32`，批量 fork 报 `Resource temporarily unavailable` |
| `--privileged` | `CapEff = 000001ffffffffff`（全开） |
| `--security-opt seccomp=unconfined` | 记录到 `SecurityOpt` |
| daemon 默认 seccomp | `["name=seccomp,profile=builtin","name=cgroupns"]` |

## 四层隔离与各自的加固点

| 层 | 机制 | 加固手段 |
| --- | --- | --- |
| 进程/文件系统 | namespace | 只读根、非 root、`--tmpfs` |
| 权限 | capabilities | `--cap-drop ALL` + 按需 `--cap-add` |
| 提权 | setuid / suid 程序 | `no-new-privileges` |
| 系统调用 | seccomp | 默认 profile（保持默认）/ 自定义 profile |
| 资源 | cgroups | `--memory`、`--cpus`、`--pids-limit` |
| 内核/设备 | devices、LSM | 不挂 `docker.sock`、不加 `--privileged`、AppArmor/SELinux |

## capabilities：默认有哪些、怎么裁

Docker 默认授予的能力（`a80425fb` 对应 14 项）：

```text
CHOWN DAC_OVERRIDE FOWNER FSETID KILL SETGID SETUID
SETPCAP NET_BIND_SERVICE NET_RAW SYS_CHROOT MKNOD
AUDIT_WRITE SETFCAP
```

默认**没有**的能力（这些才是逃逸主力）：

| 能力 | 能干什么 | 为什么默认不给 |
| --- | --- | --- |
| `CAP_SYS_ADMIN` | mount、namespace 操作 | 逃逸核心，最高危 |
| `CAP_SYS_PTRACE` | 注入进程、读内存 | 横向移动 |
| `CAP_NET_ADMIN` | 改路由/防火墙/抓包 | 网络攻击 |
| `CAP_SYS_MODULE` | 加载内核模块 | 直接拿下宿主机 |

`NET_RAW` 在默认集里，能发原始包（可做 ARP 欺骗）——对纯 Web 服务也可以裁掉：

```bash
--cap-drop ALL --cap-add NET_BIND_SERVICE --cap-add CHOWN --cap-add SETUID --cap-add SETGID
```

想知道某个二进制到底需要哪些能力：

```bash
capsh --decode=00000000a80425fb     # 解码位图
docker run --rm --cap-drop ALL myapp  # 逐个加回来，最小可达
```

## 非 root：两个层面

| 层面 | 做法 | 说明 |
| --- | --- | --- |
| 镜像构建期 | `USER appuser`（第 22 章） | 镜像自带默认用户 |
| 运行期 | `--user 10001:10001` | 可覆盖镜像设置，强制非 root |

运行期强制的价值：**即使镜像作者图省事写了 `USER root`，你也能在部署侧兜底**。

注意：

- UID 必须在镜像里存在，或至少目标目录对该 UID 可写；
- 挂载的宿主目录属主必须是该 UID（第 14 章的权限坑）；
- 非 root 无法绑定 1024 以下端口——需要 `CAP_NET_BIND_SERVICE` 或反代监听高位端口。

## 只读根文件系统

```bash
--read-only --tmpfs /tmp --tmpfs /run
```

实测：`--read-only` 下 `touch /blocked` 直接失败；加 `--tmpfs /tmp` 后 `/tmp` 可写。

需要可写的常见路径：

| 路径 | 处理 |
| --- | --- |
| `/tmp` | `--tmpfs /tmp:size=64m` |
| `/run` | `--tmpfs /run` |
| 应用数据 | 命名卷（第 12–14 章） |
| 日志 | 输出到 stdout（第 31 章），不要写文件 |
| Python `__pycache__` | `PYTHONDONTWRITEBYTECODE=1` |
| Nginx pid/cache | 挂卷或改配置到 `tmpfs` |

## seccomp 与 LSM

| 机制 | 默认状态 | 建议 |
| --- | --- | --- |
| seccomp | 启用 `builtin` profile（拦掉 40+ 危险 syscall） | **保持默认**，不要 `unconfined` |
| AppArmor | 视宿主机而定 | Linux 服务器上启用 `docker-default` |
| SELinux | RHEL/CentOS 系 | `--security-opt label=type:container_t` |

自定义 seccomp 的典型场景是"应用需要某个被默认拦掉的 syscall"（如某些 JIT）。原则：**从默认 profile 出发，只加缺的那一个**，绝不 `unconfined`。

## pids 与资源上限

```bash
--pids-limit 200          # 防 fork 炸弹
--memory 256m             # 超了 OOMKilled
--cpus 0.5
--ulimit nofile=65536:65536
```

实测 `--pids-limit 32` 下批量 `sleep 30 &` 会报 `Resource temporarily unavailable`——这就是 fork 炸弹被挡住的样子。

`--pids-limit` 与 `--memory` 必须一起配：只限内存不限进程，攻击者可以靠大量小进程拖垮调度。

## 最危险的三件事

| 做法 | 后果 | 替代 |
| --- | --- | --- |
| 挂 `/var/run/docker.sock` | 容器内等于宿主机 root | 用 API 代理（如 docker-socket-proxy）限制端点 |
| `--privileged` | 全部能力 + 全部设备 + 关闭 seccomp/AppArmor | 按需 `--cap-add` + `--device` |
| `--pid=host` / `--net=host` | 看见并能操作宿主进程/网络 | 用自定义网络 + 端口映射 |

本章实测 `--privileged` 的 `CapEff = 000001ffffffffff`，与默认的 `a80425fb` 差着 29 个能力位。

## Compose 里的等效写法

```yaml
services:
  api:
    image: myapp:1.0
    user: "10001:10001"
    read_only: true
    tmpfs:
      - /tmp:size=64m
    cap_drop: [ALL]
    cap_add: [NET_BIND_SERVICE]
    security_opt:
      - no-new-privileges:true
    pids_limit: 200
    mem_limit: 256m
    cpus: 0.5
    ulimits:
      nofile: { soft: 65536, hard: 65536 }
```

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 加了 `--read-only` 后应用崩 | 需要写 `/tmp`、缓存目录 | `--tmpfs` 或改配置 |
| 非 root 后启动失败 | 挂载目录属主是 root | `chown` 宿主目录或用命名卷 |
| 非 root 绑 80 端口失败 | 1024 以下端口受限 | `CAP_NET_BIND_SERVICE` 或反代 |
| `--cap-drop ALL` 后 `ping` 失败 | 缺 `NET_RAW` | 按需加回，别整体放开 |
| Java 容器莫名 OOMKilled | JVM 看不到 cgroup 限制（老版本） | 升级 JDK 或用 `-XX:MaxRAMPercentage` |
| 自定义 seccomp 后随机崩 | 拦掉了需要的 syscall | 从默认 profile 增量修改 |
| 容器内 `apt install` 后重跑丢失 | 只读根 | 装到构建期（第 18 章） |
| 用 `--privileged` "解决问题" | 安全边界全没了 | 定位到底缺哪个能力/设备 |

## 安全检查清单（部署前逐条勾）

- [ ] `--user` 非 root（或镜像 `USER` 已非 root）
- [ ] `--cap-drop ALL`，按需 `--cap-add`
- [ ] `--security-opt no-new-privileges:true`
- [ ] `--read-only` + 必要 `--tmpfs`
- [ ] `--pids-limit` 与 `--memory` 同时设置
- [ ] 不挂 `docker.sock`，不用 `--privileged`
- [ ] 不用 `--net=host` / `--pid=host`
- [ ] 镜像来自受信仓库且已扫描（第 32 章）
- [ ] seccomp/AppArmor 保持默认或更严

## 毕业自查

- [ ] 18/18 通过
- [ ] 能说出默认能力集里最该裁掉的两项
- [ ] 能解释 `no-new-privileges` 防的是什么
- [ ] 能说出只读根下必须保留可写的三个路径及处理方式
- [ ] 能解释 `--pids-limit` 与 `--memory` 为什么必须一起配
- [ ] 能说出 `--privileged` 为什么等于放弃隔离
- [ ] 能写出 Compose 中等效的加固配置
