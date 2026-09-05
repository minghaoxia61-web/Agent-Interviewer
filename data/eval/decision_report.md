# 追问决策评估报告

- 评估对象：`app/core/rules.py::assess_answer` + LangGraph 面试状态机
- 样本集：30 条黄金回答（data/eval/golden_answers.json）

## 一、规则回归（黄金样本）

- 决策准确率：**100%**（30/30）

| 触发原因 | TP | FP | FN |
| --- | --- | --- | --- |
| answer_too_short | 8 | 0 | 0 |
| hedge_words | 7 | 0 | 0 |
| no_causal_chain | 9 | 0 | 0 |
| no_numbers | 10 | 0 | 0 |

## 二、全链路轨迹模拟（脚本化候选人）

| 轮次 | 阶段 | 决策 | 面试官输出 |
| --- | --- | --- | --- |
| 1 | project_probing | advance | 我看到简历里写着：「负责整体后端架构设计，采用微… |
| 2 | project_probing | follow_up | 能展开讲讲当时的具体实现吗？你本人负责哪一部分，… |
| 3 | project_probing | follow_up | 这个方案为什么这么选？当时对比过哪些替代方案，分… |
| 4 | project_probing | follow_up | 假设数据量和流量再放大 100 倍，这套方案最先… |
| 5 | project_probing | advance | 好，这一点先问到这。  我看到简历里写着：「通过… |
| 6 | project_probing | follow_up | 能展开讲讲当时的具体实现吗？你本人负责哪一部分，… |
| 7 | project_probing | follow_up | 这个方案为什么这么选？当时对比过哪些替代方案，分… |
| 8 | project_probing | follow_up | 假设数据量和流量再放大 100 倍，这套方案最先… |
| 9 | project_probing | advance | 好，这一点先问到这。  我看到简历里写着：「参与… |
| 10 | project_probing | follow_up | 能展开讲讲当时的具体实现吗？你本人负责哪一部分，… |
| 11 | project_probing | follow_up | 这个方案为什么这么选？当时对比过哪些替代方案，分… |
| 12 | project_probing | follow_up | 假设数据量和流量再放大 100 倍，这套方案最先… |
| 13 | tech_drill | advance_stage | 先从第一道基础题开始。[腾讯真题·消息队列] 消… |
| 14 | tech_drill | advance | [腾讯真题·消息队列] 如何保证消息的顺序性？分… |
| 15 | tech_drill | advance | [字节跳动真题·消息队列] 消息积压了上百万条怎… |
| 16 | tech_drill | advance | [字节跳动真题·Redis] Redis 为什么… |
| 17 | stress_test | advance_stage | 别紧张，这一轮考察的是极限场景下的判断力。压力测… |
| 18 | stress_test | advance | 压力测试环节。回到你之前提到的「就大概做了下，效… |
| 19 | end | None | … |

- 追问总数：9（预期 9 = 3 个疑点 × 3 层封顶）
- 阶段轨迹：project_probing → project_probing → project_probing → project_probing → project_probing → project_probing → project_probing → project_probing → project_probing → project_probing → project_probing → project_probing → tech_drill → tech_drill → tech_drill → tech_drill → stress_test → stress_test → end
- 自然结束轮次：19
- 行为契约：✅ 全部满足

## 结论

- ✅ 全部通过
