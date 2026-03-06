from copaw.app.crons.models import JobRuntimeSpec


def test_job_runtime_default_timeout_seconds_is_600() -> None:
    runtime = JobRuntimeSpec()
    assert runtime.timeout_seconds == 600
