from pathlib import Path

from copaw.agents.skills_manager import SkillService


def _write_skill(root: Path, name: str, body: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")
    return skill_dir


def _skill_md(name: str, description: str, marker: str) -> str:
    return (
        f"---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"---\n\n"
        f"{marker}\n"
    )


def _patch_skill_dirs(monkeypatch, builtin: Path, customized: Path, active: Path):
    monkeypatch.setattr(
        "copaw.agents.skills_manager.get_builtin_skills_dir",
        lambda: builtin,
    )
    monkeypatch.setattr(
        "copaw.agents.skills_manager.get_customized_skills_dir",
        lambda: customized,
    )
    monkeypatch.setattr(
        "copaw.agents.skills_manager.get_active_skills_dir",
        lambda: active,
    )


def test_list_all_skills_customized_overrides_builtin_without_duplicates(
    tmp_path: Path,
    monkeypatch,
):
    builtin = tmp_path / "builtin"
    customized = tmp_path / "customized"
    active = tmp_path / "active"
    builtin.mkdir()
    customized.mkdir()
    active.mkdir()

    _write_skill(
        builtin,
        "wechat-content-ops",
        _skill_md("wechat-content-ops", "builtin", "builtin-body"),
    )
    _write_skill(
        customized,
        "wechat-content-ops",
        _skill_md("wechat-content-ops", "custom", "custom-body"),
    )

    _patch_skill_dirs(monkeypatch, builtin, customized, active)

    skills = SkillService.list_all_skills()
    matched = [s for s in skills if s.name == "wechat-content-ops"]

    assert len(matched) == 1
    assert matched[0].source == "customized"
    assert "custom-body" in matched[0].content


def test_delete_skill_removes_customized_and_restores_builtin_in_active(
    tmp_path: Path,
    monkeypatch,
):
    builtin = tmp_path / "builtin"
    customized = tmp_path / "customized"
    active = tmp_path / "active"
    builtin.mkdir()
    customized.mkdir()
    active.mkdir()

    _write_skill(
        builtin,
        "wechat-content-ops",
        _skill_md("wechat-content-ops", "builtin", "builtin-body"),
    )
    _write_skill(
        customized,
        "wechat-content-ops",
        _skill_md("wechat-content-ops", "custom", "custom-body"),
    )
    _write_skill(
        active,
        "wechat-content-ops",
        _skill_md("wechat-content-ops", "custom-active", "custom-active-body"),
    )

    _patch_skill_dirs(monkeypatch, builtin, customized, active)

    deleted = SkillService.delete_skill("wechat-content-ops")
    assert deleted is True

    assert not (customized / "wechat-content-ops").exists()
    active_skill_md = (active / "wechat-content-ops" / "SKILL.md").read_text(
        encoding="utf-8",
    )
    assert "builtin-body" in active_skill_md
