"""Post-sync processors.

A processor runs after every sync with the IDs of new transactions, e.g. to auto-categorize
them or detect transfers between the household's own accounts. Add one by implementing
`Processor` and registering it in pipeline/registry.py; the sync service doesn't change.
"""

from abc import ABC, abstractmethod

from sqlalchemy.orm import Session


class Processor(ABC):
    """One post-sync step. `name` appears in sync errors if the processor fails."""

    name: str

    @abstractmethod
    def run(self, db: Session, household_id: int, new_transaction_ids: list[int]) -> None: ...
