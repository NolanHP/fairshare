from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import User
from schemas import UserCreate, UserOut, Token
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
def login(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user is None:
        raise HTTPException(status_code = 401, detail = "Invalid email or password")
    auth = verify_password(user.password, db_user.password)
    if auth is False:
        raise HTTPException(status_code = 401, detail= "Invalid email or password")
    token = create_access_token(db_user.id)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/me", response_model = UserOut)
def read_me(current_user = Depends(get_current_user)):
    return current_user
    
