"""第 65 章 · 演示用内存仓储。

【要点】模块之间只通过这一层共享数据，不互相 import 对方的 router。
"""

from models import Item, User

USERS: dict[int, User] = {index: User(id=index, name=f"user{index}") for index in range(1, 6)}

ITEMS: dict[int, Item] = {
    index: Item(id=index, name=f"item{index}", price=index * 10) for index in range(1, 4)
}


def reset() -> None:
    USERS.clear()
    USERS.update({index: User(id=index, name=f"user{index}") for index in range(1, 6)})
    ITEMS.clear()
    ITEMS.update(
        {index: Item(id=index, name=f"item{index}", price=index * 10) for index in range(1, 4)}
    )