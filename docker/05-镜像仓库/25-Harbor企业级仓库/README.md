# 25 Harbor 企业级仓库

## 一句话结论

Harbor 是 registry 的企业封装：多了 **项目/命名空间、RBAC、镜像复制、漏洞扫描、签名、审计日志、Web UI**。部署是"下载离线包 → 改 `harbor.yml` → `./install.sh`"，本质是 docker compose 拉起 9 个容器。

## 最小可运行案例

```bash
# 1. 下载并解压（GitHub releases）
wget https://github.com/goharbor/harbor/releases/download/v2.11.0/harbor-offline-installer-v2.11.0.tgz
tar xzvf harbor-offline-installer-v2.11.0.tgz && cd harbor

# 2. 复制并修改配置
cp harbor.yml.tmpl harbor.yml
vi harbor.yml        # hostname、http.port、harbor_admin_password、data_volume

# 3. 安装（会自动 docker compose up）
sudo ./install.sh

# 4. 验证
curl http://<hostname>:8080/api/v2.0/systeminfo
```

## 怎么跑

```powershell
cd "05-镜像仓库\25-Harbor企业级仓库\examples"
uv run python verify.py
```

> Harbor 完整部署需要约 2–3GB 镜像和 80/443 端口，不适合在教程环境常驻。本章验收做的是**可执行的前置检查**：Compose 版本、端口、磁盘、配置字段、弱密码与扫描工具。

## 本机前置检查结果

| 检查项 | 结果 |
| --- | --- |
| Docker Compose v2 | v5.3.1，满足 |
| 高位端口探测 | 正常 |
| 8080 默认端口 | 被占用 → 需改 `http.port` |
| 磁盘剩余 | 187 GB，满足 |
| `harbor.yml` 六字段 | 齐全 |
| 硬编码弱密码 | 无（用环境变量） |
| `hostname` | 正式域名 |
| 扫描工具 | `docker scout` 可用 |

## harbor.yml 关键字段

| 字段 | 说明 | 生产要求 |
| --- | --- | --- |
| `hostname` | 访问域名 | 必须是真实域名/IP，不能 localhost |
| `http.port` | HTTP 端口 | 默认 8080，可改 |
| `https.port` | HTTPS 端口 | 生产必须启用 |
| `harbor_admin_password` | 管理员密码 | **必须改掉默认 Harbor12345** |
| `database.password` | 内置 PG 密码 | 同 |
| `data_volume` | 数据目录 | 挂到大磁盘 |
| `storage_service` | 存储后端 | 生产可换 S3/OSS |

## Harbor 核心能力

| 能力 | 说明 |
| --- | --- |
| 项目（Project） | 一级命名空间，`harbor/project/image:tag` |
| 成员与角色 | 访客/开发者/维护者/项目管理员 |
| 镜像复制 | 多 Harbor 之间同步 |
| 漏洞扫描 | 集成 Trivy |
| 镜像签名 | Notary / Cosign |
| 审计日志 | 谁推了什么 |
| 配额 | 限制项目容量 |

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 安装脚本报端口占用 | 80/443/8080 被占 | 改 `harbor.yml` |
| 登录不了 | 默认密码未改或写错 | 用 `harbor_admin_password` |
| 推送报 `unauthorized` | 未登录或项目权限不足 | `docker login` + 项目成员 |
| HTTP 推送失败 | 未配 insecure-registries | 客户端配置 |
| 磁盘满 | 无 GC/配额 | 开 GC + 项目配额 |
| 复制失败 | 目标仓库证书/网络 | 检查目标可达与证书 |
| 重启后数据丢 | `data_volume` 未持久化 | 挂载卷 |
| 时间不对 | 容器时区 | 设 `TZ` |

## 毕业自查

- [ ] 15/15 通过
- [ ] 能说出 Harbor 相比 registry 多出的 4 个能力
- [ ] 知道 `harbor.yml` 哪些字段必须改
- [ ] 知道为什么不能沿用默认密码
