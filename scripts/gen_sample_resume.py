"""生成示例简历 PDF（仅开发/演示用，不属于运行时依赖）。

用法：./.venv/Scripts/python.exe scripts/gen_sample_resume.py
依赖：pip install reportlab（使用内置 CID 中文字体 STSong-Light，无需字体文件）
"""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).resolve().parent.parent / "data" / "samples" / "sample_resume.pdf"

SECTIONS = [
    ("h1", "张三"),
    ("p", "求职意向：后端开发工程师（Python/Go）"),
    ("h2", "专业技能"),
    ("li", "熟悉 Python、Go，了解 Java"),
    ("li", "熟悉 MySQL、Redis，了解消息队列 Kafka"),
    ("li", "熟悉 Docker、Linux，了解 Kubernetes"),
    ("li", "熟悉微服务、分布式、高并发架构"),
    ("h2", "项目经历"),
    ("h3", "校园二手交易平台（2024.03 - 2024.09）｜后端负责人（2 人团队）"),
    ("li", "负责整体后端架构设计，采用微服务架构，提升了系统的可扩展性"),
    ("li", "通过引入 Redis 缓存，将接口平均响应时间降低了 80%"),
    ("li", "使用 Celery 处理异步任务，支撑了日均 10w+ 消息"),
    ("li", "参与数据库优化，查询性能提升 300%"),
    ("h3", "分布式爬虫调度平台（2023.09 - 2024.02）"),
    ("li", "基于 Scrapy-Redis 实现分布式爬虫，效率提升数倍"),
    ("li", "设计了失败重试与限流机制，保证爬虫稳定运行"),
    ("li", "大概支撑了千万级数据的采集"),
    ("h2", "实习经历"),
    ("h3", "某互联网公司 后端开发实习生（2024.06 - 2024.12）"),
    ("li", "参与订单中心微服务的开发与维护"),
    ("li", "协助完成了慢查询治理专项"),
    ("h2", "教育经历"),
    ("li", "XX大学 计算机科学与技术 本科 2021.09 - 2025.06"),
]

STYLES = {
    "h1": ParagraphStyle("h1", fontName="STSong-Light", fontSize=20, leading=26, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName="STSong-Light", fontSize=14, leading=20,
                         spaceBefore=10, spaceAfter=4),
    "h3": ParagraphStyle("h3", fontName="STSong-Light", fontSize=12, leading=18,
                         spaceBefore=6, spaceAfter=2),
    "p": ParagraphStyle("p", fontName="STSong-Light", fontSize=11, leading=17),
    "li": ParagraphStyle("li", fontName="STSong-Light", fontSize=11, leading=17,
                         leftIndent=6 * mm, bulletIndent=1 * mm),
}


def main() -> None:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=A4,
                            topMargin=18 * mm, bottomMargin=18 * mm)
    story = []
    for kind, text in SECTIONS:
        story.append(Paragraph(text, STYLES[kind], bulletText="•" if kind == "li" else None))
        if kind in ("p", "li"):
            story.append(Spacer(1, 2))
    doc.build(story)
    print(f"生成完成: {OUT}")


if __name__ == "__main__":
    main()
