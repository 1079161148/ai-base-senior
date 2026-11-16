"""第 22 章示例：标准库三件套。"""

import collections
import json
import pathlib

payload = json.dumps({"tool": "search", "limit": 3}, ensure_ascii=False)
print("序列化:", payload)
print("反序列化:", json.loads(payload))

counts = collections.Counter(["search", "cache", "search"])
print("计数:", counts.most_common())

suffix = pathlib.PurePath("data/tools.json").suffix
print("后缀:", suffix)
