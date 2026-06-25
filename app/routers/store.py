from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Store
from app.schemas.store import StoreCreate, StoreResp, StoreUpdate
from app.schemas.common import ApiResponse, PageResult, PageQuery

router = APIRouter(prefix="/api/stores", tags=["门店管理"])


@router.post("", response_model=ApiResponse[StoreResp])
def create_store(data: StoreCreate, db: Session = Depends(get_db)):
    existing = db.query(Store).filter(Store.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"门店名称 {data.name} 已存在")
    store = Store(**data.model_dump())
    db.add(store)
    db.commit()
    db.refresh(store)
    return ApiResponse(data=StoreResp.model_validate(store))


@router.get("", response_model=ApiResponse[PageResult[StoreResp]])
def list_stores(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Store)
    if keyword:
        query = query.filter(
            (Store.name.like(f"%{keyword}%")) | (Store.address.like(f"%{keyword}%"))
        )
    total = query.count()
    items = query.order_by(Store.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    data = PageResult(
        total=total,
        page=page,
        page_size=page_size,
        list=[StoreResp.model_validate(i) for i in items],
    )
    return ApiResponse(data=data)


@router.get("/all", response_model=ApiResponse[List[StoreResp]])
def list_all_stores(db: Session = Depends(get_db)):
    items = db.query(Store).order_by(Store.id.asc()).all()
    return ApiResponse(data=[StoreResp.model_validate(i) for i in items])


@router.get("/{store_id}", response_model=ApiResponse[StoreResp])
def get_store(store_id: int, db: Session = Depends(get_db)):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    return ApiResponse(data=StoreResp.model_validate(store))


@router.put("/{store_id}", response_model=ApiResponse[StoreResp])
def update_store(store_id: int, data: StoreUpdate, db: Session = Depends(get_db)):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(store, k, v)
    db.commit()
    db.refresh(store)
    return ApiResponse(data=StoreResp.model_validate(store))


@router.delete("/{store_id}", response_model=ApiResponse)
def delete_store(store_id: int, db: Session = Depends(get_db)):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="门店不存在")
    db.delete(store)
    db.commit()
    return ApiResponse(message="删除成功")
