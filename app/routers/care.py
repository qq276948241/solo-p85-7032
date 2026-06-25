import os
import uuid
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.models import CareRecord, CarePhoto, Booking, Pet, Employee, BookingStatus
from app.schemas.care import (
    CareRecordCreate, CareRecordResp, CareRecordUpdate,
    CareRecordListResp, CarePhotoResp, CarePhotoBase,
)
from app.schemas.common import ApiResponse, PageResult

router = APIRouter(prefix="/api/care-records", tags=["日常照护"])


def _ensure_upload_dir():
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "care"), exist_ok=True)


@router.post("/upload-photo", response_model=ApiResponse[str])
async def upload_care_photo(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持上传图片文件")
    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"文件大小超过限制 ({settings.MAX_UPLOAD_SIZE//1024//1024}MB)")
    _ensure_upload_dir()
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(settings.UPLOAD_DIR, "care", filename)
    with open(filepath, "wb") as f:
        f.write(contents)
    url = f"/uploads/care/{filename}"
    return ApiResponse(data=url)


@router.post("", response_model=ApiResponse[CareRecordResp])
def create_care_record(data: CareRecordCreate, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == data.booking_id).first()
    if not booking:
        raise HTTPException(status_code=400, detail="预约不存在")
    if booking.status not in [BookingStatus.CHECKED_IN, BookingStatus.CONFIRMED]:
        raise HTTPException(status_code=400, detail="仅可对已入住/已确认的预约添加照护记录")
    pet = db.query(Pet).filter(Pet.id == data.pet_id).first()
    if not pet:
        raise HTTPException(status_code=400, detail="宠物不存在")
    employee = db.query(Employee).filter(Employee.id == data.caretaker_id).first()
    if not employee:
        raise HTTPException(status_code=400, detail="护理员不存在")

    record_data = data.model_dump(exclude={"photos"})
    if not record_data.get("record_date"):
        record_data["record_date"] = date.today()
    record = CareRecord(**record_data)
    db.add(record)
    db.flush()

    for p in data.photos:
        photo = CarePhoto(care_record_id=record.id, **p.model_dump())
        db.add(photo)

    db.commit()
    db.refresh(record)
    return ApiResponse(data=CareRecordResp.model_validate(record))


@router.get("", response_model=ApiResponse[PageResult[CareRecordListResp]])
def list_care_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    booking_id: Optional[int] = None,
    pet_id: Optional[int] = None,
    caretaker_id: Optional[int] = None,
    record_date: Optional[date] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    abnormal_only: Optional[bool] = False,
    db: Session = Depends(get_db),
):
    query = db.query(CareRecord)
    if booking_id:
        query = query.filter(CareRecord.booking_id == booking_id)
    if pet_id:
        query = query.filter(CareRecord.pet_id == pet_id)
    if caretaker_id:
        query = query.filter(CareRecord.caretaker_id == caretaker_id)
    if record_date:
        query = query.filter(CareRecord.record_date == record_date)
    if start_date:
        query = query.filter(CareRecord.record_date >= start_date)
    if end_date:
        query = query.filter(CareRecord.record_date <= end_date)
    if abnormal_only:
        query = query.filter(CareRecord.abnormal_flag == True)
    total = query.count()
    items = (
        query.order_by(CareRecord.record_date.desc(), CareRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    data = PageResult(
        total=total,
        page=page,
        page_size=page_size,
        list=[CareRecordListResp.model_validate(i) for i in items],
    )
    return ApiResponse(data=data)


@router.get("/{record_id}", response_model=ApiResponse[CareRecordResp])
def get_care_record(record_id: int, db: Session = Depends(get_db)):
    record = db.query(CareRecord).filter(CareRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="照护记录不存在")
    return ApiResponse(data=CareRecordResp.model_validate(record))


@router.put("/{record_id}", response_model=ApiResponse[CareRecordResp])
def update_care_record(record_id: int, data: CareRecordUpdate, db: Session = Depends(get_db)):
    record = db.query(CareRecord).filter(CareRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="照护记录不存在")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(record, k, v)
    db.commit()
    db.refresh(record)
    return ApiResponse(data=CareRecordResp.model_validate(record))


@router.post("/{record_id}/photos", response_model=ApiResponse[List[CarePhotoResp]])
def add_photos(record_id: int, photos: List[CarePhotoBase], db: Session = Depends(get_db)):
    record = db.query(CareRecord).filter(CareRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="照护记录不存在")
    created = []
    for p in photos:
        photo = CarePhoto(care_record_id=record_id, **p.model_dump())
        db.add(photo)
        db.flush()
        db.refresh(photo)
        created.append(CarePhotoResp.model_validate(photo))
    db.commit()
    return ApiResponse(data=created)


@router.delete("/photos/{photo_id}", response_model=ApiResponse)
def delete_photo(photo_id: int, db: Session = Depends(get_db)):
    photo = db.query(CarePhoto).filter(CarePhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="照片不存在")
    db.delete(photo)
    db.commit()
    return ApiResponse(message="删除成功")


@router.delete("/{record_id}", response_model=ApiResponse)
def delete_care_record(record_id: int, db: Session = Depends(get_db)):
    record = db.query(CareRecord).filter(CareRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="照护记录不存在")
    db.delete(record)
    db.commit()
    return ApiResponse(message="删除成功")
