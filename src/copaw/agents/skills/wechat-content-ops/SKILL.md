---
name: wechat-content-ops
description: "Use when the user wants WeChat public-account content operations: fetch AI hotspots via installed agent-reach MCP tools, shortlist topics for user confirmation, write high-quality human-style soft articles, and prepare a draftbox-ready publishing payload."
---

# WeChat Content Ops

Build a repeatable workflow for public-account growth:
- Fetch cross-platform hotspots with installed `agent-reach` MCP tools.
- Propose ranked topics and wait for user confirmation.
- Write a publish-ready article with clear value and low "AI tone".
- Prepare image prompts and a draftbox payload (reserved unless user asks to publish).

## Hard Rules

1. Always use installed `agent-reach` MCP tools first for hotspot collection.
2. Never skip topic confirmation. Writing starts only after the user picks a topic.
3. Do not auto-publish. Prepare draft payload and ask for explicit approval.
4. Keep the article practical: methods, examples, and execution details.
5. Avoid empty claims and generic AI jargon.

## Tooling Priority

1. `agent-reach` MCP tools (preferred):
- Xiaohongshu-like tools: `search_feeds`, `list_feeds`, `get_feed_detail`
- Douyin-like tools: `parse_douyin_video_info`, `extract_douyin_text`
- Exa-like tools: web/news/document retrieval
2. CoPaw web tools as fallback only when MCP is unavailable.

If MCP filtering fails due option-encoding issues, retry with keyword-only search.

## Execution Workflow

1. Collect hotspots
- Query 3-6 keywords that match the user niche (default seed: `AI`, `AIGC`, `Agent`, `智能体`, `DeepSeek`).
- Pull engagement fields when available: likes, comments, collects, shares.
- Keep only relevant items (filter out off-topic entertainment/noise).

2. Build topic board
- Produce 5-10 topic candidates.
- Rank each candidate by:
  - Attention potential (title tension + social spread)
  - Commercial relevance (fit to account goals)
  - Actionability (can provide practical steps)
  - Risk (compliance, controversy, unverifiable claims)
- Output top 3 with "why now" and "angle".

3. Ask user to confirm topic
- Wait for explicit user choice (`1/2/3` or custom).
- If user says "rewrite style", revise angle and ask again.

4. Write the article
- Follow this structure:
  - Hook: one real scene + conflict in first 120 words
  - Core: 3-5 actionable sections, each with step/example/pitfall
  - Proof: references, mini cases, or concrete numbers
  - Close: one clear next action + next-issue teaser
- Keep strong human voice:
  - Use concrete details (time, role, action, result)
  - Mix short and long sentences
  - Keep opinionated but defensible
  - Remove template-sounding filler

5. Design image plan (Gemini 3)
- Provide 4-6 image prompts:
  - Cover image
  - Problem scene
  - Method infographic
  - Step flowchart
  - Closing teaser
- Prompts must specify:
  - Aspect ratio
  - Style direction
  - Key objects
  - Chinese typography requirements if needed

6. Prepare draftbox payload (reserved)
- Return a structured payload for public-account draft creation:
  - title
  - digest
  - content_html or markdown
  - cover_image_plan
  - media_assets
  - tags
- Do not call publish API unless user explicitly requests "publish now".

## Output Contract

Always respond in this order:

1. `Hotspot Board`
- Table: source, topic, engagement, why it matters

2. `Topic Options`
- 3 options, each with angle and expected reader value

3. `Waiting For Confirmation`
- Ask user to pick one option

After confirmation:

4. `Final Article`
- Complete publish-ready text

5. `Gemini 3 Image Prompts`
- 4-6 prompts

6. `Draftbox Payload (Reserved)`
- Structured JSON-like block

## Quality Checklist

Before returning the article:
- Includes at least 3 concrete actionable points
- Includes at least 2 concrete examples or mini-cases
- No obvious "AI assistant tone" boilerplate
- Title is specific, not generic
- Ending contains next-issue teaser sentence

## References

For reusable templates and prompt packs:
- `references/prompt-pack.md`
