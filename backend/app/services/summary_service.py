"""Dashboard totals: net worth, assets, liabilities, and breakdowns by kind and by person.

Used by api/v1/summary.py. Only accounts in the resolved scope are counted.
"""

from collections import defaultdict

from sqlalchemy.orm import Session

from app.core.scope import Scope
from app.models.enums import AccountKind
from app.repositories import account_repo, connection_repo, household_repo
from app.schemas.summary import KindTotal, OwnerTotal, SummaryOut


def summary(db: Session, scope: Scope, household_id: int) -> SummaryOut:
    accounts = account_repo.list_by_ids(db, scope.account_ids)
    names = {u.id: u.display_name for _, u in household_repo.list_members(db, household_id)}

    by_kind: dict[str, list[int]] = defaultdict(list)
    by_owner: dict[int | None, int] = defaultdict(int)
    for a in accounts:
        by_kind[a.kind].append(a.balance_cents)
        by_owner[a.owner_user_id] += a.balance_cents

    # Credit cards and loans have negative balances, so they count as liabilities.
    balances = [a.balance_cents for a in accounts]
    return SummaryOut(
        scope=scope.key,
        net_worth_cents=sum(balances),
        assets_cents=sum(b for b in balances if b > 0),
        liabilities_cents=sum(b for b in balances if b < 0),
        account_count=len(accounts),
        by_kind=[
            KindTotal(kind=AccountKind(k), total_cents=sum(v), account_count=len(v))
            for k, v in by_kind.items()
        ],
        by_owner=[
            OwnerTotal(
                owner_user_id=owner,
                name="Joint" if owner is None else names.get(owner, "Former member"),
                total_cents=total,
            )
            # Members by ID, then "Joint" last.
            for owner, total in sorted(by_owner.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))
        ],
        last_synced_at=connection_repo.last_synced_at(db, household_id),
    )
