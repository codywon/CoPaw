from copaw.agents.subagents.router import LocalModelRouter
from copaw.config.config import SubagentRoleConfig


def test_local_model_router_prefers_role_primary_and_parses_fallbacks():
    router = LocalModelRouter()
    role = SubagentRoleConfig(
        key="research",
        name="Research",
        model_provider="openai",
        model_name="gpt-5-mini",
        fallback_models=["gpt-4o-mini", "anthropic/claude-3-5-sonnet"],
        max_tokens=4096,
        reasoning_effort="medium",
    )

    plan = router.select(
        role,
        task_ctx={
            "active_provider": "openai",
            "active_model": "gpt-5-chat",
        },
    )
    assert plan.primary.provider == "openai"
    assert plan.primary.model == "gpt-5-mini"
    assert (plan.fallbacks[0].provider, plan.fallbacks[0].model) == (
        "openai",
        "gpt-4o-mini",
    )
    assert (plan.fallbacks[1].provider, plan.fallbacks[1].model) == (
        "anthropic",
        "claude-3-5-sonnet",
    )
    assert plan.max_tokens == 4096
    assert plan.reasoning_effort == "medium"


def test_local_model_router_falls_back_to_active_model():
    router = LocalModelRouter()
    role = SubagentRoleConfig(
        key="general",
        name="General",
    )

    plan = router.select(
        role,
        task_ctx={
            "active_provider": "openai",
            "active_model": "gpt-5-chat",
        },
    )
    assert plan.primary.provider == "openai"
    assert plan.primary.model == "gpt-5-chat"
    assert plan.fallbacks == []
