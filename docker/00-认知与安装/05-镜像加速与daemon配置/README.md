# 05 镜像加速与 daemon 配置

## 一句话结论

`registry-mirrors` 只对 **Docker Hub** 生效，配在 `daemon.json` 里，改完必须重启 daemon。国内裸连 Hub 经常超时，不配加速基本没法学习。

## 最小可运行案例

```json
// /etc/docker/daemon.json（Linux）
// 或 Docker Desktop → Settings → Docker Engine
{
  "registry-mirrors": ["https://docker.m.daocloud.io"]
}
```

```bash
sudo systemctl restart docker
docker info | grep -A3 "Registry Mirrors"
```

## 怎么跑

```powershell
cd "00-认知与安装\05-镜像加速与daemon配置\examples"
uv run python verify.py
```

## 配置文件位置

| 平台 | 路径 |
| --- | --- |
| Linux Engine | `/etc/docker/daemon.json` |
| Windows Desktop | Settings → Docker Engine（实际存于 `%APPDATA%\Docker\settings-store.json`） |
| macOS Desktop | Settings → Docker Engine |

## 常用配置项

| 键 | 作用 | 示例 |
| --- | --- | --- |
| `registry-mirrors` | Hub 加速 | `["https://docker.m.daocloud.io"]` |
| `insecure-registries` | 允许 HTTP 仓库 | `["192.168.1.10:5000"]` |
| `log-driver` | 日志驱动 | `"json-file"` |
| `log-opts` | 日志轮转 | `{"max-size":"50m","max-file":"3"}` |
| `data-root` | 数据目录 | `"/data/docker"` |
| `default-address-pools` | 自定义网段 | 避免与内网冲突 |
| `live-restore` | 重启 daemon 不杀容器 | `true` |

## 验证顺序

```bash
docker info --format '{{.RegistryConfig.Mirrors}}'   # 生效的加速源
docker info --format '{{.IndexServerAddress}}'       # 默认仓库
docker pull alpine                                  # 实测能否拉下来
```

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 改完不生效 | 没重启 daemon | `systemctl restart docker` |
| Docker 起不来 | daemon.json 不是合法 JSON | 校验 JSON，看 `journalctl -u docker` |
| 加速对 ghcr.io 无效 | 只对 Hub 生效 | ghcr 单独配或走代理 |
| 加速源突然失效 | 公共镜像源常停服 | 换源或自建 registry |
| 云厂商加速地址不通 | 仅限其云内主机 | 用公网源 |
| `latest` 拉不到新版本 | 缓存/镜像源滞后 | 指定明确版本号 |

## 毕业自查

- [ ] 10/10 通过
- [ ] 知道 `registry-mirrors` 只作用于 Docker Hub
- [ ] 会看 `docker info` 的 Registry Mirrors 段
