from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.models import Owner
from app.schemas.owner import OwnerCreate, OwnerResp, OwnerUpdate, OwnerSimpleResp
from app.schemas.common import ApiResponse, PageResult

router = APIRouter(prefix="/api/owners", tags=["主人管理"])


@router.post("", response_model=ApiResponse[OwnerResp])
def create_owner(data: OwnerCreate, db: Session = Depends(get_db)):
    owner = Owner(**data.model_dump())
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return ApiResponse(data=OwnerResp.model_validate(owner))


@router.get("", response_model=ApiResponse[PageResult[OwnerResp]])
def list_owners(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Owner)
    if keyword:
        query = query.filter(
            or_(
                Owner.name.like(f"%{keyword}%"),
                Owner.phone.like(f"%{keyword}%"),
                Owner.wechat.like(f"%{keyword}%"),
            )
        )
    total = query.count()
    items = query.order_by(Owner.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    data = PageResult(
        total=total,
        page=page,
        page_size=page_size,
        list=[OwnerResp.model_validate(i) for i in items],
    )
    return ApiResponse(data=data)


@router.get("/all", response_model=ApiResponse[List[OwnerSimpleResp]])
def list_all_owners(keyword: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Owner)
    if keyword:
        query = query.filter(
            or_(
                Owner.name.like(f"%{keyword}%"),
                Owner.phone.like(f"%{keyword}%"),
            )
        )
    items = query.order_by(Owner.id.asc()).all()
    return ApiResponse(data=[OwnerSimpleResp.model_validate(i) for i in items])


@router.get("/{owner_id}", response_model=ApiResponse[OwnerResp])
def get_owner(owner_id: int, db: Session = Depends(get_db)):
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="主人不存在")
    return ApiResponse(data=OwnerResp.model_validate(owner))


@router.put("/{owner_id}", response_model=ApiResponse[OwnerResp])
def update_owner(owner_id: int, data: OwnerUpdate, db: Session = Depends(get_db)):
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="主人不存在")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(owner, k, v)
    db.commit()
    db.refresh(owner)
    return ApiResponse(data=OwnerResp.model_validate(owner))


@router.delete("/{owner_id}", response_model=ApiResponse)
def delete_owner(owner_id: int, db: Session = Depends(get_db)):
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="主人不存在")
    if owner.pets:
        raise HTTPException(status_code=400, detail="该主人下还有宠物档案，无法删除")
    db.delete(owner)
    db.commit()
    return ApiResponse(message="删除成功")
