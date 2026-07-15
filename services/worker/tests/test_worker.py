import json

import pytest
from pydantic import ValidationError

from services.worker.app.config import WorkerSettings
from services.worker.app.main import main, run_self_check


def test_worker_self_check_has_zero_production_handlers() -> None:
    result = run_self_check(WorkerSettings(app_environment="test"))
    assert result["status"] == "ready"
    assert result["registered_production_job_handlers"] == 0
    assert result["production_jobs_enabled"] is False


def test_worker_main_prints_readiness_and_exits_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--self-check"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["service"] == "foundation-worker"
    assert output["registered_production_job_handlers"] == 0


def test_worker_configuration_is_validated() -> None:
    with pytest.raises(ValidationError):
        WorkerSettings(app_environment="")
