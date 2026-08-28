from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import User, Group, Membership
from schemas import UserCreate, UserOut, Token, GroupCreate, GroupOut
from auth import hash_password, verify_password, create_access_token, get_current_user

app = FastAPI(title="Expense Splitter API")

@app.post("/register", response_model = UserOut)
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail = "Email already registered")
    if len(user.password)>72:
        raise HTTPException(status_code=400, detail = "Password exceeds 72 characters")
    hashed = hash_password(user.password)
    new_user = User(email = user.email, password = hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/login", response_model = Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == form_data.username).first()
    if db_user is None:
        raise HTTPException(status_code = 401, detail = "Invalid email or password")
    auth = verify_password(form_data.password, db_user.password)
    if auth is False:
        raise HTTPException(status_code = 401, detail= "Invalid email or password")
    token = create_access_token(db_user.id)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/me", response_model = UserOut)
def read_me(current_user = Depends(get_current_user)):
    return current_user
    
@app.post("/groups", response_model=GroupOut)
def create_group(group: GroupCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    new_group = Group(name=group.name, creator_id=current_user.id)
    db.add(new_group)
    db.commit()
    db.refresh(new_group)

    membership = Membership(user_id=current_user.id, group_id=new_group.id, role="admin")
    db.add(membership)
    db.commit()

    return new_group

@app.get("/groups", response_model=List[GroupOut])
def get_groups(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    memberships = db.query(Membership).filter(Membership.user_id == current_user.id).all()
    group_ids = [m.group_id for m in memberships]
    groups = db.query(Group).filter(Group.id.in_(group_ids)).all()
    return groups