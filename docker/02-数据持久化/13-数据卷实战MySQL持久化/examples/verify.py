"""第 13 章 · 数据卷实战：MySQL 跨容器重建数据不丢。"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(13)
PASSWORD = "study123"


def wait_mysql(name: str, timeout: float = 240.0) -> bool:
    """轮询 SELECT 1，直到能真正执行查询（避开初始化期的临时实例）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        probe = c.run("exec", name, "mysql", "-uroot", f"-p{PASSWORD}", "-N", "-e", "SELECT 1")
        if probe.returncode == 0 and "1" in probe.stdout:
            return True
        time.sleep(3)
    return False


volume = c.name("mysql-data")
c.run("volume", "create", volume)
c.ok("命名卷创建成功", c.volume_exists(volume))

first = c.name("db")
c.run("run", "-d", "--name", first, "-e", f"MYSQL_ROOT_PASSWORD={PASSWORD}",
      "-v", f"{volume}:/var/lib/mysql", "mysql:8.4", timeout=300)
c.ok("MySQL 首次启动就绪", wait_mysql(first))

c.run("exec", first, "mysql", "-uroot", f"-p{PASSWORD}", "-e",
      "CREATE DATABASE demo; CREATE TABLE demo.t(id INT PRIMARY KEY, name VARCHAR(20));"
      "INSERT INTO demo.t VALUES (1,'docker');")
written = c.out("exec", first, "mysql", "-uroot", f"-p{PASSWORD}", "-N", "-e",
                "SELECT name FROM demo.t")
c.equal("首次写入并查询成功", written.strip(), "docker")

c.run("rm", "-f", first)
c.ok("容器已删除", not c.container_exists(first))
c.ok("卷未被删除", c.volume_exists(volume))

volume_files = c.out("run", "--rm", "-v", f"{volume}:/v", "alpine:3.20", "ls", "/v")
c.ok("卷内保存了 MySQL 数据文件", "mysql" in volume_files.lower(), volume_files.replace("\n", " ")[:60])

second = c.name("db2")
c.run("run", "-d", "--name", second, "-e", f"MYSQL_ROOT_PASSWORD={PASSWORD}",
      "-v", f"{volume}:/var/lib/mysql", "mysql:8.4", timeout=300)
c.ok("用同一卷重建后再次就绪", wait_mysql(second))

restored = c.out("exec", second, "mysql", "-uroot", f"-p{PASSWORD}", "-N", "-e",
                 "SELECT name FROM demo.t")
c.equal("重建后数据仍在", restored.strip(), "docker")

rows = c.out("exec", second, "mysql", "-uroot", f"-p{PASSWORD}", "-N", "-e",
             "SELECT count(*) FROM demo.t")
c.equal("数据行数一致", rows.strip(), "1")

mount_type = c.json("inspect", "-f", "{{json .Mounts}}", second)
c.equal("MySQL 数据目录挂载为卷", [m["Type"] for m in mount_type], ["volume"])

raise SystemExit(c.finish())
