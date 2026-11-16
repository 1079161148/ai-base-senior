"""第 14 章示例：__len__ / __getitem__ / __str__。"""

class ToolBatch:
    """一组工具名，支持 len、索引与迭代。"""
    def __init__(self, names):
        self.names = list(names)

    def __len__(self):
        return len(self.names)

    def __getitem__(self, index):
        return self.names[index]

    def __str__(self):
        return "ToolBatch(" + ",".join(self.names) + ")"

batch = ToolBatch(["search", "cache"])
print("长度:", len(batch))
print("索引:", batch[0])
print("迭代:", [name for name in batch])
print("字符串:", str(batch))
