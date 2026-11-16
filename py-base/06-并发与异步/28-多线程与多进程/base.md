# 28 多线程与多进程 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「进程 vs 线程 vs 协程七维对比、`threading` 模块（创建线程/`Thread` 类/守护线程）、线程安全与竞态条件（`Lock`/`RLock`/`Semaphore`/`Event`/`Queue`/`ThreadPoolExecutor` 与 asyncio 配合/`Thread Local`）、多线程常见问题（GIL/CPU 密集/死锁）、何时用线程何时用协程」逐条展开，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 / Windows / 20 核实测） |
| 前置 | 第 16、18 章（异常、上下文管理器） |
| 覆盖范围 | 三方对比、`threading.Thread` 全用法、六种同步原语、`ThreadPoolExecutor`/`ProcessPoolExecutor`、GIL 实测、竞态与死锁、`threading.local`、与 asyncio 配合、选型决策 |
| 明确不覆盖 | 异步细节（24–27 章）、`multiprocessing` 的 Manager/共享内存高级用法、C 扩展、`subinterpreters` |
| 学完验收 | 能解释 GIL 下线程为何对 I/O 有用、能复现并修复竞态、能按任务类型选线程/进程/协程（见第 12 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Tn]` `` 指向第 11 节官方链接；标「实测」的是本机 Python 3.12.8 / Windows / 20 逻辑核运行结果。耗时数据随机器差异较大，文档强调的是**数量级与方向**，不是绝对值。

**推荐顺序**：

```text
1 三方对比（第 1 节）      → 先建立选型直觉
2 threading（第 2 节）     → 线程基础
3 线程安全（第 3 节）      → 锁与队列（重点）
4 执行器（第 4 节）        → 高层 API
5 与 asyncio（第 5 节）    → 桥接
6 常见问题（第 6 节）      → GIL/死锁
7 选型决策（第 7 节）      → 决策树
8 综合示例（第 8 节）
9 注意事项（第 9 节）      → 40 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责 API 穷举、实测数据与坑。冲突时以本文件为准。

## 1. 进程 vs 线程 vs 协程

### 1.1 七维对比

| 维度 | 进程（Process） | 线程（Thread） | 协程（Coroutine） |
| --- | --- | --- | --- |
| 运行载体 | 操作系统内核态 | 操作系统内核态 | 用户态（事件循环） |
| 资源开销 | 极高：独立地址空间、文件描述符表，`fork`/`clone` | 中等：共享地址空间，独立栈（数 MB） | 极低：共享线程栈，状态极小（几 KB） |
| 切换成本 | 最贵：TLB 刷新、页表切换 | 昂贵：内核态切换，数百 CPU 周期 | 非常廉价：纯用户态，数十 CPU 周期 |
| 数据共享 | 需 IPC（管道、共享内存、socket） | 共享内存，需同步机制 | 单线程天然安全，但 `await` 处有竞态 |
| 利用多核 | ✅ 原生支持 | ❌（CPython 受 GIL 限制） | ❌ 单线程内不支持 |
| 适用场景 | 隔离性要求高的多任务、CPU 密集 | CPU 密集型（受 GIL 限制）、同步阻塞 I/O | 海量 I/O 密集 |
| 创建数量级 | 十级别 | 百/千级别 | 万/十万级别 |

**依据**：`[T1]` `[T2]` `[T3]` `[T5]`

### 1.2 实测：同一批 CPU 任务

```python
def cpu_work(rounds=1_000_000):
    total = 0
    for index in range(rounds):
        total += index * index
    return total
```

| 方式 | 耗时 | 说明 |
| --- | --- | --- |
| 串行 2 次 | 66ms | 基准 |
| 2 线程 | 64ms | **没有加速**（GIL） |
| 2 进程 | 174ms | **更慢**（进程启动与序列化开销） |

```text
CPU_SERIAL_MS 66
CPU_THREADS_MS 64
CPU_PROCESSES_MS 174
```

| 结论 | 说明 | 依据 |
| --- | --- | --- |
| 线程对 CPU 密集无加速 | GIL 使字节码串行 | `[T5]` |
| 进程对小任务是负优化 | 启动成本 > 计算收益 | `[T2]` |
| 进程适合「足够大」的任务 | 需要摊薄启动成本 | `[T2]` |

> 注意：这个实测结果（进程比串行慢 2.6 倍）经常被忽略——**进程不是银弹**。任务粒度小于几十毫秒时，用进程池反而拖慢。`[T2]`

### 1.3 实测：同一批 I/O 任务

```text
IO_SERIAL_MS 151
IO_THREADS_MS 52
```

| 方式 | 耗时 | 加速比 |
| --- | --- | --- |
| 串行 3 × 50ms | 151ms | 1× |
| 3 线程 | 52ms | ≈ 3× |

| 原因 | 说明 | 依据 |
| --- | --- | --- |
| `time.sleep` 会释放 GIL | 等待期间别的线程能跑 | `[T5]` |
| 网络/磁盘 I/O 同理 | 阻塞时释放 GIL | `[T5]` |
| 所以线程对 I/O 密集有效 | 这是 GIL 设计的前提 | `[T5]` |

### 1.4 三方选型速查

| 任务特征 | 首选 | 次选 | 依据 |
| --- | --- | --- | --- |
| 网络请求多、可 async | 协程 | 线程池 | `[T3]` |
| 只有同步库、I/O 阻塞 | 线程池 | 进程池 | `[T3]` |
| CPU 密集、任务大 | 进程池 | 原生扩展 | `[T2]` |
| 需要隔离/崩溃不影响主进程 | 进程 | —— | `[T2]` |
| 万级并发连接 | 协程 | —— | 27 章 |
| 少量长任务 | 线程 | —— | `[T1]` |

## 2. threading 模块

### 2.1 三种创建方式

```python
# 1 函数 + target
thread = threading.Thread(target=body, args=("t1", log), name="worker-1")
thread.start()
thread.join()

# 2 继承 Thread
class Worker(threading.Thread):
    def run(self):
        ...

# 3 线程池（推荐）
with ThreadPoolExecutor(max_workers=3) as pool:
    pool.map(fn, items)
```

| 方式 | 适用 | 依据 |
| --- | --- | --- |
| `target` | 一次性任务 | `[T1]` |
| 继承 `Thread` | 需要状态/多方法 | `[T1]` |
| 线程池 | 批量、复用 | `[T3]` |

### 2.2 `Thread` 常用属性

```python
thread = threading.Thread(target=body, args=("t1", log), name="worker-1")
print(thread.is_alive(), thread.name, thread.daemon)
thread.start()
thread.join()
print(thread.is_alive(), log)
```

实测：

```text
THREAD_BEFORE_START False worker-1 False
THREAD_AFTER_JOIN False ['start t1', 'end t1']
```

| 成员 | 含义 | 依据 |
| --- | --- | --- |
| `start()` | 启动（只能一次） | `[T1]` |
| `join(timeout=None)` | 等待结束 | `[T1]` |
| `is_alive()` | 是否运行中 | `[T1]` |
| `name` / `getName()` | 线程名 | `[T1]` |
| `daemon` | 是否守护线程 | `[T1]` |
| `ident` / `native_id` | 线程标识 | `[T1]` |
| `run()` | 线程体（可重写） | `[T1]` |

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 重复 `start()` | `RuntimeError` | `[T1]` |
| `join()` 前未 `start()` | `RuntimeError` | `[T1]` |
| 主线程退出时非守护线程会被等待 | 进程不结束 | `[T1]` |

### 2.3 守护线程

```python
daemon = threading.Thread(target=daemon_body, daemon=True)
daemon.start()
daemon.join(timeout=0.01)
```

实测：

```text
DAEMON_FLAG True True
DAEMON_AFTER_TIMEOUT_JOIN True []
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `daemon=True` 表示「主线程退出时不等待」 | 会被强行终止 | `[T1]` |
| 守护线程可能在任意时刻被杀 | 不能做清理 | `[T1]` |
| `join(timeout)` 超时后线程仍在跑 | 实测 `True` | `[T1]` |
| 必须在 `start()` 前设置 `daemon` | 之后改报错 | `[T1]` |

> 注意：守护线程**不适合**做写文件、提交事务这类收尾工作——主线程一退出就被杀，数据可能只写了一半。要保证完成的用非守护线程 + `join()`。`[T1]`

### 2.4 `Timer`

```python
timer = threading.Timer(0.05, callback, args=("timer-fired",))
timer.start()
timer.join()
```

实测：

```text
TIMER ['timer-fired']
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `Timer` 是 `Thread` 子类 | 延迟执行 | `[T1]` |
| `cancel()` 可在触发前取消 | 竞态：可能已触发 | `[T1]` |
| 只执行一次 | 周期任务要自己循环 | `[T1]` |

### 2.5 线程信息

| API | 作用 | 依据 |
| --- | --- | --- |
| `threading.current_thread()` | 当前线程对象 | `[T1]` |
| `threading.main_thread()` | 主线程 | `[T1]` |
| `threading.active_count()` | 活跃线程数 | `[T1]` |
| `threading.enumerate()` | 所有活跃线程 | `[T1]` |

实测启动前：

```text
ACTIVE_THREADS 1 MainThread
```

## 3. 线程安全与竞态条件

### 3.1 竞态：无锁自增会丢

```python
counter = {"value": 0}

def unsafe():
    for _ in range(20_000):
        value = counter["value"]
        sum(range(50))          # 放大「读」与「写」之间的窗口
        counter["value"] = value + 1

threads = [threading.Thread(target=unsafe) for _ in range(8)]
```

实测：

```text
RACE_NO_LOCK_TOTAL 33029 EXPECTED 160000
RACE_WITH_LOCK_TOTAL 160000
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 丢失约 79% 的更新 | 33029 / 160000 | `[T1]` |
| 加锁后精确 160000 | 读改写原子 | `[T1]` |
| 小规模（10 线程 × 1 次）可能测不出 | 窗口太小 | `[T1]` |

> 注意：竞态测试必须**放大窗口**（更多循环、中间加计算），否则会被 GIL 的字节码粒度掩盖，得出「没有竞态」的错误结论。`[T1]`

### 3.2 GIL 为什么不能替代锁

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| GIL 保证「同一时刻一个线程跑字节码」 | 不是「操作原子」 | `[T5]` |
| `x += 1` 是多条字节码 | 中间可能被切换 | `[T5]` |
| 切换点在字节码边界 | 读与写之间可能让出 | `[T5]` |
| 所以仍需锁 | 保护复合操作 | `[T1]` |

### 3.3 `Lock`：互斥锁

```python
guard = threading.Lock()

with guard:
    value = counter["value"]
    counter["value"] = value + 1
```

| 方法 | 作用 | 依据 |
| --- | --- | --- |
| `acquire(blocking=True, timeout=-1)` | 获取锁 | `[T1]` |
| `release()` | 释放 | `[T1]` |
| `locked()` | 是否被持有 | `[T1]` |
| `with lock:` | 自动获取/释放 | `[T1]` |

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 不可重入 | 同线程二次获取会死锁 | `[T1]` |
| 建议一律用 `with` | 异常也能释放 | `[T1]` |
| 忘记 `release` | 永久阻塞 | `[T1]` |

实测不可重入（用超时避免卡死）：

```python
def try_reenter():
    with plain_lock:
        reenter_state["acquired"] = plain_lock.acquire(timeout=0.1)
```

```text
LOCK_NOT_REENTRANT False
```

### 3.4 `RLock`：可重入锁

```python
rlock = threading.RLock()

def reenter(depth=2):
    with rlock:
        if depth > 0:
            reenter(depth - 1)

reenter()
```

```text
RLOCK_REENTRANT True
```

| 对比 | `Lock` | `RLock` | 依据 |
| --- | --- | --- | --- |
| 同线程重入 | 死锁 | ✅ 允许 | `[T1]` |
| 释放次数 | 1 次 | 获取几次释放几次 | `[T1]` |
| 性能 | 略快 | 略慢 | `[T1]` |
| 适用 | 简单互斥 | 递归/可重入调用链 | `[T1]` |

### 3.5 `Semaphore`：计数信号量

```python
sem = threading.Semaphore(2)

with sem:
    do_work()
```

实测峰值：

```text
SEMAPHORE_PEAK 2
```

| API | 作用 | 依据 |
| --- | --- | --- |
| `Semaphore(n)` | 最多 n 个并发 | `[T1]` |
| `BoundedSemaphore(n)` | 释放超限报错 | `[T1]` |
| `acquire()` / `release()` | 手动控制 | `[T1]` |
| `with sem:` | 自动 | `[T1]` |

> 注意：`Semaphore` 不检查「释放次数是否超过初始值」，写错逻辑会让并发上限悄悄变大。要严格就用 `BoundedSemaphore`。`[T1]`

### 3.6 `Event`：线程间通知

```python
event = threading.Event()
event.wait(timeout=1)
event.set()
```

实测：

```text
EVENT_BEFORE_SET False []
EVENT_AFTER_SET True ['woken']
```

| 方法 | 作用 | 依据 |
| --- | --- | --- |
| `set()` | 置位，唤醒所有等待 | `[T1]` |
| `clear()` | 复位 | `[T1]` |
| `is_set()` | 查询 | `[T1]` |
| `wait(timeout=None)` | 阻塞等待（**会阻塞线程**） | `[T1]` |

| 对比 | `threading.Event` | `asyncio.Event` | 依据 |
| --- | --- | --- | --- |
| `wait()` | 阻塞线程 | 挂起协程 | `[T1]` `[T3]` |
| 用在协程里 | ❌ 卡住循环 | ✅ | 27 章 |

### 3.7 `Condition`：带谓词的等待

```python
condition = threading.Condition()
with condition:
    condition.wait_for(lambda: shared["ready"], timeout=1)
```

实测：

```text
CONDITION ['notified']
```

| 方法 | 作用 | 依据 |
| --- | --- | --- |
| `wait(timeout=None)` | 释放锁并等待通知 | `[T1]` |
| `wait_for(predicate)` | 谓词为真才返回 | `[T1]` |
| `notify(n=1)` | 唤醒一个 | `[T1]` |
| `notify_all()` | 唤醒全部 | `[T1]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| 不在 `with condition` 内 `wait` | `RuntimeError` | `[T1]` |
| 用 `if` 而非 `while` 判断 | 虚假唤醒 | `[T1]` |
| 忘记 `notify` | 永久等待 | `[T1]` |

### 3.8 `queue.Queue`：线程安全队列

```python
channel = queue.Queue(maxsize=2)
channel.put(item)
item = channel.get()
channel.task_done()
channel.join()
```

实测：

```text
QUEUE_DONE [0, 1, 2, 3, 4] 0
```

| 方法 | 作用 | 依据 |
| --- | --- | --- |
| `put(x, block=True, timeout=None)` | 满时阻塞 | `[T6]` |
| `put_nowait(x)` | 满时抛 `Full` | `[T6]` |
| `get(...)` | 空时阻塞 | `[T6]` |
| `get_nowait()` | 空时抛 `Empty` | `[T6]` |
| `task_done()` | 标记完成 | `[T6]` |
| `join()` | 等全部完成 | `[T6]` |
| `qsize()` / `empty()` / `full()` | 状态 | `[T6]` |

| 队列类型 | 特点 | 依据 |
| --- | --- | --- |
| `Queue` | FIFO | `[T6]` |
| `LifoQueue` | LIFO（栈） | `[T6]` |
| `PriorityQueue` | 按优先级 | `[T6]` |

> 注意：`Queue` 的 `qsize()` 在多线程下只能当参考——你读取的瞬间可能已经变了。判断空/满不要靠 `qsize()`，用 `get_nowait` + 捕获 `Empty`。`[T6]`

### 3.9 `Thread Local`：线程独立数据

```python
local = threading.local()

def local_worker(name):
    local.value = name
    time.sleep(0.01)
    observed[name] = getattr(local, "value", None)
```

实测：

```text
THREAD_LOCAL [('w0', 'w0'), ('w1', 'w1')]
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 每个线程看到自己的副本 | 互不干扰 | `[T8]` |
| 适合 | 请求上下文、数据库连接 | `[T8]` |
| 不适合 | 需要跨线程共享的数据 | `[T8]` |
| 替代方案 | `contextvars`（异步场景） | 27 章 |

### 3.10 死锁与规避

```python
def lock_order_left():
    with first:
        time.sleep(0.01)
        if second.acquire(timeout=0.05):
            second.release()
            deadlock_reported.append("left-acquired")
        else:
            deadlock_reported.append("left-timeout")
```

实测：

```text
DEADLOCK_AVOIDED ['left-acquired', 'right-timeout']
```

| 死锁条件 | 说明 | 依据 |
| --- | --- | --- |
| 互斥 | 资源不可共享 | `[T1]` |
| 持有并等待 | 拿着一个等另一个 | `[T1]` |
| 不可剥夺 | 不能强行抢 | `[T1]` |
| 循环等待 | A 等 B、B 等 A | `[T1]` |

| 规避手段 | 做法 | 依据 |
| --- | --- | --- |
| 统一加锁顺序 | 所有线程按同一顺序获取 | `[T1]` |
| 加超时 | `acquire(timeout=...)` | `[T1]` |
| 减小锁粒度 | 少嵌套 | `[T1]` |
| 用队列替代共享状态 | 消息传递 | `[T6]` |

> 注意：死锁最难的不是修，是复现。生产上宁可给 `acquire` 加超时 + 告警，也不要赌「顺序应该没事」。`[T1]`

## 4. `concurrent.futures`：高层执行器

### 4.1 `ThreadPoolExecutor`

```python
with ThreadPoolExecutor(max_workers=3) as pool:
    results = list(pool.map(fn, items))
```

| 方法 | 作用 | 依据 |
| --- | --- | --- |
| `submit(fn, *args)` | 提交单个，返回 Future | `[T3]` |
| `map(fn, iterable)` | 批量，**保序**返回 | `[T3]` |
| `shutdown(wait=True)` | 关闭 | `[T3]` |
| `with` 语句 | 自动 shutdown | `[T3]` |

实测保序：

```text
MAP_ORDERED [0.03, 0.01, 0.02]
COMPLETION_ORDER [0.01, 0.02, 0.03]
```

| 方法 | 顺序 | 依据 |
| --- | --- | --- |
| `map` | 输入顺序 | `[T3]` |
| `as_completed` | 完成顺序 | `[T3]` |

### 4.2 默认 worker 数

```python
with ThreadPoolExecutor() as pool:
    print(pool._max_workers)
```

实测（20 逻辑核）：

```text
DEFAULT_WORKERS 24
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 默认约 `min(32, cpu + 4)` | 3.12 行为 | `[T3]` |
| 本机 20 核 → 24 | 符合公式 | `[T3]` |
| 生产建议显式设置 | 避免机器差异 | `[T3]` |

### 4.3 异常传播

```python
bad = pool.submit(raise_value_error, 7)
print(type(bad.exception()).__name__)
```

实测：

```text
EXC_VIA_EXCEPTION ValueError
EXC_VIA_RESULT bad 7
MAP_RAISES bad 1
```

| 方式 | 行为 | 依据 |
| --- | --- | --- |
| `future.exception()` | 返回异常对象 | `[T3]` |
| `future.result()` | 重新抛出 | `[T3]` |
| `map` 迭代 | 迭代到该项时抛出 | `[T3]` |
| 不取结果 | 静默丢失 | `[T3]` |

> 注意：`map` 的异常是在**迭代时**抛出的，不是提交时。所以 `list(pool.map(fn, items))` 会中断在第一个失败项，后面的结果丢失。`[T3]`

### 4.4 `ProcessPoolExecutor`

```python
with ProcessPoolExecutor(max_workers=2) as pool:
    print(list(pool.map(cpu_work, [10])))
```

实测：

```text
PROCESS_OK 285
PROCESS_MAP_KEEPS_ORDER True
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 参数与返回值必须可 pickle | 跨进程传输 | `[T2]` |
| 目标函数必须模块级 | 否则无法 pickle | `[T2]` |
| Windows 必须 `if __name__ == "__main__"` | spawn 启动方式 | `[T2]` |
| 启动成本高 | 适合大任务 | `[T2]` |

实测 lambda 失败：

```text
PROCESS_LAMBDA_ERR AttributeError Can't get local object 'main.<locals>.<lambda>'
```

| 不可 pickle 的常见对象 | 替代 | 依据 |
| --- | --- | --- |
| `lambda` | 顶层 `def` | `[T2]` |
| 局部函数/闭包 | 顶层函数 | `[T2]` |
| 打开的文件/连接 | 句柄不能跨进程 | `[T2]` |
| 线程锁 | 进程间不共享 | `[T2]` |

### 4.5 `multiprocessing.Queue`

```python
channel = multiprocessing.Queue()
receiver = multiprocessing.Process(target=child_put, args=(channel,))
receiver.start()
print(channel.get(timeout=5))
```

```text
MP_QUEUE child-value
```

| 对比 | `queue.Queue` | `multiprocessing.Queue` | 依据 |
| --- | --- | --- | --- |
| 跨线程 | ✅ | ✅ | `[T2]` `[T6]` |
| 跨进程 | ❌ | ✅（序列化） | `[T2]` |
| 性能 | 快 | 慢（pickle） | `[T2]` |

## 5. 与 asyncio 配合

| 方向 | API | 依据 |
| --- | --- | --- |
| 协程 → 线程池 | `await asyncio.to_thread(fn)` | `[T3]` |
| 协程 → 线程池 | `await loop.run_in_executor(pool, fn)` | `[T3]` |
| 协程 → 进程池 | `await loop.run_in_executor(ProcessPoolExecutor(), fn)` | `[T3]` |
| 线程 → 协程 | `asyncio.run_coroutine_threadsafe(coro, loop)` | `[T3]` |

```python
# 协程里调用阻塞库
result = await asyncio.to_thread(blocking_call)

# 线程里投递协程
future = asyncio.run_coroutine_threadsafe(coro, loop)
value = future.result(timeout=5)
```

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| 在协程里直接调用 `ThreadPoolExecutor.submit().result()` | 阻塞循环 | `[T3]` |
| 在协程里用 `pool.map` | 阻塞循环 | `[T3]` |
| 在线程里 `await` | 语法错误 | `[T3]` |
| `ProcessPoolExecutor` 在协程里频繁创建 | 启动开销 | `[T2]` |

> 注意：`to_thread` 只是「把阻塞挪走」，不改变 GIL——它适合阻塞 I/O，不适合 CPU 密集。CPU 密集要用 `run_in_executor(ProcessPoolExecutor(), ...)`。`[T3]` `[T2]`

## 6. 多线程常见问题

### 6.1 GIL

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| CPython 用 GIL 保护解释器状态 | 同一时刻一个线程跑字节码 | `[T5]` |
| 切换间隔默认 5ms | `sys.getswitchinterval()`（实测 `0.005`） | `[T5]` |
| I/O 阻塞会释放 GIL | 所以线程对 I/O 有效 | `[T5]` |
| 3.13 起有实验性 free-threading | 默认未启用 | `[T5]` |

实测确认：

```text
PLATFORM win32 SWITCH_INTERVAL 0.005
SWITCH_INTERVAL_NOW 1e-06
```

| 调参 | 效果 | 依据 |
| --- | --- | --- |
| `sys.setswitchinterval(1e-6)` | 切换更频繁，竞态更容易复现 | `[T5]` |
| 调大间隔 | 切换更少，性能略升，响应变差 | `[T5]` |

### 6.2 CPU 密集：为什么该用进程

| 方案 | 多核利用 | 实测（2 次 1M 循环） | 依据 |
| --- | --- | --- | --- |
| 串行 | 1 核 | 66ms | `[T5]` |
| 线程 | 1 核（GIL） | 64ms | `[T5]` |
| 进程 | 2 核 | 174ms（任务太小） | `[T2]` |

| 结论 | 说明 | 依据 |
| --- | --- | --- |
| 线程不能加速 CPU | GIL 串行 | `[T5]` |
| 进程能加速但要看粒度 | 启动成本固定 | `[T2]` |
| 经验阈值 | 单任务 ≥ 50ms 才值得进程 | `[T2]` |

> 注意：上表进程更慢，是「任务太小 + Windows spawn 开销大」的典型结果。同样代码把每任务放大到 1 秒，进程就能接近 2× 加速。**不要用这次实测反推「进程没用」**。`[T2]`

### 6.3 死锁

| 迹象 | 说明 | 依据 |
| --- | --- | --- |
| 进程不退出、CPU 为 0 | 可能死锁 | `[T1]` |
| `py-spy dump` 看到多个线程卡在 `acquire` | 典型 | `[T1]` |
| 加超时后开始报错 | 说明确实有争用 | `[T1]` |

```python
# 排查手段
if not lock.acquire(timeout=1):
    logger.error("lock timeout, possible deadlock", extra={"thread": threading.current_thread().name})
```

### 6.4 线程泄漏

| 原因 | 说明 | 依据 |
| --- | --- | --- |
| `start()` 后从不 `join()` | 线程累积 | `[T1]` |
| 线程池不 `shutdown` | 线程常驻 | `[T3]` |
| 守护线程被误用 | 静默消失 | `[T1]` |

```python
print(threading.active_count(), [t.name for t in threading.enumerate()])
```

### 6.5 上下文切换成本

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 线程数超过 CPU 核数 | 切换开销上升 | `[T1]` |
| 锁争用激烈 | 大量线程空转等待 | `[T1]` |
| 经验 | I/O 型可到几十~几百，CPU 型 ≈ 核数 | `[T3]` |

## 7. 何时用线程、何时用协程

### 7.1 决策树

```text
任务是 CPU 密集吗？
├── 是 → 进程池（任务够大）
└── 否（I/O 密集）
    ├── 依赖库有 async 版本？
    │   ├── 是 → 协程
    │   └── 否
    │       ├── 并发量 > 1000 → 协程 + to_thread
    │       └── 并发量小 → 线程池
    └── 需要崩溃隔离？
        └── 是 → 进程
```

### 7.2 对照表

| 条件 | 推荐 | 依据 |
| --- | --- | --- |
| 只有同步库 + 阻塞 I/O | 线程池 | `[T3]` |
| 可改造成 async | 协程 | 27 章 |
| CPU 密集 + 大任务 | 进程池 | `[T2]` |
| 需要隔离（第三方库不稳） | 进程 | `[T2]` |
| 简单脚本、任务 < 10 | 串行更快 | `[T3]` |
| 万级连接 | 协程 | 27 章 |
| 后台定时任务 | 线程 / `Timer` | `[T1]` |

### 7.3 组合使用

| 场景 | 组合 | 依据 |
| --- | --- | --- |
| 异步服务 + 同步 SDK | 协程主 + `to_thread` | `[T3]` |
| 异步服务 + 重计算 | 协程主 + 进程池 | `[T3]` `[T2]` |
| 批处理脚本 | 线程池 / 进程池 | `[T3]` |
| 常驻服务 | 协程 + 少量线程 | 27 章 |

## 8. 综合示例：按任务类型选执行器

```python
"""第 28 章综合示例：I/O 用线程池，CPU 用进程池。"""

import concurrent.futures
import time


def io_task(name: str) -> str:
    time.sleep(0.02)
    return name + ":ok"


def cpu_task(rounds: int = 10_000) -> int:
    return sum(index * index for index in range(rounds))


def main() -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        io_results = list(pool.map(io_task, ["search", "cache", "translate"]))

    with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:
        cpu_results = list(pool.map(cpu_task, [10_000, 20_000]))

    print("IO", io_results)
    print("CPU", cpu_results)


if __name__ == "__main__":
    main()
```

本机实测输出：

```text
IO ['search:ok', 'cache:ok', 'translate:ok']
CPU [333283335000, 2666466670000]
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `ThreadPoolExecutor(max_workers=3)` | I/O 并行 | `[T3]` |
| `pool.map` | 保序返回 | `[T3]` |
| `ProcessPoolExecutor(max_workers=2)` | 绕开 GIL | `[T2]` |
| `cpu_task` 模块级函数 | 可 pickle | `[T2]` |
| `if __name__ == "__main__"` | Windows spawn 必需 | `[T2]` |

> 注意：`cpu_results` 的数值是 `sum(i*i, 0..n-1)`，可直接手算验证。如果写成 `lambda`，在 Windows 上会因无法 pickle 直接失败。`[T2]`

## 9. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| CPU 密集用线程 | 没有加速（实测 66→64ms） | 进程池 | `[T5]` |
| I/O 密集用进程 | 慢（启动开销） | 线程池 | `[T2]` |
| Windows 下进程池无 `__main__` 保护 | 无限重启子进程 | `if __name__ == "__main__"` | `[T2]` |
| 进程池传 `lambda` | `AttributeError`/`PicklingError` | 顶层 `def` | `[T2]` |
| 进程池传不可 pickle 对象 | 报错 | 只传可序列化数据 | `[T2]` |
| 无锁改共享计数 | 丢更新（实测 33029/160000） | `Lock` | `[T1]` |
| 以为 GIL 让 `+=` 原子 | 仍会丢 | 加锁 | `[T5]` |
| 用 `Lock` 重入 | 死锁 | `RLock` | `[T1]` |
| 加锁顺序不一致 | 死锁 | 统一顺序 | `[T1]` |
| `acquire` 不设超时 | 永久卡死 | `timeout` | `[T1]` |
| 忘记 `release` | 永久阻塞 | `with lock` | `[T1]` |
| `Semaphore` 多 `release` | 并发上限失效 | `BoundedSemaphore` | `[T1]` |
| 用 `qsize()` 判空 | 竞态 | `get_nowait` + `Empty` | `[T6]` |
| `get` 后不 `task_done` | `join()` 卡死 | 每次 `task_done` | `[T6]` |
| 消费者无退出条件 | 线程不结束 | 哨兵/`Event` | `[T6]` |
| 守护线程做收尾 | 数据丢失 | 非守护 + `join` | `[T1]` |
| `join` 无超时 | 卡死 | `join(timeout)` | `[T1]` |
| 重复 `start()` | `RuntimeError` | 一次 | `[T1]` |
| `start()` 后改 `daemon` | `RuntimeError` | 先设 | `[T1]` |
| 线程池不关闭 | 线程泄漏 | `with` | `[T3]` |
| `map` 期望并发顺序 | `map` 保序 | `as_completed` | `[T3]` |
| `map` 异常当全部成功 | 中途中断 | 捕获 + 收集 | `[T3]` |
| 不取 `Future` 结果 | 异常静默 | `result()`/`exception()` | `[T3]` |
| 在协程里 `pool.map` | 阻塞循环 | `to_thread`/`run_in_executor` | `[T3]` |
| 在线程里 `await` | 语法错误 | `run_coroutine_threadsafe` | `[T3]` |
| 线程数 = 任务数 | 切换开销爆炸 | ≈ 核数或并发上限 | `[T1]` |
| 用线程做定时任务栈 | 累积 | `Timer`/调度器 | `[T1]` |
| `Condition` 用 `if` 判断 | 虚假唤醒 | `while`/`wait_for` | `[T1]` |
| 不在 `with condition` 内 `wait` | `RuntimeError` | 加锁 | `[T1]` |
| `Event` 用在协程里 | 阻塞循环 | `asyncio.Event` | 27 章 |
| 用 `threading.local` 存跨线程数据 | 各线程看不到 | 共享 + 锁/队列 | `[T8]` |
| 进程间共享普通对象 | 各自副本 | `Queue`/`Manager` | `[T2]` |
| 子进程里打印大量日志 | 输出交错 | 日志到文件/队列 | `[T2]` |
| 进程池返回大对象 | 序列化开销 | 返回必要字段 | `[T2]` |
| 用进程池做小任务 | 更慢（实测 174ms） | 串行/线程 | `[T2]` |
| 忽略 `active_count` 增长 | 线程泄漏 | 定期检查 | `[T1]` |
| 用 `time.sleep` 轮询 | CPU 空转 | `Event`/`Condition` | `[T1]` |
| 用锁保护整个函数 | 串行化 | 缩小临界区 | `[T1]` |
| 在锁内做 I/O | 长时间持锁 | 移出临界区 | `[T1]` |
| 混用 `asyncio` 与 `multiprocessing` | 事件循环与子进程管理复杂 | 明确边界 | `[T3]` |

## 10. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 默认用执行器，不裸写 `Thread` | 生命周期可控 | `[T3]` |
| 优先「不共享」 | 传值、返回结果 | `[T1]` |
| 共享必加锁，锁粒度最小 | 避免串行化 | `[T1]` |
| 加锁顺序全局统一 | 防死锁 | `[T1]` |
| `acquire` 带超时 | 可观测、可恢复 | `[T1]` |
| CPU 密集用进程且任务够大 | 摊薄启动 | `[T2]` |
| `max_workers` 显式设置 | 机器无关 | `[T3]` |
| 消费每个 Future 的结果 | 不静默失败 | `[T3]` |
| 用 `Queue` 替代手工队列 | 线程安全 | `[T6]` |
| 后台任务用非守护线程 + `join` | 不丢数据 | `[T1]` |
| 协程里同步库用 `to_thread` | 不阻塞循环 | `[T3]` |
| 日志带线程/任务标识 | 可排查 | `[T4]` |

**风格示范**：

```python
"""workers 模块：受控并发的 I/O 批处理。

为什么用线程池而不是协程：下游 SDK 只有同步接口。
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def run_all(
    items: Iterable[str],
    call: Callable[[str], T],
    *,
    limit: int = 8,
) -> list[T]:
    """并发执行，单个失败记录后继续。"""
    results: list[T] = []
    with ThreadPoolExecutor(max_workers=limit) as pool:
        futures = {pool.submit(call, item): item for item in items}
        for future in as_completed(futures):
            name = futures[future]
            error = future.exception()
            if error is not None:
                logger.error("task failed: %s", name, exc_info=error)
                continue
            results.append(future.result())
    return results
```

**边界**：

- GIL 只约束 CPython 字节码；C 扩展与系统 I/O 可释放。
- 进程池的序列化成本可能远超计算收益，任务粒度要够大。
- 线程与协程可以组合，但边界要清晰（谁拥有循环、谁负责关闭）。

## 11. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[T1]` | python.org | https://docs.python.org/3.12/library/threading.html | `Thread`、`Lock`/`RLock`/`Semaphore`/`Event`/`Condition`、守护线程、死锁相关原语 |
| `[T2]` | python.org | https://docs.python.org/3.12/library/multiprocessing.html | 进程、pickle 限制、`Queue`、Windows spawn、`__main__` 保护 |
| `[T3]` | python.org | https://docs.python.org/3.12/library/concurrent.futures.html | `ThreadPoolExecutor`/`ProcessPoolExecutor`、`map` 保序、`as_completed`、异常传播 |
| `[T4]` | PEP 官方 | https://peps.python.org/pep-0008/ | 命名、注释写「为什么」 |
| `[T5]` | python.org | https://docs.python.org/3.12/glossary.html | GIL 定义与语义 |
| `[T6]` | python.org | https://docs.python.org/3.12/library/queue.html | `Queue`/`LifoQueue`/`PriorityQueue`、`task_done`/`join` |
| `[T7]` | python.org | https://docs.python.org/3.12/library/asyncio-dev.html | 与 asyncio 的边界、阻塞隔离 |
| `[T8]` | python.org | https://docs.python.org/3.12/library/threading.html#thread-local-data | `threading.local` 语义 |

> **核对状态**：`[T4]` 与本章 `README.md` 已核对来源一致；其余按 `docs.python.org/3.12` 官方结构整理，**本次未逐页直连复核**。文中「实测」为本机 Python 3.12.8 / Windows / 20 逻辑核结果；耗时数据随机器波动，结论看方向而非绝对值。

## 12. 毕业自查清单

**能说清（概念层）**：

- [ ] GIL 下线程为什么对 I/O 密集仍有效
- [ ] 为什么线程不能加速 CPU 密集
- [ ] 进程为什么可能比串行更慢
- [ ] 线程 / 进程 / 协程七维差异
- [ ] `Lock` 与 `RLock` 的区别
- [ ] `Semaphore` 与 `BoundedSemaphore` 的区别
- [ ] `map` 与 `as_completed` 的顺序差异
- [ ] 进程池为什么要求可 pickle
- [ ] 死锁的四个条件与规避手段

**能写出（代码层）**：

- [ ] `Thread(target=..., args=..., daemon=...)` + `start`/`join`
- [ ] 继承 `Thread` 重写 `run`
- [ ] `Lock` 保护自增并验证不丢
- [ ] `Semaphore` 限流
- [ ] `Event` 通知
- [ ] `Condition` 的 `wait_for`
- [ ] `queue.Queue` 生产者/消费者 + `task_done`/`join`
- [ ] `threading.local` 隔离
- [ ] `ThreadPoolExecutor.map` + `as_completed`
- [ ] `ProcessPoolExecutor` + `__main__` 保护
- [ ] `asyncio.to_thread` / `run_in_executor`

**能判断（避坑层）**：

- [ ] 看到 CPU 密集用线程能指出 GIL
- [ ] 看到进程池传 lambda 能指出 pickle
- [ ] 看到 Windows 无 `__main__` 保护能指出无限启动
- [ ] 看到无锁共享计数能指出竞态
- [ ] 看到 `Lock` 重入能指出死锁
- [ ] 看到 `get` 后不 `task_done` 能指出 `join` 卡死
- [ ] 看到协程里 `pool.map` 能指出阻塞

**能跑通（验收层）**：

- [ ] 运行 `examples/concurrency_demo.py` 并解释保序
- [ ] 把第 8 节示例存成文件运行，输出与文档一致
- [ ] 复现一次 33029/160000 的竞态并加锁修好
- [ ] 对比串行/线程/进程三种方式的耗时

## 13. 下一章衔接

第 29 章 `构建发布`（按教程主线）：并发与异步到此收束，接下来是工程化收尾——打包、发布、项目管理工具、monorepo 与断点调试。

本章留下的伏笔：

1. 并发任务的异常收集方式，会在第 32 章「调试与日志」里再次出现。
2. 线程/进程的选择会影响部署形态（worker 数、内存占用），第 30 章会涉及。
3. `ThreadPoolExecutor` 与 `ProcessPoolExecutor` 是后面所有「批处理」脚本的基础工具。