# 03 Docker Desktop 桌面端

## 一句话结论

Docker Desktop 是 Windows/macOS 上的"全家桶"：一个 Linux 虚拟机 + dockerd + CLI + Compose + Buildx + Kubernetes，还带图形界面。日常工作用它最省事，但要清楚**容器实际跑在它背后的 Linux VM 里**。

## 最小可运行案例

```powershell
docker context ls                    # 应有 desktop-linux
docker info --format '{{.OperatingSystem}}'
docker desktop version               # Desktop 专属 CLI 插件
```

## 怎么跑

```powershell
cd "00-认知与安装\03-Docker-Desktop桌面端\examples"
uv run python verify.py
```

## 界面导览

| 区域 | 能做什么 |
| --- | --- |
| Containers | 启停、查看日志、进入终端、删除 |
| Images | 查看、拉取、删除、查看层 |
| Volumes | 查看与管理数据卷 |
| Builds | 查看构建历史与缓存 |
| Extensions | 安装第三方扩展 |
| Settings → Resources | 调 CPU/内存/磁盘上限 |
| Settings → Docker Engine | 编辑 `daemon.json` |
| Settings → Kubernetes | 一键启用本地 K8s |

## 关键设置项

| 设置 | 建议 | 说明 |
| --- | --- | --- |
| Resources → CPUs | 按需，别占满宿主 | 决定容器可用 CPU |
| Resources → Memory | 8GB 起，AI 场景更大 | 决定容器可用内存 |
| Resources → Disk | 60GB+ | 镜像/卷占满会报错 |
| General → Start Docker Desktop when you sign in | 开发机可开 | 开机自启 |
| Docker Engine | 加 `registry-mirrors` | 国内加速（第 05 章） |
| Kubernetes | 需要时再开 | 吃内存 |

## 命令行与 GUI 的关系

```powershell
docker context ls          # desktop-linux 是 Desktop 创建的上下文
docker context use default # 切回其它引擎（如远程 Docker）
docker desktop status      # Desktop 状态
docker desktop restart     # 重启 Desktop（不重装）
```

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 改了 Resources 不生效 | 需要 Apply & Restart | 点 Apply 等待重启 |
| `docker` 命令找不到 | Desktop 未启动或 PATH 未加载 | 启动 Desktop、重开终端 |
| VM 磁盘满 | 镜像/卷累积 | `docker system df` 后清理 |
| 容器内路径看不到 | 容器在 VM 内 | 用 bind mount 映射，第 12 章 |
| 想用 GPU 跑模型 | 默认未开 GPU 支持 | Settings → Resources → 启用 GPU |

## 毕业自查

- [ ] 13/13 通过
- [ ] 能在 GUI 里找到 Resources 与 Docker Engine 设置
- [ ] 能解释 `desktop-linux` context 的含义
