from sqlalchemy import Column, Integer, String, ForeignKey, Float
from sqlalchemy.orm import relationship
from database import Base, engine

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key = True, index = True)
    email = Column(String, unique = True, nullable = False)
    password = Column(String, nullable = False)
    
    
class Group(Base):
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key = True, index = True)
    name = Column(String, nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"))

# join table (links users to groups and carries role)
class Membership(Base):
    __tablename__ = "memberships"
    
    id = Column(Integer, primary_key = True, index = True)
    user_id = Column(Integer, ForeignKey("users.id"))
    group_id = Column(Integer, ForeignKey("groups.id"))
    role = Column(String, default = "member")

class Expense(Base):
    __tablename__ = "expenses"
    
    id = Column(Integer, primary_key= True, index = True)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable = False)
    paid_by = Column(Integer, ForeignKey("users.id"))
    group_id = Column(Integer, ForeignKey("groups.id"))
    
class ExpenseSplit(Base):
    __tablename__ = "expense_split"
    
    id = Column(Integer, primary_key=True, index = True)
    expense_id = Column(Integer, ForeignKey("expenses.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float, nullable=False)

Base.metadata.create_all(bind=engine)