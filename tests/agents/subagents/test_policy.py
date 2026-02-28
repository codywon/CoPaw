from copaw.agents.subagents.policy import (
    select_role_for_task,
    should_force_dispatch,
)
from copaw.config.config import SubagentRoleConfig, SubagentsConfig


def test_should_force_dispatch_by_default_mode():
    cfg = SubagentsConfig(enabled=True, dispatch_mode="force_by_default")
    decision = should_force_dispatch("hello", cfg)
    assert decision.should_dispatch is True
    assert "force_by_default" in decision.reason


def test_should_force_dispatch_when_keyword_matched():
    cfg = SubagentsConfig(
        enabled=True,
        dispatch_mode="force_when_matched",
        auto_dispatch_keywords=["batch", "parallel"],
    )
    decision = should_force_dispatch("please run batch processing", cfg)
    assert decision.should_dispatch is True
    assert "keyword" in decision.reason


def test_should_not_force_dispatch_in_advisory():
    cfg = SubagentsConfig(enabled=True, dispatch_mode="advisory")
    decision = should_force_dispatch("batch process everything", cfg)
    assert decision.should_dispatch is False


def test_select_role_for_task_matches_routing_keywords():
    cfg = SubagentsConfig(
        enabled=True,
        roles=[
            SubagentRoleConfig(
                key="news",
                name="News Agent",
                routing_keywords=["news", "资讯"],
            ),
            SubagentRoleConfig(
                key="code",
                name="Code Agent",
                routing_keywords=["code", "refactor"],
            ),
        ],
    )
    role = select_role_for_task("请采集news并总结", cfg)
    assert role is not None
    assert role.key == "news"
