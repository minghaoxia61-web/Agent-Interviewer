"""简历上传与解析路由。

上传接口只做同步的文本提取 + LLM 结构化解析（单次调用，响应快），
漏洞挖掘与体检诊断转入后台线程并行执行——避免网关（Cloudflare/魔搭等）
对长请求的超时截断。前端通过 GET /{session_id}/analysis 轮询结果。
"""
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.schemas.resume import Weakness
from app.core.security import ensure_owner, visitor_id
from app.services import mock_llm
from app.services.orchestrator import ORCHESTRATOR
from app.services.resume_parser import SUPPORTED_SUFFIXES, extract_text, parse_resume
from app.storage.session_store import STORE
from app.core.config import settings

router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.post("/upload", response_model=dict)
async def upload_resume(request: Request,
                        file: UploadFile = File(...),
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
    sess = STORE.create(target_position=target_position.strip(), resume=resume_dict,
                        weaknesses=[], analysis_status="processing",
                        owner=visitor_id(request))
    # 按会话归档原始简历
    kept = settings.uploads_dir / f"{sess.id}{suffix}"
    kept.write_bytes(content)

    # 漏洞挖掘 ∥ 体检诊断：后台并行执行，完成后回写会话
    def _dig() -> list:
        try:
            raw = llm.dig_weaknesses(resume_dict)[:3]
            return [Weakness(**w).model_dump() for w in raw]
        except Exception:  # noqa: BLE001 - LLM 失败自动降级确定性启发式
            return mock_llm.dig_weaknesses(resume_dict)[:3]

    def _diagnose() -> dict:
        return llm.diagnose_resume(resume_dict, target_position.strip())

    def _analyze() -> None:
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                f_dig, f_diag = pool.submit(_dig), pool.submit(_diagnose)
                weaknesses, diagnosis = f_dig.result(), f_diag.result()
            sess.weaknesses = weaknesses
            sess.diagnosis = diagnosis
            sess.analysis_status = "done"
        except Exception as e:  # noqa: BLE001
            sess.analysis_status = "failed"
            sess.analysis_error = str(e)[:200]
        STORE.save(sess)

    threading.Thread(target=_analyze, name=f"analyze-{sess.id}", daemon=True).start()

    return {
        "session_id": sess.id,
        "resume": resume_dict,
        "weaknesses": [],
        "diagnosis": None,
        "analysis_status": "processing",
        "target_position": sess.target_position,
        "parse_mode": mode,
        "llm_mode": "mock" if llm.mock else "real",
        "filename": file.filename,
    }


@router.get("/{session_id}/analysis")
def get_analysis(session_id: str, request: Request):
    """轮询简历分析结果（processing / done / failed）。"""
    sess = STORE.get(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="会话不存在，请先上传简历")
    ensure_owner(sess.owner, request)
    return {
        "session_id": sess.id,
        "analysis_status": sess.analysis_status,
        "analysis_error": sess.analysis_error,
        "weaknesses": sess.weaknesses if sess.analysis_status == "done" else [],
        "diagnosis": sess.diagnosis if sess.analysis_status == "done" else None,
        "target_position": sess.target_position,
    }


class JdMatchRequest(BaseModel):
    jd: str


@router.post("/{session_id}/jd-match")
def jd_match(session_id: str, body: JdMatchRequest, request: Request):
    sess = STORE.get(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="会话不存在，请先上传简历")
    ensure_owner(sess.owner, request)
    if not body.jd.strip():
        raise HTTPException(status_code=422, detail="JD 文本不能为空")
    return ORCHESTRATOR.llm.jd_match(sess.resume, body.jd, sess.target_position)
