# 02 三平台安装 Docker

## 一句话结论

Windows / macOS 装 **Docker Desktop**（图形化，自带 Linux 虚拟机与 Compose）；Linux 服务器装 **Docker Engine**（无图形界面，生产标配）。装完必须验证四件事：版本、daemon 可达、Compose 插件、能真实跑容器。

## 最小可运行案例

```bash
docker version                 # Client 和 Server 都要有
docker compose version         # 必须能输出 v2.x
docker run --rm hello-world    # 真跑一个容器
```

## 怎么跑

```powershell
cd "00-认知与安装\02-三平台安装Docker\examples"
uv run python verify.py
```

## Windows 安装（推荐 Docker Desktop）

1. **前置**：Windows 10 22H2+ / Windows 11，开启 BIOS 虚拟化（VT-x/AMD-V），启用 WSL2。
2. **下载**：https://www.docker.com/products/docker-desktop/ → Windows 版 `Docker Desktop Installer.exe`。
3. **安装**：双击运行，勾选 `Use WSL 2 instead of Hyper-V`，完成后重启。
4. **首次启动**：接受协议，可跳过登录（Skip）。
5. **验证**：打开 PowerShell 执行 `docker run --rm hello-world`。

```powershell
wsl --install            # 如果没有 WSL2，先装
wsl --update             # 更新内核
wsl --status             # 确认默认版本为 2
```

## macOS 安装（Docker Desktop）

| 芯片 | 下载包 |
| --- | --- |
| Apple Silicon（M1/M2/M3/M4） | `Docker.dmg`（Apple chip） |
| Intel | `Docker.dmg`（Intel chip） |

拖入 Applications → 启动 → 授权 → 验证 `docker run --rm hello-world`。

## Linux 安装（Docker Engine，以 Rocky/RHEL 为例）

```bash
# 1. 卸载冲突软件
sudo dnf remove -y docker docker-client docker-common podman runc

# 2. 添加官方仓库
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# 3. 安装引擎与两个插件
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 4. 启动并开机自启
sudo systemctl enable --now docker

# 5. 验证
sudo docker version && sudo docker compose version
```

Ubuntu/Debian 用 `apt`，把仓库换成 `download.docker.com/linux/ubuntu`，包名相同。

**免 sudo（可选，仅开发机）**：
```bash
sudo usermod -aG docker $USER   # 重新登录生效
```

## 安装后验证清单

| 检查项 | 命令 | 期望 |
| --- | --- | --- |
| 客户端 | `docker version` | Client 有版本 |
| 服务端 | `docker version` | Server 有版本 |
| Compose | `docker compose version` | v2.x |
| Buildx | `docker buildx version` | 有版本 |
| 真实运行 | `docker run --rm hello-world` | 打印 Hello |
| 网络 | `docker pull alpine` | 拉取成功 |

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `Cannot connect to the Docker daemon` | Desktop 没启动 | 启动 Docker Desktop |
| `permission denied /var/run/docker.sock` | 用户不在 docker 组 | `usermod -aG docker $USER` 后重登 |
| WSL2 报 `wsl update failed` | 内核过旧 | `wsl --update` |
| `docker: 'compose' is not a docker command` | 装了旧版 | 装 `docker-compose-plugin` |
| 拉镜像超时 | 网络问题 | 配置镜像加速（第 05 章） |
| 端口 5432/80 被占 | 本机已有服务 | 换映射端口 |

## 毕业自查

- [ ] 10/10 通过
- [ ] 能说出 Desktop 与 Engine 的区别
- [ ] 知道 `latest` 不适合生产
