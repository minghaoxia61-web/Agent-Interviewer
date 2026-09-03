"""求职投递看板 CRUD API。"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.storage.application_store import APPLICATIONS, STATUSES

router = APIRouter(prefix="/api/applications", tags=["applications"])


class ApplicationIn(BaseModel):
    company: str
    position: str
    status: str = "wishlist"
    salary: str = ""
    link: str = ""
    notes: str = ""


class ApplicationPatch(BaseModel):
    company: Optional[str] = None
    position: Optional[str] = None
    status: Optional[str] = None
    salary: Optional[str] = None
    link: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
def list_applications():
    items = APPLICATIONS.list()
    return {
        "statuses": STATUSES,
        "total": len(items),
        "items": items,
    }


@router.post("")
def create_application(body: ApplicationIn):
    if not body.company.strip() or not body.position.strip():
        raise HTTPException(status_code=422, detail="公司和岗位不能为空")
    if body.status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"非法状态，可选：{list(STATUSES)}")
    return APPLICATIONS.create(**body.model_dump())


@router.put("/{app_id}")
def update_application(app_id: str, body: ApplicationPatch):
    item = APPLICATIONS.update(app_id, body.model_dump(exclude_none=True))
    if item is None:
        raise HTTPException(status_code=404, detail="投递记录不存在")
    return item


@router.delete("/{app_id}")
def delete_application(app_id: str):
    if not APPLICATIONS.delete(app_id):
        raise HTTPException(status_code=404, detail="投递记录不存在")
    return {"deleted": True}
