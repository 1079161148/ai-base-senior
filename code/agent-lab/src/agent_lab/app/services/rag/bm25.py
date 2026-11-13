import math

import jieba


class BM25Index:
    """Okapi BM25 关键词检索。

    为什么单独实现而不是用库：
      - 库（rank_bm25）用英文字符切分，对中文无效
      - 分词在入索引时已经用 jieba 做好，这里只做 IDF 和评分
      - 50 行代码，依赖零，出错一眼能看到哪不全
    """

    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs = docs  # 每个文档是分词后的词列表

        N = len(docs)
        self.avgdl = sum(len(d) for d in docs) / max(1, N)

        # IDF
        df: dict[str, int] = {}
        for doc in docs:
            for term in set(doc):
                df[term] = df.get(term, 0) + 1

        self.idf: dict[str, float] = {}
        for term, freq in df.items():
            # Robertson-Sparck Jones IDF: 平滑版，罕见词权重高但不爆
            self.idf[term] = math.log((N - freq + 0.5) / (freq + 0.5) + 1.0)

    def search(self, query: str, top_k: int = 50) -> list[tuple[int, float]]:
        """返回 [(chunk_index, score)]，score 降序。"""
        tokens = list(jieba.cut_for_search(query))
        terms = [t for t in tokens if len(t.strip()) > 0 and t in self.idf]
        if not terms:
            return []

        scores: list[tuple[int, float]] = []
        for i, doc in enumerate(self.docs):
            doc_len = len(doc)
            score = 0.0
            for term in terms:
                tf = doc.count(term)
                if tf == 0:
                    continue
                # BM25 核心公式
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                score += self.idf[term] * numerator / denominator

            if score > 0:
                scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]