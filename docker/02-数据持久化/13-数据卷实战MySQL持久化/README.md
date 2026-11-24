# 13 数据卷实战：MySQL 持久化

## 一句话结论

MySQL 容器的数据在 `/var/lib/mysql`，把这个目录挂到命名卷上，**删掉容器重建后数据依然在**。这是数据卷最典型、也最该先掌握的用法。

## 最小可运行案例

```bash
docker volume create mysql-data
docker run -d --name db \
  -e MYSQL_ROOT_PASSWORD=study123 \
  -v mysql-data:/var/lib/mysql \
  mysql:8.4

docker exec db mysql -uroot -pstudy123 -e "CREATE DATABASE demo;"
docker rm -f db
docker run -d --name db -e MYSQL_ROOT_PASSWORD=study123 -v mysql-data:/var/lib/mysql mysql:8.4
docker exec db mysql -uroot -pstudy123 -e "SHOW DATABASES;"   # demo 还在
```

## 怎么跑

```powershell
cd "02-数据持久化\13-数据卷实战MySQL持久化\examples"
uv run python verify.py
```

> 首次启动 MySQL 要初始化数据目录，通常 20–60 秒，脚本会轮询 `SELECT 1` 等待就绪。

## 关键参数

| 参数 | 作用 | 必须 |
| --- | --- | --- |
| `MYSQL_ROOT_PASSWORD` | root 密码 | 是（否则容器退出） |
| `-v <卷>:/var/lib/mysql` | 数据目录持久化 | 强烈建议 |
| `MYSQL_DATABASE` | 初始化时建库 | 可选 |
| `MYSQL_USER` / `MYSQL_PASSWORD` | 建普通用户 | 可选 |
| `-p 3306:3306` | 暴露端口 | 需要外部访问时 |

## 验证"数据真的持久化"的标准流程

```text
1. 启动容器，建表插数据
2. docker rm -f 删除容器
3. docker volume ls 确认卷还在
4. 用同一卷启动新容器
5. 查询数据 → 还在
```

本机实测：删容器后卷内仍有 `#innodb_redo`、`ibdata` 等文件；重建后 `SELECT name FROM demo.t` 返回 `docker`。

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 容器启动即退出 | 没设 `MYSQL_ROOT_PASSWORD` | 加 `-e` |
| 连不上 MySQL | 还在初始化 | 轮询 `SELECT 1` 而不是只看容器 running |
| 数据"丢了" | 用了匿名卷或没挂 | 用命名卷 |
| `down -v` 后数据没了 | 卷被删 | 别加 `-v` |
| 中文乱码 | 字符集 | 加 `--character-set-server=utf8mb4` |
| 卷被多个 MySQL 共用 | 数据损坏 | 一个实例一个卷 |
| 权限问题 | 卷属主是 mysql 用户 | 不要手工改卷内文件权限 |

## 毕业自查

- [ ] 10/10 通过
- [ ] 能独立完成"删容器重建数据仍在"的实验
- [ ] 知道 MySQL 数据目录在哪
- [ ] 知道为什么不能只看容器 running 判断就绪
