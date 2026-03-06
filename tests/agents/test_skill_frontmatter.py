from pathlib import Path

import frontmatter


def test_builtin_skill_frontmatter_is_valid_yaml():
    skills_root = (
        Path(__file__).resolve().parents[2] / "src" / "copaw" / "agents" / "skills"
    )
    skill_files = sorted(skills_root.glob("*/SKILL.md"))

    assert skill_files, "No built-in SKILL.md files found."

    for skill_file in skill_files:
        content = skill_file.read_text(encoding="utf-8")
        post = frontmatter.loads(content)

        assert post.get("name"), f"Missing 'name' in {skill_file}"
        assert post.get("description"), f"Missing 'description' in {skill_file}"
