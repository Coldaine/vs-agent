from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from vs_harness.types import IntentPacket, MoverProposal, PerceptionFrame


class Mover(ABC):
    approach_id: str = "base"

    @abstractmethod
    def propose(
        self,
        perception: PerceptionFrame,
        intent: IntentPacket,
        state: dict[str, Any] | None = None,
    ) -> MoverProposal:
        raise NotImplementedError
