from pydantic import BaseModel, EmailStr, Field
from typing import List

# The API takes and returns INTEGER CENTS. The frontend converts to dollars for display.

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    email: EmailStr
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ---------- groups ----------

class GroupCreate(BaseModel):
    name: str

class GroupOut(GroupCreate):
    id: int
    creator_id: int
    class Config:
        from_attributes = True

class MemberAdd(BaseModel):
    email: EmailStr

class MemberOut(BaseModel):
    user_id: int
    email: EmailStr
    role: str

class GroupDetail(GroupOut):
    members: List[MemberOut]

# ---------- expenses (equal split only, for now) ----------

class ExpenseCreate(BaseModel):
    description: str
    amount_cents: int = Field(gt=0)
    # who shares this expense; the payer is the current user
    participant_ids: List[int] = Field(min_length=1)

class SplitOut(BaseModel):
    user_id: int
    amount_cents: int
    class Config:
        from_attributes = True

class ExpenseOut(BaseModel):
    id: int
    description: str
    amount_cents: int
    paid_by: int
    group_id: int
    splits: List[SplitOut]
    class Config:
        from_attributes = True

# ---------- balances & settlement ----------

class BalanceOut(BaseModel):
    user_id: int
    email: EmailStr
    balance_cents: int  # positive = is owed money, negative = owes money

class TransferOut(BaseModel):
    from_user_id: int  # pays
    to_user_id: int    # receives
    amount_cents: int