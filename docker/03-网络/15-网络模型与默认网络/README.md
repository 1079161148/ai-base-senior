# 15 网络模型与默认网络

## 一句话结论

Docker 默认建三个网络：**bridge（默认，NAT 出网）、host（共享宿主网络栈）、none（只有 loopback）**。默认 bridge 的致命短板是**不能用容器名互相访问**，只能记 IP——这正是第 16 章要自定义网络的原因。

## 最小可运行案例

```bash
docker network ls
docker run -d --name a alpine sleep 3600
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' a
docker run --rm --network none alpine ip -o link show    # 只有 lo
```

## 怎么跑

```powershell
cd "03-网络\15-网络模型与默认网络\examples"
uv run python verify.py
```

## 三种默认网络

| 网络 | 行为 | 适用 |
| --- | --- | --- |
| `bridge` | 每个容器独立 IP，NAT 出网，**不支持名称解析** | 默认，单机简单场景 |
| `host` | 直接共享宿主网络命名空间，无独立 IP | 高性能、需绑定宿主端口 |
| `none` | 只有 loopback，完全无网络 | 安全隔离、纯计算任务 |

## 数据流

```text
容器A(172.17.0.4) ──veth──┐
                          ├─ docker0(172.17.0.1) ──NAT──► 外部网络
容器B(172.17.0.5) ──veth──┘
```

| 组件 | 作用 |
| --- | --- |
| docker0 | 宿主上的虚拟网桥，默认网关 172.17.0.1 |
| veth pair | 一头在容器、一头接网桥的虚拟网卡对 |
| iptables MASQUERADE | 出网时做源地址转换 |

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 容器间用名字 ping 不通 | 默认 bridge 无 DNS | 用自定义网络（第 16 章） |
| 容器内 `localhost` 连不上宿主 | localhost 是容器自己 | 用 `host.docker.internal` 或网关 IP |
| host 网络容器端口冲突 | 与宿主共享端口 | 换端口或不用 host |
| none 网络里装包失败 | 无网络 | 需要就换 bridge |
| 容器重启后 IP 变了 | 动态分配 | 自定义网络 + 名称解析 |
| 容器访问宿主机服务失败 | 宿主机防火墙/绑定地址 | 监听 0.0.0.0 或用网关 IP |

## 毕业自查

- [ ] 11/11 通过
- [ ] 能说出 docker0、veth、NAT 各自的角色
- [ ] 知道默认 bridge 为什么不支持容器名
- [ ] 知道 host 网络与 bridge 的本质区别
