"""Stage interface: every pipeline stage implements Stage.run()."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.sentinel import ScanState


class Stage(ABC):
    """Common contract for all 14 pipeline stages."""

    @abstractmethod
    async def run(self, state: ScanState) -> ScanState:
        """Execute this stage, return the (mutated) state."""
        ...

    def _error(
        self,
        state: ScanState,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        user_facing: bool = True,
    ) -> ScanState:
        """Attach a structured error envelope to the state."""
        state.pipeline_error = {
            "code": code,
            "message": message,
            "retryable": retryable,
            "user_facing": user_facing,
        }
        return state
