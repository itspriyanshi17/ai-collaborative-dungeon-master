from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class ActionBatch:
    room_id: str
    actions: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def add(self, action: str) -> None:
        normalized = action.strip()
        if normalized:
            self.actions.append(normalized)
