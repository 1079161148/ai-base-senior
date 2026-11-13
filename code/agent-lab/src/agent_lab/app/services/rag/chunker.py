"""结构感知分块 + 上下文增强。

**为什么不用固定字数**（教材 3.2）：
固定长度分块会切断语义 —— "该产品支持两种模式" 脱离上下文后，人看不懂是哪个产品，
模型同样看不懂。Pinecone 那条标准很直接：**脱离上下文后，人还能看懂吗？**

**方案选择**：递归字符切分（教材推荐 #3），再叠加上下文增强（Anthropic）。
不用语义分块（#5）—— 每次摄入再跑一遍 embedding，对学习项目不值得。

**分块流程**：
  Markdown → 按标题分段 → 段内递归切（\\n\\n → \\n → 。→ ，）→ 上下文前缀
"""

import re
from dataclasses import dataclass

# 分隔符从大到小：优先在自然边界下刀
_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " "]

# 1 token ≈ 1.6 汉字（bge tokenizer 用 CLS tokenizer，实测）
_TOKEN_PER_CHAR = 1.6


@dataclass(slots=True)
class ChunkSelection:
    """分块结果：content 用于嵌入，raw 用于展示"""

    heading: str      # "三、分块 > 3.3 递归分块"
    raw: str          # 原文
    content: str      # 上下文增强后


def chunk_markdown(
    text: str,
    doc_title: str,
    target_tokens: int = 600,
    min_chars: int = 60,
) -> list[ChunkSelection]:
    """把 Markdown 文本切成语义完整的块。

    target_tokens：目标 token 数（按 1.6 字/token 换算成字符数）。
    不是硬上限，先按段落切，切不动才按句子/逗号下刀 ——
    保证「段落不会莫名其妙断开」比「块大小完全均等」重要。
    """
    max_chars = int(target_tokens / _TOKEN_PER_CHAR)

    # 第一步：按 Markdown 标题把文档切成「节」
    sections = _split_by_headings(text)

    # 第二步：节内递归切
    chunks: list[ChunkSelection] = []
    for heading, body in sections:
        for raw in _recursive_split(body, max_chars):
            raw = raw.strip()
            if len(raw) < 2:
                continue
            content = _enrich(raw, heading, doc_title)
            chunks.append(
                ChunkSelection(heading=heading, raw=raw, content=content)
            )

    # 第三步：过短的块拼回前一块（避免一堆 5 字的碎片）
    return _merge_short(chunks, min_chars)


# ---- 内部函数 ----

_SECTION_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def _split_by_headings(text: str) -> list[tuple[str, str]]:
    """按 Markdown 标题切分，返回 [(标题路径, 正文)]。

    标题路径用 > 串联：'S3 · RAG > 三、分块 > 3.3 递归分块'
    """
    lines = text.split("\n")
    sections: list[tuple[str, str]] = []
    # 标题栈：索引 0 是 h1，索引 1 是 h2，索引 2 是 h3
    heading_stack: list[str] = []
    body_buf: list[str] = []
    in_code = False

    for line in lines:
        # 跳过代码块：里面的 `# 注释`、`### step1` 不是真正的标题。
        # 不跳的话，"# 还有超大的块" 会被当成 h1，"LangChain 思路" 会变成标题栈。
        if line.lstrip().startswith("```"):
            in_code = not in_code
            body_buf.append(line)
            continue

        m = _SECTION_RE.match(line) if not in_code else None
        if m:
            # 遇到新标题：先存前一段
            body = "\n".join(body_buf)
            if heading_stack or body.strip():
                sections.append((" > ".join(heading_stack) or "正文", body))
            body_buf = []

            level = len(m.group(1)) - 1  # 0-based
            title_text = m.group(2).strip()
            # 清掉同级及以下标题
            heading_stack = heading_stack[:level] + [title_text]
        else:
            body_buf.append(line)

    # 最后一段
    body = "\n".join(body_buf)
    if heading_stack or body.strip():
        sections.append((" > ".join(heading_stack) or "正文", body))

    return sections


def _recursive_split(text: str, max_len: int, sep_idx: int = 0) -> list[str]:
    """递归按分隔符切。超长块降级到下一个分隔符。

    sep_idx 0=\\n\\n, 1=\\n, 2=。, 3=！...越往后越细。
    到最后一个分隔符时用单字符切（不会再有超长块）。
    """
    if len(text) <= max_len:
        return [text] if text.strip() else []

    if sep_idx >= len(_SEPARATORS):
        # 无分隔符可用：按字符硬切
        return [text[i : i + max_len] for i in range(0, len(text), max_len)]

    sep = _SEPARATORS[sep_idx]
    parts = text.split(sep)

    out: list[str] = []
    buf = ""
    for p in parts:
        combined = (buf + sep + p) if buf else p
        if len(combined) <= max_len:
            buf = combined
        else:
            if buf:
                out.append(buf)
            # 当前片断超长：用下一级分隔符再切
            if len(p) > max_len:
                out.extend(_recursive_split(p, max_len, sep_idx + 1))
            else:
                buf = p

    if buf:
        out.append(buf)

    return out


def _enrich(raw: str, heading: str, doc_title: str) -> str:
    """上下文增强（Anthropic 的核心创新，教材 3.4）。

    把「该公司营收增长 3%」变成：
    「来自《ACME 财报》三、财务数据 > 3.1 季度营收：
      该公司营收增长 3%。」

    这块增信比什么检索技巧都便宜：不花钱、不增加模型调用，
    只改了索引里的文本，就能让命中率大幅上升。
    """
    location = heading or "正文"
    return f"来自《{doc_title}》{location}：\n{raw}"


def _merge_short(
    chunks: list[ChunkSelection],
    min_len: int,
) -> list[ChunkSelection]:
    """过短的块并到前一块，避免碎片。只合并 raw 文本，heading 取前一块的。"""
    if not chunks:
        return chunks

    out: list[ChunkSelection] = [chunks[0]]
    for chunk in chunks[1:]:
        if len(chunk.raw) < min_len and out:
            last = out[-1]
            out[-1] = ChunkSelection(
                heading=last.heading,
                raw=last.raw + "\n" + chunk.raw,
                content=_enrich(
                    last.raw + "\n" + chunk.raw,
                    last.heading,
                    "",  # 标题前缀已在 raw 里，这里只写正文
                ),
            )
        else:
            out.append(chunk)

    return out


# ---- 纯文本入口 ----

def chunk_text(text: str, title: str) -> list[ChunkSelection]:
    """纯文本（没有标题层级时用）：只有一个"正文"节，里面递归切。"""
    raws = _recursive_split(text, int(600 / _TOKEN_PER_CHAR))
    chunks: list[ChunkSelection] = []
    for raw in raws:
        raw = raw.strip()
        if not raw:
            continue
        content = _enrich(raw, "正文", title)
        chunks.append(ChunkSelection(heading="正文", raw=raw, content=content))
    return _merge_short(chunks, 60)