# 13 数据卷实战：MySQL 持久化 · 完整版

## 0. 怎么用

跑 10/10。本章用真实 MySQL 8.4 完成"删容器 → 重建 → 数据仍在"的完整闭环。

## 1. 概念

有状态服务（MySQL、Redis、PostgreSQL）都把数据放在容器内固定目录。只要把这个目录挂到卷上，容器的生命周期就与数据解耦。

| 服务 | 数据目录 |
| --- | --- |
| MySQL / MariaDB | `/var/lib/mysql` |
| PostgreSQL | `/var/lib/postgresql/data` |
| Redis | `/data` |
| MongoDB | `/data/db` |

## 2. 机制

```text
mysql:8.4 启动
  → entrypoint 检查 /var/lib/mysql 是否为空
  → 空：初始化（建系统表、设 root 密码）
  → 非空：直接启动，复用已有数据
这正是不挂卷会丢数据、挂卷能复用的根本原因。
```

## 3. 实操拆解（本机实测）

| 步骤 | 命令 | 实测结果 |
| --- | --- | --- |
| 建卷 | `volume create ch13-mysql-data` | 成功 |
| 启动 | `-e MYSQL_ROOT_PASSWORD -v 卷:/var/lib/mysql` | 就绪（轮询 SELECT 1） |
| 写入 | `CREATE DATABASE demo; INSERT ...` | `docker` |
| 删容器 | `rm -f ch13-db` | 卷仍在 |
| 查卷内容 | `alpine ls /v` | `#innodb_redo`、`ibdata` 等 |
| 重建 | 同卷再启动 | 就绪 |
| 查数据 | `SELECT name FROM demo.t` | `docker` |
| 挂载类型 | `inspect .Mounts` | `volume` |

## 4. 边界条件

- `MYSQL_ROOT_PASSWORD` 必须设置，否则容器直接退出。
- 判断就绪不能看容器 `running`，初始化期间 `mysqld` 有临时实例，必须用真实查询探测（`SELECT 1`）。
- 卷一旦被 MySQL 初始化，就绑定该版本的数据格式；跨大版本升级需要 `mysqldump` 迁移。
- 一个卷只能给一个 MySQL 实例用，否则数据损坏。
- Windows/macOS 上绑定挂载 MySQL 数据目录性能差且可能权限问题，务必用命名卷。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 不设 root 密码 | 容器立即退出 | `-e MYSQL_ROOT_PASSWORD` | 官方 |
| 只看 running 判就绪 | 连接被拒 | 轮询真实查询 | 实测 |
| 数据目录用绑定挂载 | 权限/性能问题 | 用命名卷 | 官方 |
| 多实例共用一个卷 | 数据损坏 | 一实例一卷 | 官方 |
| `down -v` 清场 | 数据全没 | 确认后再加 `-v` | 第 11 章 |
| 跨大版本直接换镜像 | 启动失败 | dump 迁移 | 官方 |
| 手工改卷内文件权限 | 权限错乱 | 交给容器管理 | 实测 |
| 不备份 | 卷损坏即丢 | 定期 mysqldump | 最佳实践 |
| 忘记端口映射 | 外部连不上 | `-p 3306:3306` | 第 04 章 |
| 跳过验收 | 持久化没验证 | 10/10 再走 | 实测 |

## 6. 最佳实践

有状态服务 = 命名卷 + 环境变量 + 健康检查 + 定期备份；升级走 dump/restore，不直接换大版本镜像。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | mysql 镜像文档 |
| `[r3]` | 实测 | 10/10，MySQL 8.4 跨容器重建 |

## 8. 毕业自查

- [ ] 10/10 通过
- [ ] 能独立完成 MySQL 持久化实验

## 9. 下一章

第 14 章学绑定挂载与权限：`:z`、只读、单文件挂载与覆盖陷阱。
