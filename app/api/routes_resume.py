"""简历上传与解析路由。"""
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.schemas.resume import Weakness
from app.services import mock_llm
from app.services.orchestrator import ORCHESTRATOR
from app.services.resume_parser import SUPPORTED_SUFFIXES, extract_text, parse_resume
from app.storage.session_store import STORE
from app.core.config import settings

router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.post("/upload", response_model=dict)
async def upload_resume(file: UploadFile = File(...),
                        target_position: str = Form("后端开发工程师")):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=400,
                            detail=f"不支持的文件类型 {suffix}，请上传 PDF / TXT / MD 简历")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件超过 10MB 限制")
    if not content:
        raise HTTPException(status_code=400, detail="文件内容为空")

    llm = ORCHESTRATOR.llm
    tmp_path = settings.uploads_dir / f"tmp_upload{suffix}"
    tmp_path.write_bytes(content)
    try:
        text = extract_text(tmp_path)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"简历文本提取失败：{e}") from e

    try:
        parsed, mode = parse_resume(llm, text, target_position.strip())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    resume_dict = parsed.model_dump()

    # 漏洞挖掘：LLM 失败时自动降级为确定性启发式
    try:
        raw_weaknesses = llm.dig_weaknesses(resume_dict)[:3]
        weaknesses = [Weakness(**w).model_dump() for w in raw_weaknesses]
        dig_mode = "llm" if not llm.mock else "heuristic"
    except Exception:  # noqa: BLE001
        weaknesses = mock_llm.dig_weaknesses(resume_dict)[:3]
        dig_mode = "heuristic"

    # 简历体检诊断（LLM 失败自动回落启发式，见 llm.diagnose_resume）
    diagnosis = llm.diagnose_resume(resume_dict, target_position.strip())

    sess = STORE.create(target_position=target_position.strip(),
                        resume=resume_dict, weaknesses=weaknesses,
                        diagnosis=diagnosis)
    # 按会话归档原始简历
    kept = settings.uploads_dir / f"{sess.id}{suffix}"
    kept.write_bytes(content)

    return {
        "session_id": sess.id,
        "resume": resume_dict,
        "weaknesses": weaknesses,
        "diagnosis": diagnosis,
        "target_position": sess.target_position,
        "parse_mode": mode,
        "dig_mode": dig_mode,
        "llm_mode": "mock" if llm.mock else "real",
        "filename": file.filename,
    }


class JdMatchRequest(BaseModel):
    jd: str


@router.post("/{session_id}/jd-match")
def jd_match(session_id: str, body: JdMatchRequest):
    sess = STORE.get(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="会话不存在，请先上传简历")
    if not body.jd.strip():
        raise HTTPException(status_code=422, detail="JD 文本不能为空")
    return ORCHESTRATOR.llm.jd_match(sess.resume, body.jd, sess.target_position)
