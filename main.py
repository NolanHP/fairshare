from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import User, Group, Membership, Expense, ExpenseSplit
from schemas import (
    UserCreate, UserOut, Token,
    GroupCreate, GroupOut, GroupDetail, MemberAdd, MemberOut,
    ExpenseCreate, ExpenseOut, BalanceOut, TransferOut,
)
from auth import hash_password, verify_password, create_access_token, get_current_user
from logic import split_equal, compute_balances, settle

app = FastAPI(title="Expense Splitter API")


# ---------- helpers ----------

def require_membership(group_id: int, user: User, db: Session) -> Group:
    """Return the group if it exists AND the user belongs to it; otherwise raise.

    Every group-scoped endpoint calls this first, so access control lives in one place.
    404 for both "no such group" and "not a member" so outsiders can't probe which
    group ids exist.
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    is_member = db.query(Membership).filter(
        Membership.group_id == group_id, Membership.user_id == user.id
    ).first()
    if is_member is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


def group_member_ids(group_id: int, db: Session) -> List[int]:
    return [m.user_id for m in db.query(Membership).filter(Membership.group_id == group_id).all()]


# ---------- auth ----------

@app.post("/register", response_model=UserOut)
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    if len(user.password) > 72:
        raise HTTPException(status_code=400, detail="Password exceeds 72 characters")
    hashed = hash_password(user.password)
    new_user = User(email=user.email, password=hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == form_data.username).first()
    if db_user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    auth = verify_password(form_data.password, db_user.password)
    if auth is False:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(db_user.id)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/me", response_model=UserOut)
def read_me(current_user=Depends(get_current_user)):
    return current_user


# ---------- groups ----------

@app.post("/groups", response_model=GroupOut)
def create_group(group: GroupCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    new_group = Group(name=group.name, creator_id=current_user.id)
    db.add(new_group)
    # flush() sends the INSERT so new_group.id exists, but doesn't commit yet.
    # The group and the creator's membership then commit together (one transaction):
    # either both rows are saved or neither is.
    db.flush()
    db.add(Membership(user_id=current_user.id, group_id=new_group.id, role="admin"))
    db.commit()
    db.refresh(new_group)
    return new_group

@app.get("/groups", response_model=List[GroupOut])
def get_groups(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    memberships = db.query(Membership).filter(Membership.user_id == current_user.id).all()
    group_ids = [m.group_id for m in memberships]
    groups = db.query(Group).filter(Group.id.in_(group_ids)).all()
    return groups

@app.get("/groups/{group_id}", response_model=GroupDetail)
def get_group(group_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    group = require_membership(group_id, current_user, db)
    members = [
        MemberOut(user_id=m.user_id, email=m.user.email, role=m.role)
        for m in group.memberships
    ]
    return GroupDetail(id=group.id, name=group.name, creator_id=group.creator_id, members=members)

@app.post("/groups/{group_id}/members", response_model=MemberOut)
def add_member(group_id: int, body: MemberAdd, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Any existing member can add another registered user by email."""
    require_membership(group_id, current_user, db)
    user = db.query(User).filter(User.email == body.email).first()
    if user is None:
        raise HTTPException(status_code=404, detail="No user with that email")
    already = db.query(Membership).filter(
        Membership.group_id == group_id, Membership.user_id == user.id
    ).first()
    if already:
        raise HTTPException(status_code=409, detail="User is already in this group")
    membership = Membership(user_id=user.id, group_id=group_id, role="member")
    db.add(membership)
    db.commit()
    return MemberOut(user_id=user.id, email=user.email, role=membership.role)


# ---------- expenses ----------

@app.post("/groups/{group_id}/expenses", response_model=ExpenseOut)
def create_expense(group_id: int, body: ExpenseCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """The current user paid body.amount_cents; split it equally among participant_ids."""
    require_membership(group_id, current_user, db)

    # Validate BEFORE writing anything.
    participants = body.participant_ids
    if len(set(participants)) != len(participants):
        raise HTTPException(status_code=400, detail="Duplicate participant ids")
    members = set(group_member_ids(group_id, db))
    outsiders = [uid for uid in participants if uid not in members]
    if outsiders:
        raise HTTPException(status_code=400, detail=f"Not group members: {outsiders}")

    shares = split_equal(body.amount_cents, participants, payer_id=current_user.id)

    # Expense + all its splits are saved in ONE commit: either everything is
    # written or nothing is, so the db never has an expense with missing splits.
    expense = Expense(
        description=body.description,
        amount_cents=body.amount_cents,
        paid_by=current_user.id,
        group_id=group_id,
    )
    for uid, cents in shares.items():
        expense.splits.append(ExpenseSplit(user_id=uid, amount_cents=cents))
    db.add(expense)  # cascade adds the splits too
    db.commit()
    db.refresh(expense)
    return expense

@app.get("/groups/{group_id}/expenses", response_model=List[ExpenseOut])
def list_expenses(group_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    require_membership(group_id, current_user, db)
    return (
        db.query(Expense)
        .filter(Expense.group_id == group_id)
        .order_by(Expense.id.desc())  # newest first
        .all()
    )


# ---------- balances & settlement ----------

def _group_balances(group_id: int, db: Session):
    member_ids = group_member_ids(group_id, db)
    expenses = db.query(Expense).filter(Expense.group_id == group_id).all()
    return compute_balances(member_ids, expenses)

@app.get("/groups/{group_id}/balances", response_model=List[BalanceOut])
def get_balances(group_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Positive = the group owes them; negative = they owe the group."""
    require_membership(group_id, current_user, db)
    balances = _group_balances(group_id, db)
    users = db.query(User).filter(User.id.in_(balances.keys())).all()
    email = {u.id: u.email for u in users}
    return [
        BalanceOut(user_id=uid, email=email[uid], balance_cents=amt)
        for uid, amt in sorted(balances.items())
    ]

@app.get("/groups/{group_id}/settlement", response_model=List[TransferOut])
def get_settlement(group_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Suggested payments that would bring everyone to zero (greedy, see logic.settle)."""
    require_membership(group_id, current_user, db)
    transfers = settle(_group_balances(group_id, db))
    return [TransferOut(from_user_id=f, to_user_id=t, amount_cents=a) for f, t, a in transfers]


# ---------- frontend ----------
# Serve the single-page frontend from the same server. Same origin as the API,
# so the browser doesn't need any CORS configuration.

STATIC_DIR = Path(__file__).parent / "static"

@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(STATIC_DIR / "index.html")
