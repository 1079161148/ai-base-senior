# 25 Harbor 企业级仓库 · 完整版

## 0. 怎么用

跑 15/15。本章先把前置条件查清楚，再按文档部署，避免装到一半卡在端口或磁盘上。

## 1. 概念

Harbor 由 CNCF 孵化，基于 registry 扩展。架构：

| 组件 | 作用 |
| --- | --- |
| nginx | 反向代理、TLS 终止 |
| harbor-core | 主 API |
| harbor-portal | Web UI |
| registry | 镜像存储（复用第 24 章） |
| postgresql | 元数据 |
| redis | 缓存/会话 |
| jobservice | 异步任务（复制、扫描） |
| trivy | 漏洞扫描 |
| proxy | （可选）外网代理 |

## 2. 机制

```text
./install.sh
  → 生成 docker-compose.yml（harbor.yml 渲染进去）
  → docker compose up -d（9 个容器）
  → 首次启动初始化 PG、创建默认项目 library
访问 http://hostname:8080 → 登录 → 建项目 → docker login → push
```

## 3. 部署拆解

| 步骤 | 命令/要点 |
| --- | --- |
| 下载 | `harbor-offline-installer-vX.Y.Z.tgz` |
| 解压 | `tar xzvf ... && cd harbor` |
| 配置 | `cp harbor.yml.tmpl harbor.yml` 后修改 |
| 必改 | `hostname`、`harbor_admin_password`、`data_volume` |
| 安装 | `sudo ./install.sh` |
| 带扫描 | `sudo ./install.sh --with-trivy` |
| 验证 | `curl http://host:8080/api/v2.0/systeminfo` |
| 停止 | `docker compose down` |
| 升级 | `./prepare` + `docker compose up -d` |

## 4. 本机实测（前置检查）

| 项 | 值 |
| --- | --- |
| Compose | v5.3.1（满足 v2 要求） |
| 磁盘剩余 | 187 GB |
| 8080 | 被占用（需改端口） |
| 高位端口探测 | 正常 |
| `harbor.yml` 字段 | 六项齐全 |
| 弱密码 | 未出现 `Harbor12345` |
| 扫描工具 | `docker scout` 可用 |

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 沿用默认密码 | 被爆破 | 首装即改 | 安全 |
| `hostname: localhost` | 客户端无法解析 | 用域名/IP | 官方 |
| data_volume 放系统盘 | 磁盘满 | 挂大数据盘 | 最佳实践 |
| 不开 HTTPS | 凭证明文 | 配证书 | 安全 |
| 不配 insecure（HTTP） | push 失败 | 客户端配 | 第 05 章 |
| 不做 GC | 空间只增 | 定期 GC | 官方 |
| 不开项目配额 | 单项目占满 | 设 quota | 官方 |
| 不接扫描 | 带漏洞上线 | `--with-trivy` | 安全 |
| 单节点当高可用 | 单点故障 | 多副本/复制 | 官方 |
| 跳过前置检查 | 装到一半失败 | 15/15 先过 | 实测 |

## 6. 最佳实践

生产：HTTPS + 外部 PG/Redis + S3 后端 + 项目配额 + 定期 GC + 复制到异地 + 强制扫描门禁。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Harbor Installation Guide |
| `[r3]` | 实测 | 15/15 前置检查 |

## 8. 毕业自查

- [ ] 15/15 通过
- [ ] 能列出 Harbor 的 9 个组件
- [ ] 知道 `--with-trivy` 的作用

## 9. 下一章

M05 完成。第 26 章进入 M06，学 Docker Compose 编排。
