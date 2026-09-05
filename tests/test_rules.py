"""追问决策规则回归：黄金样本全量回归 + 关键行为单元断言。"""
import json
from pathlib import Path

import pytest

from app.core.rules import assess_answer, reasons_label

GOLDEN = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "eval" / "golden_answers.json")
    .read_text(encoding="utf-8"))


@pytest.mark.parametrize("item", GOLDEN, ids=[i["id"] for i in GOLDEN])
def test_golden_answers(item):
    """黄金样本回归：决策与触发原因必须与标注完全一致（CI 回归门）。"""
    solid, reasons = assess_answer(item["answer"])
    assert solid == item["expect_solid"], (item["id"], reasons)
    assert set(reasons) == set(item["expect_reasons"]), (item["id"], reasons)


def test_short_answer_reports_only_short_reason():
    solid, reasons = assess_answer("就大概做了下")
    assert solid is False
    assert reasons == ["answer_too_short"]


def test_solid_answer_passes_all_rules():
    answer = ("因为压测发现基线接口平均 RT 是 250ms，定位后发现 80% 耗时在重复查询，"
              "于是把热点数据放进 Redis 并设置 5 分钟 TTL，改造后压测 RT 降到 45ms")
    solid, reasons = assess_answer(answer)
    assert solid is True
    assert reasons == []


def test_reasons_label_maps_to_chinese():
    assert "回答过短" in reasons_label(["answer_too_short"])
    assert reasons_label([]) == "无"


def test_hedge_threshold_requires_two_distinct_words():
    # 单个模糊词不应触发 hedge_words
    solid, reasons = assess_answer(
        "因为当时只有大概 2 天时间，所以选择了最简单的方案，收益是按时上线了")
    assert "hedge_words" not in reasons
    assert solid is True
