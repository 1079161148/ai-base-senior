# 01 容器与虚拟机

## 一句话结论

容器不是"迷你虚拟机"，它是被 **namespace** 隔离、被 **cgroups** 限制资源、用 **OverlayFS** 拼装文件系统的普通进程。它和宿主机共用内核，所以快、小、但隔离弱于虚拟机。

## 最小可运行案例

```bash
# 看隔离：hostname 是容器 ID，PID 1 是容器主进程
docker run --rm alpine hostname
docker run --rm alpine cat /proc/1/comm

# 看限制：--memory 后容器内看到的内存上限
docker run --rm --memory 64m alpine cat /sys/fs/cgroup/memory.max
```

## 怎么跑

```powershell
cd "00-认知与安装\01-容器与虚拟机\examples"
uv run python verify.py
```

## 隔离三件套

| 技术 | 解决什么 | 怎么验证 |
| --- | --- | --- |
| namespace | 独立进程/网络/文件系统视图 | `/proc/1/ns` 里有 pid/net/mnt/uts |
| cgroups | 限制 CPU、内存 | `--memory 64m` → `memory.max=67108864` |
| OverlayFS | 多层只读 + 可写层叠加 | `docker info` 的 Storage Driver |

## 最容易踩的坑

| 错误认知 | 真相 |
| --- | --- |
| 容器有独立内核 | 共用宿主机内核，`uname -r` 与宿主一致 |
| 容器隔离等同虚拟机 | 内核共享，逃逸风险高于 VM |
| `--memory` 不生效 | 容器内 `/sys/fs/cgroup` 能看到限制 |
| Windows 上跑的是 Windows 容器 | Docker Desktop 背后是小 Linux 虚拟机（WSL2） |
| 容器里 `localhost` 是宿主机 | 是容器自己 |

## 毕业自查

- [ ] 12/12 通过
- [ ] 能说出 namespace 和 cgroups 各解决什么问题
- [ ] 能解释为什么容器启动是秒级
