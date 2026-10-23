from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base, engine

# All money is stored as INTEGER CENTS ($10.00 -> 1000).
# Integers are exact, so balances sum correctly and "== 0" reliably means settled.
# Floats can't represent values like 0.1 exactly in binary, so errors pile up.

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"))

    memberships = relationship("Membership", back_populates="group")


# join table (links users to groups and carries role)
class Membership(Base):
    __tablename__ = "memberships"
    # A user can only be in a given group once. Enforced by the database itself,
    # so a duplicate can't sneak in even if an endpoint forgets to check.
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uq_user_group"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    role = Column(String, default="member")

    user = relationship("User")
    group = relationship("Group", back_populates="memberships")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    paid_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)

    # Lets you do expense.splits -> list of ExpenseSplit rows.
    # This is what ExpenseOut.splits reads via from_attributes.
    splits = relationship("ExpenseSplit", back_populates="expense", cascade="all, delete-orphan")


class ExpenseSplit(Base):
    __tablename__ = "expense_split"

    id = Column(Integer, primary_key=True, index=True)
    expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)  # what this user owes for the expense

    expense = relationship("Expense", back_populates="splits")


Base.metadata.create_all(bind=engine)
