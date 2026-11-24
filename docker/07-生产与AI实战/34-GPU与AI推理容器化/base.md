# 34 GPU 与 AI 推理容器化 · 完整版

## 0. 怎么用

跑 24/24。本章用零依赖的假推理服务（stdlib HTTP）演示 AI 容器化的**全部工程面**：模型外置、只读挂载、缓存卷、批处理、健康检查、资源限制、GPU 声明。把 `serve.py` 换成 transformers/vLLM，容器配置一行不用改。

## 1. AI 容器和普通容器差在哪

| 维度 | 普通 Web 服务 | AI 推理服务 |
| --- | --- | --- |
| 镜像体积 | 几十到几百 MB | 基础镜像含 CUDA/cuDNN 常见 3–10GB |
| 额外资源 | 无 | GPU、显存、共享内存 |
| 启动时间 | 秒级 | 加载权重几十秒到几分钟 |
| 数据 | 数据库 | 模型权重（GB 级）、tokenizer、缓存 |
| 扩展方式 | 水平扩副本 | 受 GPU 数量限制，常按显存算并发 |
| 冷启动 | 可忽略 | 必须预热（否则首请求超时） |

所以 AI 容器的工程重点不是"能不能跑"，而是**模型怎么放、显存怎么分、冷启动怎么熬**。

## 2. GPU 的三层依赖与实测

```text
① 宿主驱动（Windows: NVIDIA 驱动；Linux: nvidia-driver）
        ↓
② 容器运行时（nvidia-container-toolkit → nvidia runtime / CDI 规范）
        ↓
③ 镜像（nvidia/cuda、pytorch、vllm/vllm-openai 等含 CUDA 用户态库）
```

### 2.1 本机实测结果

| 检查 | 本机结果 | 含义 |
| --- | --- | --- |
| `docker info .Runtimes` | `io.containerd.runc.v2`、`nvidia`、`runc` | ② 已装 |
| `docker info .CDISpecDirs` | `/etc/cdi`、`/var/run/cdi` | 支持 CDI 方式暴露设备 |
| `docker run --gpus all` 是否报错 | 不报错，容器启动 | 参数被接受 |
| `HostConfig.DeviceRequests` | `[{"Driver":"","Count":-1,"Capabilities":[["gpu"]]}]` | 请求已记录 |
| 容器内 `/dev/nvidia0` | **不存在** | ① 没通：设备未真正注入 |
| `nvidia-smi`（alpine） | `no such file or directory` | ③ 缺失：镜像里没有工具 |

**结论：`--gpus all` 被接受 ≠ 能用 GPU。** 这是一个非常常见的误判——daemon 只校验参数与运行时存在，真正的设备注入在运行时阶段，缺失时容器照样起来。

### 2.2 正确的排查顺序

```bash
# 1. 宿主有没有 GPU
nvidia-smi
# 2. 运行时有没有注册
docker info --format '{{json .Runtimes}}'
# 3. 用官方 CUDA 镜像验证端到端
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

第 3 步成功才算通。失败时的三种报错：

| 报错 | 层 | 修法 |
| --- | --- | --- |
| `could not select device driver "" with capabilities: [[gpu]]` | ② | 装 nvidia-container-toolkit，重启 docker |
| `nvidia-smi: not found` | ③ | 换 CUDA 基础镜像 |
| 容器里没有 `/dev/nvidia*`、`nvidia-smi` 报 `No devices were found` | ① | 装/升级驱动；WSL2 需 Windows 侧驱动 + `wsl --update` |

### 2.3 Windows + WSL2 的特殊性

| 事实 | 说明 |
| --- | --- |
| GPU 直通由 WSL2 提供 | 必须在 Windows 装 NVIDIA 驱动（不是 Linux 驱动） |
| Docker Desktop 用 WSL2 后端 | 设置里启用 "Use the WSL 2 based engine" |
| 容器内不能装驱动 | 驱动在宿主，容器只用用户态库 |
| `nvidia` runtime 默认注册 | 新版 Docker Desktop 自带 |

## 3. 模型放哪里

### 3.1 三种方案对比

| 方案 | 镜像体积 | 更新模型 | 多副本 | 推荐度 |
| --- | --- | --- | --- | --- |
| `COPY` 进镜像 | GB 级 | 重新构建 + 推送 | 每副本一份，浪费 | ❌ |
| 只读挂载宿主目录 | 小 | 换文件即可 | 共享一份 | ✅ 单机 |
| 对象存储 + 启动时下载 | 小 | 换路径 | 各自下载（慢） | ✅ 云上（配缓存） |

本章实测：镜像内 `/models` 为空，宿主 48MB 权重通过 `:ro` 挂载进容器，`/healthz` 报 `model_bytes=50331648`，写操作被拒。

### 3.2 只读挂载的意义

| 好处 | 说明 |
| --- | --- |
| 防篡改 | 应用即使被攻破也改不了权重 |
| 共享 | 多个容器挂同一份权重，节省磁盘 |
| 可版本化 | 宿主上按版本目录组织 `models/v3/`，切换只改挂载路径 |

### 3.3 缓存卷

```yaml
volumes:
  - ./models:/models:ro
  - embedcache:/cache        # 命名卷，跨容器复用
```

缓存里放什么：tokenizer 缓存、量化中间产物、预热后的图/引擎（TensorRT）、批处理结果索引。**必须可写、必须持久**，否则每次冷启动都重算。

本章实测：批处理容器写 `/cache/last_batch.json`，容器删除后新容器读出 `count=3`。

## 4. 两种运行形态

| 形态 | 命令 | 特点 | 适用 |
| --- | --- | --- | --- |
| 常驻服务 | `docker run -d -p ...` | 有端口、健康检查、常驻 | 在线推理 |
| 一次性批处理 | `docker run --rm -i ... --batch` | 无端口、随跑随删、stdin/stdout | 离线批量、评测、数据清洗 |

批处理容器的工程价值：**用同一镜像覆盖两种负载**，不需要为离线任务单独打包。

```bash
# 批量嵌入，stdout 直接落文件
cat docs.jsonl | docker run --rm -i \
  -v $PWD/models:/models:ro -v embedcache:/cache \
  my-embed:v1 python serve.py --batch > vectors.jsonl
```

## 5. 资源与显存

### 5.1 容器能限的

| 参数 | 效果 | 实测 |
| --- | --- | --- |
| `--memory 64m` | 超限 OOMKilled | `OOMKilled=true`、`ExitCode=137`、`HostConfig.Memory=67108864` |
| `--cpus 1.0` | CPU 配额 | `NanoCpus=1000000000` |
| `--shm-size 2g` | `/dev/shm` 大小 | 默认仅 64MB |
| `--pids-limit` | 进程数 | 第 30 章 |

### 5.2 容器不能限的：显存

NVIDIA 没有等价的 cgroup 显存限制。手段只有：

| 手段 | 粒度 | 说明 |
| --- | --- | --- |
| 应用参数 | 进程 | vLLM `--gpu-memory-utilization 0.8` |
| `torch.cuda.set_per_process_memory_fraction` | 进程 | 仅 PyTorch |
| MIG | 卡内切片 | A100/H100 支持，硬隔离 |
| 一容器一卡 | 卡 | `--gpus '"device=0"'` |
| 队列/网关 | 服务 | 限制并发数间接控显存 |

### 5.3 `--shm-size` 为什么关键

PyTorch `DataLoader(num_workers>0)` 通过共享内存传张量。`/dev/shm` 默认 64MB，稍大的 batch 就 `Bus error (core dumped)`。

```bash
docker run --shm-size=2g --ipc=host ...   # --ipc=host 也可，但降低隔离
```

## 6. 冷启动与预热

| 手段 | 效果 |
| --- | --- |
| 常驻服务 + 健康检查 | 就绪后才接流量（第 28 章） |
| 启动时预热（跑一条 dummy 请求） | 避免首请求超时 |
| 缓存卷保存编译产物 | 减少重复编译 |
| 多副本 + 就绪探针 | 滚动更新期间不掉请求 |
| 镜像内置权重（仅小模型） | 牺牲体积换启动速度 |

本章测了"启动到 `/healthz` 就绪"的耗时，这个数字是容量规划的输入：**并发 = 副本数 × 单副本吞吐**，而副本启动慢意味着扩容赶不上流量峰值。

## 7. Compose 生产模板

见 `examples/compose.yaml` 与 `compose.gpu.yaml`。要点：

| 配置 | 作用 |
| --- | --- |
| `volumes: ./models:/models:ro` | 权重只读 |
| `embedcache:/cache` | 缓存复用 |
| `gpus: all` | GPU 声明（无卡可删） |
| `shm_size: 2gb` | 多进程数据加载 |
| `deploy.resources.limits` | CPU/内存上限 |
| `healthcheck` | 就绪判定 |
| `NVIDIA_VISIBLE_DEVICES` | 指定可见 GPU |

`docker compose config` 校验这些语法**不需要真实 GPU**，本章已实测通过。

## 8. 逐条验收解读（24 条）

| 组 | 覆盖内容 |
| --- | --- |
| 1–3 | runc / nvidia runtime / CDI 目录 |
| 4–7 | `--gpus all` 被接受、DeviceRequests 记录、设备缺失、声明≠可用 |
| 8–10 | compose 生产配置与 GPU 语法校验 |
| 11–13 | 镜像构建、体积、镜像内无权重 |
| 14–16 | 宿主 48MB 权重、只读挂载可读、写被拒 |
| 17–19 | 就绪耗时、embedding 维度、批处理行数 |
| 20 | 缓存卷跨容器复用 |
| 21–24 | 内存限制、OOMKilled、退出码 137、cgroup 上限 |

## 9. 坑与对策

| 现象 | 根因 | 对策 |
| --- | --- | --- |
| 起了容器但 GPU 不可用 | 驱动/WSL GPU 不通 | 宿主 `nvidia-smi` 先验证 |
| `could not select device driver` | 缺 toolkit | 安装后重启 docker |
| `nvidia-smi` not found | 非 CUDA 镜像 | 换基础镜像 |
| `Bus error` | `/dev/shm` 太小 | `--shm-size=2g` |
| 137 退出 | OOMKilled | 加内存/减 batch |
| 显存 OOM | 无容器级限制 | 应用侧配额 / MIG |
| 镜像巨大 | 权重 COPY 进镜像 | 挂载 |
| 首请求超时 | 未预热 | 预热 + 就绪探针 |
| 每次启动都下载权重 | 无缓存 | 宿主目录 + 缓存卷 |
| 多副本抢同一张卡 | 未分配 device | `--gpus '"device=0"'` |

## 10. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | NVIDIA Container Toolkit 文档、Docker GPU 支持文档、vLLM/TEI 部署文档 |
| `[r3]` | 实测 | 24/24；runtimes/CDI/DeviceRequests、设备缺失、OOMKilled=137、缓存卷复用均为本机实录 |

## 11. 毕业自查

- [ ] 24/24 通过
- [ ] 能画出 GPU 三层依赖并给出排查命令
- [ ] 能解释"参数被接受但用不到 GPU"
- [ ] 能写出模型只读挂载 + 缓存卷的编排
- [ ] 能说出 `--shm-size` 与 `--memory` 各自防什么
- [ ] 能解释显存为什么不受 cgroup 限制
- [ ] 能设计常驻 + 批处理双形态

## 12. 下一章

第 35 章把 AI 应用栈整体容器化：pgvector 向量库 + Agent 服务 + MCP 工具 + DevContainer 开发环境。
