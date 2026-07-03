from pydantic import BaseModel, EmailStr
from typing import Optional, List

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    email: EmailStr
    class Config:
        from_attributes = True
        
class GroupCreate(BaseModel):
    name: str

class GroupOut(GroupCreate):
    id: int
    creator_id: int
    class Config:
        from_attributes = True
    
class SplitInput(BaseModel):
    user_id: int
    value: Optional[float] = None
    
class ExpenseCreate(BaseModel):
    description: str
    amount: float
    split_type: str
    splits: List[SplitInput]
    
class SplitOut(BaseModel):
    user_id: int
    amount: float
    class Config:
        from_attributes = True

class ExpenseOut(BaseModel):
    id: int
    description: str
    amount: float
    paid_by: int
    group_id: int
    splits: List[SplitOut]
    class Config:
        from_attributes = True

    