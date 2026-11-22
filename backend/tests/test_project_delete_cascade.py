import os
from datetime import datetime

import pytest

from app import create_app
from app.api import graph as graph_api
from app.models.project import ProjectManager
from app.services.report_agent import Report, ReportManager, ReportStatus
from app.services.simulation_manager import SimulationManager
from app.services.simulation_runner import (
    RunnerStatus,
    SimulationRunner,
    SimulationRunState,
)


@pytest.fixture
def storage(tmp_path, monkeypatch):
    dirs = {
        "projects": tmp_path / "projects",
        "simulations": tmp_path / "simulations",
        "reports": tmp_path / "reports",
    }
    for path in dirs.values():
        path.mkdir()
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(dirs["projects"]))
    monkeypatch.setattr(SimulationManager, "SIMULATION_DATA_DIR", str(dirs["simulations"]))
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(dirs["simulations"]))
    monkeypatch.setattr(ReportManager, "REPORTS_DIR", str(dirs["reports"]))
    for attr in ("_run_states", "_processes", "_monitor_threads"):
        monkeypatch.setattr(SimulationRunner, attr, {})
    for attr in ("_pause_requests", "_parallel_runs"):
        monkeypatch.setattr(SimulationRunner, attr, set())
    return dirs


@pytest.fixture
def deleted_graphs(monkeypatch):
    calls = []
    monkeypatch.setattr(graph_api, "_delete_cloud_graph_if_present", calls.append)
    return calls


@pytest.fixture
def client(storage):
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def _project(graph_id="graph_1"):
    project = ProjectManager.create_project(name="Cascade test")
    project.graph_id = graph_id
    ProjectManager.save_project(project)
    return project


def _simulation(project_id, graph_id="graph_1"):
    return SimulationManager().create_simulation(project_id=project_id, graph_id=graph_id)


def _report(simulation_id, n):
    report = Report(
        report_id=f"report_{simulation_id}_{n}",
        simulation_id=simulation_id,
        graph_id="graph_1",
        simulation_requirement="test",
        status=ReportStatus.COMPLETED,
        created_at=datetime.now().isoformat(),
    )
    ReportManager.save_report(report)
    return report


def _set_run_status(simulation_id, status):
    SimulationRunner._save_run_state(
        SimulationRunState(simulation_id=simulation_id, runner_status=status)
    )


def test_delete_removes_project_simulations_reports_and_graph(client, storage, deleted_graphs):
    project = _project()
    first = _simulation(project.project_id)
    second = _simulation(project.project_id)
    _report(first.simulation_id, 1)
    _report(first.simulation_id, 2)
    _report(second.simulation_id, 1)
    _set_run_status(first.simulation_id, RunnerStatus.COMPLETED)
    other_project = _project(graph_id="graph_other")
    untouched = _simulation(other_project.project_id, graph_id="graph_other")
    _report(untouched.simulation_id, 1)

    response = client.delete(f"/api/graph/project/{project.project_id}")

    assert response.status_code == 200
    assert response.json["data"]["deleted_simulations"] == 2
    assert response.json["data"]["deleted_reports"] == 3
    assert deleted_graphs == ["graph_1"]
    assert ProjectManager.get_project(project.project_id) is None
    assert SimulationManager().list_simulations(project_id=project.project_id) == []
    assert ReportManager.list_reports(simulation_id=first.simulation_id) == []
    assert first.simulation_id not in SimulationRunner._run_states
    # Another project's data is left alone
    assert ProjectManager.get_project(other_project.project_id) is not None
    assert os.path.isdir(storage["simulations"] / untouched.simulation_id)
    assert len(ReportManager.list_reports(simulation_id=untouched.simulation_id)) == 1


@pytest.mark.parametrize("status", [
    RunnerStatus.STARTING,
    RunnerStatus.RUNNING,
    RunnerStatus.PAUSED,
    RunnerStatus.STOPPING,
])
def test_delete_is_refused_while_a_simulation_is_active(client, storage, deleted_graphs, status):
    project = _project()
    simulation = _simulation(project.project_id)
    _report(simulation.simulation_id, 1)
    _set_run_status(simulation.simulation_id, status)

    response = client.delete(f"/api/graph/project/{project.project_id}")

    assert response.status_code == 409
    assert simulation.simulation_id in response.json["error"]
    assert deleted_graphs == []
    assert ProjectManager.get_project(project.project_id) is not None
    assert os.path.isdir(storage["simulations"] / simulation.simulation_id)
    assert len(ReportManager.list_reports(simulation_id=simulation.simulation_id)) == 1


def test_nothing_local_is_deleted_when_the_graph_is_still_in_use(client, storage, monkeypatch):
    project = _project()
    simulation = _simulation(project.project_id)

    def graph_in_use(graph_id):
        raise graph_api.GraphInUseError(f"Graph {graph_id} is in use")

    monkeypatch.setattr(graph_api, "_delete_cloud_graph_if_present", graph_in_use)

    response = client.delete(f"/api/graph/project/{project.project_id}")

    assert response.status_code == 409
    assert ProjectManager.get_project(project.project_id) is not None
    assert os.path.isdir(storage["simulations"] / simulation.simulation_id)


def test_simulations_left_behind_by_a_deleted_project_can_be_cleaned_up(client, storage, deleted_graphs):
    project = _project()
    orphan = _simulation(project.project_id)
    ProjectManager.delete_project(project.project_id)

    response = client.delete(f"/api/graph/project/{project.project_id}")

    assert response.status_code == 200
    assert response.json["data"]["deleted_simulations"] == 1
    assert not os.path.exists(storage["simulations"] / orphan.simulation_id)
    assert deleted_graphs == [None]


def test_unknown_project_is_not_found(client, storage, deleted_graphs):
    response = client.delete("/api/graph/project/proj_missing")

    assert response.status_code == 404
    assert deleted_graphs == []
