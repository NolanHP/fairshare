"""Pure money logic for FairShare. No database, no FastAPI, so it's easy to test.

All amounts are integer cents.
"""
import heapq
from typing import Dict, Iterable, List, Tuple


def split_equal(amount_cents: int, participant_ids: List[int], payer_id: int) -> Dict[int, int]:
    """Split amount_cents equally among participants. Returns {user_id: cents_owed}.

    divmod gives a base share and a remainder (always < number of participants).
    The leftover cents go to the payer if they're a participant; otherwise one
    extra cent each to participants in user_id order. Deterministic, so the same
    input always gives the same split (and tests can assert exact values).

    Example: 1000 among [1, 2, 3], payer 1 -> {1: 334, 2: 333, 3: 333}
    """
    if amount_cents <= 0:
        raise ValueError("amount must be positive")
    if not participant_ids:
        raise ValueError("need at least one participant")

    base, remainder = divmod(amount_cents, len(participant_ids))
    shares = {uid: base for uid in participant_ids}

    if payer_id in shares:
        shares[payer_id] += remainder
    else:
        for uid in sorted(participant_ids)[:remainder]:
            shares[uid] += 1

    assert sum(shares.values()) == amount_cents  # invariant: nothing created or lost
    return shares


def compute_balances(member_ids: Iterable[int], expenses) -> Dict[int, int]:
    """Net balance per member: total they paid minus total they owe.

    positive -> the group owes them money
    negative -> they owe the group money

    `expenses` is anything with .paid_by, .amount_cents and .splits
    (each split having .user_id and .amount_cents), e.g. the Expense ORM objects.
    """
    balances = {uid: 0 for uid in member_ids}
    for e in expenses:
        balances[e.paid_by] = balances.get(e.paid_by, 0) + e.amount_cents
        for s in e.splits:
            balances[s.user_id] = balances.get(s.user_id, 0) - s.amount_cents

    # Every cent paid is owed by someone, so a group's balances always sum to 0.
    assert sum(balances.values()) == 0
    return balances


def settle(balances: Dict[int, int]) -> List[Tuple[int, int, int]]:
    """Suggest payments that bring every balance to zero.

    Returns a list of (from_user_id, to_user_id, amount_cents).

    Greedy: repeatedly pair the person who owes the most with the person owed the
    most, and have the debtor pay min(debt, credit). Each step zeroes out at least
    one person, so there are at most (n - 1) payments.

    Finding the true MINIMUM number of payments is NP-hard (it's related to
    subset-sum), so greedy is the standard practical choice: simple, O(n log n)
    with heaps, and usually optimal or close to it for real groups.
    """
    # heapq is a min-heap, so store negatives to pop the largest first.
    creditors = [(-amt, uid) for uid, amt in balances.items() if amt > 0]
    debtors = [(amt, uid) for uid, amt in balances.items() if amt < 0]  # amt already negative
    heapq.heapify(creditors)
    heapq.heapify(debtors)

    transfers = []
    while creditors and debtors:
        neg_credit, creditor = heapq.heappop(creditors)
        neg_debt, debtor = heapq.heappop(debtors)
        credit, debt = -neg_credit, -neg_debt

        pay = min(credit, debt)
        transfers.append((debtor, creditor, pay))

        # Whoever isn't fully settled goes back in the heap with what's left.
        if credit > pay:
            heapq.heappush(creditors, (-(credit - pay), creditor))
        if debt > pay:
            heapq.heappush(debtors, (-(debt - pay), debtor))

    return transfers
