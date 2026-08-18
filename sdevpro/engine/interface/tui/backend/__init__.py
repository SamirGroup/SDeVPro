"""Backend bridge for external TUI clients."""

from sdevpro.engine.interface.tui.backend.controller import TuiController
from sdevpro.engine.interface.tui.backend.server import TuiBackendServer


__all__ = ["TuiBackendServer", "TuiController"]
