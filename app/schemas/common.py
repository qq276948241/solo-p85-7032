from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field
from datetime import datetime

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = Field(default=0, description="状态码，0表示成功")
    message: str = Field(default="success", description="响应消息")
    data: Optional[T] = Field(default=None, description="响应数据")


class PageResult(BaseModel, Generic[T]):
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页条数")
    list: List[T] = Field(description="数据列表")


class PageQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=100, description="每页条数")
    keyword: Optional[str] = Field(default=None, description="搜索关键词")


class IdNameResp(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class TimestampMixin(BaseModel):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
