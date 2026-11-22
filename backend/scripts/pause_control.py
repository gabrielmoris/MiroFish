"""
Round-boundary pause for the simulation scripts.

The backend writes ``pause_control.json`` into the simulation folder (see
SimulationRunner.pause_simulation). The script checks it before every round
and waits there while it says "pause". The OASIS environment stays alive, so
resuming continues with the next round instead of restarting.

Kept free of OASIS imports so it can be unit-tested on its own.
"""

import asyncio
import json
import os
from typing import Callable, Optional


CONTROL_FILENAME = "pause_control.json"
POLL_SECONDS = 1.0


def control_path(simulation_dir: str) -> str:
    return os.path.join(simulation_dir, CONTROL_FILENAME)


def is_pause_requested(simulation_dir: str) -> bool:
    try:
        with open(control_path(simulation_dir), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        # Missing, half-written or unreadable: keep running
        return False
    return isinstance(data, dict) and data.get("action") == "pause"


async def wait_while_paused(
    simulation_dir: str,
    should_stop: Callable[[], bool],
    on_paused: Optional[Callable[[], None]] = None,
    on_resumed: Optional[Callable[[], None]] = None,
    poll_seconds: float = POLL_SECONDS,
) -> bool:
    """
    Wait at a round boundary while a pause is requested.

    Returns True when the round should run, False when the run is shutting
    down (stop requested while paused).
    """
    if not is_pause_requested(simulation_dir):
        return True

    if on_paused:
        on_paused()
    while is_pause_requested(simulation_dir):
        if should_stop():
            return False
        await asyncio.sleep(poll_seconds)

    if should_stop():
        return False
    if on_resumed:
        on_resumed()
    return True
