# 01 Docker 环境与容器

## 一句话结论

常见做法是用 `postgres:16` + `pgadmin4` 两个容器；本教程投屏到 **54321**（pgAdmin 可选 5050），并把数据卷放在项目 `.pgdata`。这一章用 8 条断言确认环境真的能写、能连、能持久化。

## 最小可运行案例

```powershell
docker run -d --name pg16-study `
  -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=study123 -e POSTGRES_DB=study `
  -p 54321:5432 `
  -v "E:/ai-agent-study/PostgreSQL/.pgdata:/var/lib/postgresql/data" `
  postgres:16-alpine
docker exec -it pg16-study psql -U admin -d study
```

```sql
\conninfo
\l
SELECT version();
\q
```

## 怎么跑

```powershell
cd "00-认知与环境\01-Docker环境与容器\examples"
uv run python verify.py
```

预期 `结果：8/8 通过`。若数据目录断言失败，说明容器用的不是本教程的数据卷。

## 核心 API 速查

| 参数 | 作用 | 本教程值 |
| --- | --- | --- |
| `-e POSTGRES_USER` | 超级用户 | `admin` |
| `-e POSTGRES_PASSWORD` | 密码 | `study123` |
| `-e POSTGRES_DB` | 初始库 | `study` |
| `-p 54321:5432` | 端口映射 | 宿主机 54321 |
| `-v ...:/var/lib/postgresql/data` | 数据持久化 | `.pgdata` |
| `docker exec -it` | 进容器执行命令 | — |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 宿主机连 5432 | 连接拒绝 | 连 54321 |
| 不挂数据卷 | 删容器数据全丢 | 挂 `.pgdata` |
| Windows 下载 ARM 版 Docker | 装不上 | 下载 AMD 版 |
| 网上示例的 `admin123` | 密码不匹配 | 本教程统一 `study123` |

## 毕业自查

- [ ] 8/8 通过
- [ ] 能说出四个 `docker run` 参数的作用
- [ ] 能解释为什么数据卷不能删
- [ ] 动手题：停止容器再启动，确认上一章建的 `ch00.isolation_probe` 还在
