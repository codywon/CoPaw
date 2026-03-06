import json
import os

from copaw.envs.store import load_envs_into_environ


def test_load_envs_into_environ_applies_copaw_working_dir(
    tmp_path,
    monkeypatch,
):
    env_file = tmp_path / "envs.json"
    env_file.write_text(
        json.dumps(
            {
                "COPAW_WORKING_DIR": "~/.copaw/workspace",
                "EXTRA_FLAG": "1",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "copaw.envs.store.get_envs_json_path",
        lambda: env_file,
    )
    monkeypatch.delenv("COPAW_WORKING_DIR", raising=False)
    monkeypatch.delenv("EXTRA_FLAG", raising=False)

    loaded = load_envs_into_environ()

    assert loaded["COPAW_WORKING_DIR"] == "~/.copaw/workspace"
    assert loaded["EXTRA_FLAG"] == "1"
    assert os.environ["COPAW_WORKING_DIR"] == "~/.copaw/workspace"
    assert os.environ["EXTRA_FLAG"] == "1"
