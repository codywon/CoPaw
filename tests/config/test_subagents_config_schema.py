from copaw.config.config import AgentsConfig


def test_subagents_defaults_loaded():
    cfg = AgentsConfig()
    assert cfg.subagents.max_concurrency == 5
    assert cfg.subagents.write_mode == "worktree"
    assert cfg.subagents.dispatch_mode == "advisory"
    assert cfg.subagents.role_selection_mode == "auto"
    assert cfg.subagents.execution_mode == "sync"
    assert cfg.subagents.retry_max_attempts == 1
    assert "web_search" in cfg.subagents.tools.default_enabled
    assert "web_fetch" in cfg.subagents.tools.default_enabled
