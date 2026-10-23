# FairShare

A group expense splitter. Users create groups, log shared expenses, and see who owes whom, along with a suggested set of payments to settle up.

**Stack:** FastAPI · SQLAlchemy · SQLite · JWT auth (python-jose + bcrypt) · plain HTML/JS frontend · pytest

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

- App: http://localhost:8000
- API docs: http://localhost:8000/docs

Set `FAIRSHARE_SECRET_KEY` to sign tokens with your own key (a dev-only default is used otherwise).

## Tests

```bash
pytest
```

- `tests/test_logic.py` covers the money math: splitting, balances, settlement.
- `tests/test_api.py` runs the full flow through the API against an in-memory database.

## API

| Method | Path | What it does |
|---|---|---|
| POST | `/register` | Create an account |
| POST | `/login` | Get a JWT (OAuth2 password form) |
| GET | `/me` | Current user |
| POST / GET | `/groups` | Create a group / list my groups |
| GET | `/groups/{id}` | Group with its members |
| POST | `/groups/{id}/members` | Add a registered user by email |
| POST / GET | `/groups/{id}/expenses` | Add an expense I paid (equal split) / list expenses |
| GET | `/groups/{id}/balances` | Net balance per member |
| GET | `/groups/{id}/settlement` | Suggested payments to settle everyone |

## Design decisions

**Money is stored as integer cents.** Floats are binary, and values like 0.1 can't be represented exactly, so errors accumulate and a balance that should be 0 ends up as something like 1e-16. Integers are exact. The API takes and returns cents, and the frontend converts to dollars for display only.

**Remainder cents.** $10.00 split 3 ways is `divmod(1000, 3) = (333, 1)`: everyone owes 333 and 1 cent is left over. The payer absorbs it. The rule is deterministic, so the same input always produces the same split. Splits are checked to always sum to the total.

**Balances.** balance = total paid − total owed. Positive means the group owes you, negative means you owe. Every cent paid is owed by someone, so a group's balances always sum to exactly 0.

**Settlement is greedy.** The person who owes the most repeatedly pays the person owed the most, for `min(debt, credit)`. Each step settles at least one person, so there are at most n − 1 payments. The run time is O(n log n) using heaps. Finding the true minimum number of payments is NP-hard, so greedy is the practical choice.

**Access control in one place.** Every group endpoint calls `require_membership()`. Non-members get a 404 rather than a 403, so outsiders can't discover which group IDs exist.

**Atomic writes.** An expense and all of its splits are saved in one commit. The same goes for a new group and its creator's membership. Either everything is written or nothing is.

**Database constraints.** A `UniqueConstraint` on (user, group) stops a user from being added to the same group twice, even if an endpoint forgets to check.

**Frontend.** A single page served by FastAPI from the same origin, so no CORS setup is needed. The JWT is kept in `localStorage` so a refresh doesn't log you out. The trade-off is that any script on the page can read it; an httpOnly cookie would be safer.

## Not done yet

- Uneven splits (percentages, exact amounts)
- Recording payments so balances update after someone pays
- Rotating who absorbs the remainder cent, so it's fair over time
- Removing members, editing or deleting expenses
- Database migrations (Alembic); tables are currently created with `create_all`
