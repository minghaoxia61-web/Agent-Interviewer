# RAG 检索评测报告

- 查询集：40 条标注查询（data/eval/rag_queries.json）
- 指标：recall@5（前 5 命中任一标注题）、MRR（标注题平均倒数排名）

| 引擎 | recall@5 | MRR | 平均耗时(ms) | 备注 |
| --- | --- | --- | --- | --- |
| ngram | 1.0 | 1.0 | 1.59 |  |
| bm25 | 1.0 | 1.0 | 0.39 |  |
| chroma | - | - | - | 初始化失败回落 bm25 |

- 当前配置（RETRIEVER_MODE=auto）实际启用：**bm25**

> chroma 默认内置 embedding 模型对中文偏弱且首次使用需联网下载；生产建议配置 OpenAI 兼容 embedding 服务后重跑本脚本对比。