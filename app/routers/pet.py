from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.models import Pet, Owner, Vaccine
from app.schemas.pet import (
    PetCreate, PetResp, PetUpdate, PetSimpleResp,
    VaccineCreate, VaccineResp, VaccineUpdate,
)
from app.schemas.common import ApiResponse, PageResult

router = APIRouter(prefix="/api/pets", tags=["宠物档案"])


@router.post("", response_model=ApiResponse[PetResp])
def create_pet(data: PetCreate, db: Session = Depends(get_db)):
    owner = db.query(Owner).filter(Owner.id == data.owner_id).first()
    if not owner:
        raise HTTPException(status_code=400, detail="主人不存在")
    pet = Pet(**data.model_dump())
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return ApiResponse(data=PetResp.model_validate(pet))


@router.get("", response_model=ApiResponse[PageResult[PetResp]])
def list_pets(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: Optional[str] = None,
    owner_id: Optional[int] = None,
    species: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Pet)
    if keyword:
        query = query.join(Owner).filter(
            or_(
                Pet.name.like(f"%{keyword}%"),
                Pet.breed.like(f"%{keyword}%"),
                Pet.chip_number.like(f"%{keyword}%"),
                Owner.name.like(f"%{keyword}%"),
                Owner.phone.like(f"%{keyword}%"),
            )
        )
    if owner_id:
        query = query.filter(Pet.owner_id == owner_id)
    if species:
        query = query.filter(Pet.species == species)
    if is_active is not None:
        query = query.filter(Pet.is_active == is_active)
    total = query.count()
    items = (
        query.order_by(Pet.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    data = PageResult(
        total=total,
        page=page,
        page_size=page_size,
        list=[PetResp.model_validate(i) for i in items],
    )
    return ApiResponse(data=data)


@router.get("/all", response_model=ApiResponse[List[PetSimpleResp]])
def list_all_pets(
    owner_id: Optional[int] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Pet).filter(Pet.is_active == True)
    if owner_id:
        query = query.filter(Pet.owner_id == owner_id)
    if keyword:
        query = query.filter(
            or_(
                Pet.name.like(f"%{keyword}%"),
                Pet.breed.like(f"%{keyword}%"),
            )
        )
    items = query.order_by(Pet.name.asc()).all()
    return ApiResponse(data=[PetSimpleResp.model_validate(i) for i in items])


@router.get("/{pet_id}", response_model=ApiResponse[PetResp])
def get_pet(pet_id: int, db: Session = Depends(get_db)):
    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")
    return ApiResponse(data=PetResp.model_validate(pet))


@router.put("/{pet_id}", response_model=ApiResponse[PetResp])
def update_pet(pet_id: int, data: PetUpdate, db: Session = Depends(get_db)):
    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")
    update_data = data.model_dump(exclude_unset=True)
    if "owner_id" in update_data:
        owner = db.query(Owner).filter(Owner.id == update_data["owner_id"]).first()
        if not owner:
            raise HTTPException(status_code=400, detail="主人不存在")
    for k, v in update_data.items():
        setattr(pet, k, v)
    db.commit()
    db.refresh(pet)
    return ApiResponse(data=PetResp.model_validate(pet))


@router.delete("/{pet_id}", response_model=ApiResponse)
def delete_pet(pet_id: int, db: Session = Depends(get_db)):
    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")
    pet.is_active = False
    db.commit()
    return ApiResponse(message="删除成功")


@router.post("/{pet_id}/vaccines", response_model=ApiResponse[VaccineResp])
def add_vaccine(pet_id: int, data: VaccineCreate, db: Session = Depends(get_db)):
    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")
    v_data = data.model_dump()
    v_data.pop("pet_id", None)
    vaccine = Vaccine(pet_id=pet_id, **v_data)
    db.add(vaccine)
    db.commit()
    db.refresh(vaccine)
    return ApiResponse(data=VaccineResp.model_validate(vaccine))


@router.get("/{pet_id}/vaccines", response_model=ApiResponse[List[VaccineResp]])
def list_vaccines(pet_id: int, db: Session = Depends(get_db)):
    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")
    vaccines = (
        db.query(Vaccine)
        .filter(Vaccine.pet_id == pet_id)
        .order_by(Vaccine.vaccinated_date.desc())
        .all()
    )
    return ApiResponse(data=[VaccineResp.model_validate(v) for v in vaccines])


@router.put("/vaccines/{vaccine_id}", response_model=ApiResponse[VaccineResp])
def update_vaccine(vaccine_id: int, data: VaccineUpdate, db: Session = Depends(get_db)):
    vaccine = db.query(Vaccine).filter(Vaccine.id == vaccine_id).first()
    if not vaccine:
        raise HTTPException(status_code=404, detail="疫苗记录不存在")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(vaccine, k, v)
    db.commit()
    db.refresh(vaccine)
    return ApiResponse(data=VaccineResp.model_validate(vaccine))


@router.delete("/vaccines/{vaccine_id}", response_model=ApiResponse)
def delete_vaccine(vaccine_id: int, db: Session = Depends(get_db)):
    vaccine = db.query(Vaccine).filter(Vaccine.id == vaccine_id).first()
    if not vaccine:
        raise HTTPException(status_code=404, detail="疫苗记录不存在")
    db.delete(vaccine)
    db.commit()
    return ApiResponse(message="删除成功")
