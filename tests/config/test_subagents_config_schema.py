from copaw.config.config import AgentsConfig, SubagentRoleConfig, SubagentsConfig


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


def test_subagent_role_model_policy_defaults_loaded():
    role = SubagentRoleConfig(key="research", name="Research Agent")
    assert role.model_provider == ""
    assert role.model_name == ""
    assert role.fallback_models == []
    assert role.max_tokens is None
    assert role.budget_limit_usd is None
    assert role.reasoning_effort == ""


def test_subagents_keywords_mojibake_is_normalized():
    cfg = SubagentsConfig(
        auto_dispatch_keywords=[
            "parallel",
            "\u03b5\u0389\u0386\u03b8\u2018\u008c",
            "\u03b6\u0089\u0389\u03b9\u0087\u008f",
            "骞惰",
            "鎵归噺",
        ],
    )
    assert cfg.auto_dispatch_keywords == ["parallel", "并行", "批量"]
