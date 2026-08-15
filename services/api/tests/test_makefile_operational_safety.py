import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_makefile_operational_targets_render_without_running_services() -> None:
    rendered = subprocess.run(
        ["make", "-n", "storage-sweep"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "infra.scripts.storage_sweep" in rendered
    assert "--apply" not in rendered

    applied = subprocess.run(
        ["make", "-n", "storage-sweep", "APPLY=1"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "--apply" in applied

    makefile = (REPOSITORY_ROOT / "Makefile").read_text()
    assert "api.owner" in makefile and "web.owner" in makefile
    assert "process_owned" in makefile
    assert "Refusing to stop live unowned RC PID" in makefile
    assert "kill -KILL" in makefile
    assert "--connect-timeout 2 --max-time 10" in makefile
    assert "exec -T api" in makefile
    assert "hosted-backup" in makefile
