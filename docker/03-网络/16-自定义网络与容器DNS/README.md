# 16 自定义网络与容器 DNS

## 一句话结论

`docker network create` 建的自定义 bridge 网络**自带 DNS**（127.0.0.11），容器之间可以直接用**容器名**互相访问，不用记 IP。这是单机容器编排的基础，Compose 默认就是这么做的。

## 最小可运行案例

```bash
docker network create mynet
docker run -d --name api --network mynet nginx:alpine
docker run --rm --network mynet alpine ping -c1 api     # 直接用名字
```

## 怎么跑

```powershell
cd "03-网络\16-自定义网络与容器DNS\examples"
uv run python verify.py
```

## 核心命令

| 命令 | 作用 |
| --- | --- |
| `docker network create NAME` | 建自定义 bridge 网络 |
| `--subnet 172.28.0.0/16` | 指定网段 |
| `--network NAME` | 容器接入网络 |
| `--network-alias api` | 给容器加可解析别名 |
| `docker network connect NET C` | 把运行中容器接入网络 |
| `docker network disconnect NET C` | 断开 |
| `docker network inspect -f '{{len .Containers}}'` | 查网络内容器数 |

## 名称解析机制

```text
容器 A 查 "api"
  → /etc/resolv.conf 指向 127.0.0.11
  → Docker 内嵌 DNS 查该网络的容器记录
  → 命中容器名/别名 → 返回容器 IP
```

同一个容器可以加入**多个网络**，每个网络里都有一个 IP 和一套名字。

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 名字解析失败 | 容器在默认 bridge | 用自定义网络 |
| 别名冲突 | 同网络两个容器同名/同别名 | 换别名 |
| 容器 ping 不通但能 curl | ICMP 被限制 | 用应用层验证 |
| 网络隔离后连不上依赖 | 不在同一网络 | `network connect` |
| 自定义子网与内网冲突 | 网段重叠 | 换 `--subnet` |
| 容器重启后名字变 | 用了 `--name` 外的临时名 | 固定 `--name` |
| 跨网络访问不通 | 未连通 | 连到同一网络或 connect |

## 毕业自查

- [ ] 10/10 通过
- [ ] 能解释 127.0.0.11 是什么
- [ ] 会用 `--network-alias` 给服务起别名
- [ ] 知道怎么让两个网络的容器互通
