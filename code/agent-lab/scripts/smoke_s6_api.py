"""S6 接口冒烟：真实调用 LLM 生成计划 → run → 审批 → 幂等重放。

用 8002 这个临时实例跑，避免影响正在用的 8001。
"""

import json
import urllib.request

BASE = "http://127.0.0.1:8002/api/v1"


def call(method: str, path: str, body: dict | None = None) -> object:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def main() -> None:
    print("→ 生成计划…")
    plan = call("POST", "/plans", {"goal": "把待办里未完成的事项列出来，然后删掉标题包含「测试」的那一条"})
    assert isinstance(plan, dict)
    print("  goal:", plan["goal"])
    print("  结构化重试次数:", plan.get("structured_attempts"))
    for s in plan["steps"]:
        print(f"   step{s['idx']} {s['action']} {s['params']} human={s['requires_human']}")

    deleted = [s["idx"] for s in plan["steps"] if s["action"] == "delete_todo"]
    assert deleted, "删除步骤必须被识别"
    assert all(s["requires_human"] for s in plan["steps"] if s["action"] == "delete_todo"), (
        "delete_todo 必须被强制标记 needs human"
    )

    pid = plan["id"]
    print("\n→ run（应在删除前暂停）")
    plan = call("POST", f"/plans/{pid}/run")
    print("  status:", plan["status"])
    print("  steps:", [(s["idx"], s["status"]) for s in plan["steps"]])
    assert plan["status"] in ("awaiting_approval", "done"), plan["status"]

    if plan["status"] == "awaiting_approval":
        idx = next(s["idx"] for s in plan["steps"] if s["status"] == "pending" and s["requires_human"])
        print(f"\n→ 编辑第 {idx} 步参数（改成删除 id=999，不存在的记录）")
        plan = call("PATCH", f"/plans/{pid}/steps/{idx}", {"params": {"id": 999}})
        print("  新参数:", plan["steps"][idx]["params"])

        print(f"\n→ 审批第 {idx} 步")
        plan = call("POST", f"/plans/{pid}/steps/{idx}/approve")
        print("  approved:", plan["steps"][idx]["approved"])

        print("\n→ 再次 run")
        plan = call("POST", f"/plans/{pid}/run")
        print("  status:", plan["status"])
        print("  steps:", [(s["idx"], s["status"]) for s in plan["steps"]])

    print("\n→ 重复 run 两次（验证幂等，不会重复执行）")
    a = call("POST", f"/plans/{pid}/run")
    b = call("POST", f"/plans/{pid}/run")
    print("  两次状态:", a["status"], b["status"])

    print("\n→ 列表接口")
    plans = call("GET", "/plans?limit=5")
    print("  计划数:", len(plans))
    print("\n✅ S6 接口冒烟通过")


main()
