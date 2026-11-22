import asyncio
import json
import os
import sys

import pytest

from app.services.simulation_runner import (
    RunnerStatus,
    SimulationRunner,
    SimulationRunState,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import pause_control  # noqa: E402


SIM_ID = "sim_pause_test"


class AliveProcess:
    def poll(self):
        return None


class ExitedProcess:
    def poll(self):
        return 0


@pytest.fixture
def runner(tmp_path, monkeypatch):
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(SimulationRunner, "_run_states", {})
    monkeypatch.setattr(SimulationRunner, "_processes", {})
    monkeypatch.setattr(SimulationRunner, "_monitor_threads", {})
    monkeypatch.setattr(SimulationRunner, "_pause_requests", set())
    monkeypatch.setattr(SimulationRunner, "_parallel_runs", set())
    synced = []
    monkeypatch.setattr(
        SimulationRunner,
        "_sync_simulation_status",
        classmethod(lambda cls, sim_id, status, error=None: synced.append(status)),
    )
    SimulationRunner.synced = synced
    return SimulationRunner


def _running_state(runner, *, parallel=True, process=None):
    state = SimulationRunState(
        simulation_id=SIM_ID,
        runner_status=RunnerStatus.RUNNING,
        twitter_running=True,
        reddit_running=True,
    )
    runner._save_run_state(state)
    runner._processes[SIM_ID] = process or AliveProcess()
    if parallel:
        runner._parallel_runs.add(SIM_ID)
    return state


def _control(runner):
    path = runner._pause_control_path(SIM_ID)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)["action"]


def _log_event(runner, state, platform, event_type):
    sim_dir = os.path.join(runner.RUN_STATE_DIR, SIM_ID, platform)
    os.makedirs(sim_dir, exist_ok=True)
    path = os.path.join(sim_dir, "actions.jsonl")
    position = os.path.getsize(path) if os.path.exists(path) else 0
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"event_type": event_type, "platform": platform}) + "\n")
    runner._read_action_log(path, position, state, platform)


# --- backend: requesting a pause -------------------------------------------

def test_pause_is_a_request_until_the_round_ends(runner):
    _running_state(runner)

    state = runner.pause_simulation(SIM_ID)

    assert _control(runner) == "pause"
    assert state.pause_requested is True
    assert state.runner_status == RunnerStatus.RUNNING
    assert SIM_ID in runner._pause_requests


def test_pause_twice_is_harmless(runner):
    _running_state(runner)
    runner.pause_simulation(SIM_ID)

    assert runner.pause_simulation(SIM_ID).pause_requested is True


@pytest.mark.parametrize(
    "setup",
    [
        lambda r: _running_state(r, parallel=False),
        lambda r: _running_state(r, process=ExitedProcess()),
        lambda r: setattr(_running_state(r), "runner_status", RunnerStatus.COMPLETED),
    ],
    ids=["single-platform script", "process exited", "already completed"],
)
def test_pause_is_rejected_when_it_cannot_take_effect(runner, setup):
    setup(runner)

    with pytest.raises(ValueError):
        runner.pause_simulation(SIM_ID)
    assert _control(runner) is None


def test_pause_is_rejected_once_every_platform_finished_its_rounds(runner):
    state = _running_state(runner)
    _log_event(runner, state, "twitter", "simulation_end")
    _log_event(runner, state, "reddit", "simulation_end")

    # Still RUNNING while the process waits for interview commands
    assert state.runner_status == RunnerStatus.RUNNING
    with pytest.raises(ValueError):
        runner.pause_simulation(SIM_ID)


def test_unknown_simulation_cannot_be_paused_or_resumed(runner):
    with pytest.raises(ValueError):
        runner.pause_simulation("sim_missing")
    with pytest.raises(ValueError):
        runner.resume_simulation("sim_missing")


# --- backend: status follows what the script reports -------------------------

def test_status_is_paused_only_when_every_running_platform_has_stopped(runner):
    state = _running_state(runner)
    runner.pause_simulation(SIM_ID)

    _log_event(runner, state, "twitter", "simulation_paused")
    assert state.runner_status == RunnerStatus.RUNNING

    _log_event(runner, state, "reddit", "simulation_paused")
    assert state.runner_status == RunnerStatus.PAUSED
    assert runner.synced[-1] == RunnerStatus.PAUSED


def test_a_finished_platform_does_not_block_pausing(runner):
    state = _running_state(runner)
    _log_event(runner, state, "twitter", "simulation_start")
    _log_event(runner, state, "reddit", "simulation_end")
    runner.pause_simulation(SIM_ID)

    _log_event(runner, state, "twitter", "simulation_paused")

    assert state.runner_status == RunnerStatus.PAUSED


def test_resume_goes_back_to_running_when_the_script_continues(runner):
    state = _running_state(runner)
    runner.pause_simulation(SIM_ID)
    _log_event(runner, state, "twitter", "simulation_paused")
    _log_event(runner, state, "reddit", "simulation_paused")

    runner.resume_simulation(SIM_ID)
    assert _control(runner) is None
    assert state.pause_requested is False

    _log_event(runner, state, "twitter", "simulation_resumed")
    assert state.runner_status == RunnerStatus.RUNNING
    assert runner.synced[-1] == RunnerStatus.RUNNING


def test_resume_cancels_a_pause_that_has_not_taken_effect(runner):
    state = _running_state(runner)
    runner.pause_simulation(SIM_ID)

    runner.resume_simulation(SIM_ID)

    assert _control(runner) is None
    assert state.pause_requested is False
    assert state.runner_status == RunnerStatus.RUNNING


def test_resume_is_rejected_when_nothing_is_paused(runner):
    _running_state(runner)

    with pytest.raises(ValueError):
        runner.resume_simulation(SIM_ID)


def test_pause_events_do_not_override_a_stop_in_progress(runner):
    state = _running_state(runner)
    runner.pause_simulation(SIM_ID)
    state.runner_status = RunnerStatus.STOPPING

    _log_event(runner, state, "twitter", "simulation_paused")
    _log_event(runner, state, "reddit", "simulation_paused")

    assert state.runner_status == RunnerStatus.STOPPING


def test_finishing_all_rounds_drops_a_pending_pause(runner):
    state = _running_state(runner)
    runner.pause_simulation(SIM_ID)

    _log_event(runner, state, "twitter", "simulation_end")
    _log_event(runner, state, "reddit", "simulation_end")

    assert _control(runner) is None
    assert state.pause_requested is False


def test_restart_cleanup_removes_a_leftover_pause_file(runner):
    _running_state(runner)
    runner.pause_simulation(SIM_ID)
    runner._run_states[SIM_ID].runner_status = RunnerStatus.STOPPED

    runner.cleanup_simulation_logs(SIM_ID)

    assert _control(runner) is None


def test_activity_check_covers_paused_runs_and_live_processes(runner):
    state = _running_state(runner)
    assert runner.is_simulation_active(SIM_ID)

    state.runner_status = RunnerStatus.PAUSED
    assert runner.is_simulation_active(SIM_ID)

    state.runner_status = RunnerStatus.COMPLETED
    assert runner.is_simulation_active(SIM_ID)  # process still alive

    runner._processes[SIM_ID] = ExitedProcess()
    assert not runner.is_simulation_active(SIM_ID)


# --- script: waiting at the round boundary -----------------------------------

def _write(simulation_dir, content):
    with open(pause_control.control_path(str(simulation_dir)), "w", encoding="utf-8") as f:
        f.write(content)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (None, False),
        ('{"action": "pause"}', True),
        ('{"action": "resume"}', False),
        ('{"action": "pa', False),  # half-written
        ('["pause"]', False),
    ],
)
def test_script_reads_the_control_file_defensively(tmp_path, content, expected):
    if content is not None:
        _write(tmp_path, content)

    assert pause_control.is_pause_requested(str(tmp_path)) is expected


def test_script_runs_the_round_immediately_when_not_paused(tmp_path):
    events = []

    result = asyncio.run(pause_control.wait_while_paused(
        str(tmp_path),
        should_stop=lambda: False,
        on_paused=lambda: events.append("paused"),
        on_resumed=lambda: events.append("resumed"),
    ))

    assert result is True
    assert events == []


def test_script_waits_until_resumed(tmp_path):
    _write(tmp_path, '{"action": "pause"}')
    events = []

    async def resume_soon():
        await asyncio.sleep(0.05)
        os.remove(pause_control.control_path(str(tmp_path)))

    async def scenario():
        resumer = asyncio.create_task(resume_soon())
        result = await pause_control.wait_while_paused(
            str(tmp_path),
            should_stop=lambda: False,
            on_paused=lambda: events.append("paused"),
            on_resumed=lambda: events.append("resumed"),
            poll_seconds=0.01,
        )
        await resumer
        return result

    assert asyncio.run(scenario()) is True
    assert events == ["paused", "resumed"]


def test_script_stops_waiting_when_shut_down(tmp_path):
    _write(tmp_path, '{"action": "pause"}')
    calls = {"n": 0}

    def should_stop():
        calls["n"] += 1
        return calls["n"] > 2

    result = asyncio.run(pause_control.wait_while_paused(
        str(tmp_path), should_stop=should_stop, poll_seconds=0.01,
    ))

    assert result is False
