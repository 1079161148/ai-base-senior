# 02 三平台安装 Docker · 完整版

## 0. 怎么用

先按下面步骤装好，再跑 10/10。本章验收是"环境就绪检测"，任何一项不过都说明安装不完整。

## 1. 概念

| 形态 | 平台 | 说明 |
| --- | --- | --- |
| Docker Desktop | Windows / macOS / Linux | 图形化、自带 Linux VM、含 Compose/Buildx/K8s |
| Docker Engine | Linux 服务器 | 无图形界面，生产标准部署 |
| Docker CE 包组 | Linux | `docker-ce` + `docker-ce-cli` + `containerd.io` + 两个插件 |

## 2. 机制

```text
安装 → dockerd 作为 systemd 服务常驻 → CLI 通过 /var/run/docker.sock 调 API
Desktop：在宿主机里跑一个小 Linux VM（WSL2 / HyperKit / QEMU），容器跑在 VM 内
```

## 3. 三平台逐个拆解

### Windows

| 步骤 | 操作 |
| --- | --- |
| 前置 | Win10 22H2+ / Win11，BIOS 开启虚拟化 |
| WSL2 | `wsl --install`、`wsl --update` |
| 下载 | docker.com/products/docker-desktop |
| 安装 | 勾选 Use WSL 2 instead of Hyper-V |
| 验证 | `docker run --rm hello-world` |

### macOS

| 芯片 | 包 |
| --- | --- |
| Apple Silicon | Apple chip 版 dmg |
| Intel | Intel chip 版 dmg |

装到 Applications，首次启动授权，验证同样一条命令。

### Linux（Rocky/RHEL）

```bash
sudo dnf remove -y docker docker-client docker-common podman runc
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
```

包职责：

| 包 | 作用 |
| --- | --- |
| `docker-ce` | 引擎 `/usr/bin/dockerd` |
| `docker-ce-cli` | 命令行 |
| `containerd.io` | 底层运行时（含 runc） |
| `docker-buildx-plugin` | 扩展构建 |
| `docker-compose-plugin` | `docker compose` 子命令 |

GPG 指纹：`060A 61C5 1B55 8A7F 742B 77AA C52F EB6B 621E 9F35`

## 4. 边界条件

- Docker Desktop 商用需注意许可（大型企业有付费要求）。
- Windows 家庭版只能用 WSL2 后端，不能用 Hyper-V 后端。
- 离线环境需 `dnf download` 拉全量 RPM 后本地安装。
- 官方一键脚本（`get.docker.com`）只适合开发测试，生产应走仓库安装。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 不装 compose 插件 | `compose` 命令不存在 | 装 `docker-compose-plugin` | 实测 |
| 用 `docker-compose`（短横线） | 已废弃 | 用 `docker compose` | 官方 |
| 不启 WSL2 | Desktop 无法启动 | `wsl --install` | 官方 |
| Linux 不 enable 服务 | 重启后 daemon 不在 | `systemctl enable --now docker` | 实测 |
| 直接 `chmod 777 docker.sock` | 安全风险 | 加 docker 组 | 官方 |
| 生产用 latest | 版本不可控 | 固定版本号 | 最佳实践 |
| 用 root 跑容器 | 逃逸风险 | 非 root 用户（第 22 章） | 安全 |
| 不验证 Server 版本 | 只装了 CLI | `docker version` 看两段 | 实测 |
| 跳过环境检测 | 后续章节全挂 | 10/10 再走 | 实测 |

## 6. 最佳实践

装完立即跑本章验收；生产环境用 Engine + 固定版本 + 私有仓库，开发机用 Desktop 提升体验。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | docs.docker.com/engine/install |
| `[r3]` | 实测 | Desktop 29.6.2，context=desktop-linux |

> 本次实测 10/10，本机为 `Docker Desktop (containerized)`，`docker compose v5.3.1`，`buildx v0.35.0-desktop.2`。

## 8. 毕业自查

- [ ] 10/10 通过
- [ ] 能写出 Linux 五步安装命令

## 9. 下一章

第 03 章上手 Docker Desktop 桌面端：界面、设置、资源与 CLI 集成。
