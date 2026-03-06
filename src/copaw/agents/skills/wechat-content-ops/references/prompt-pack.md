# Prompt Pack

## A. Hotspot Mining Prompt

Use this when collecting raw materials from `agent-reach` MCP:

```text
Collect AI-related hotspots from installed agent-reach sources.
Keywords: [AI, AIGC, Agent, 智能体, DeepSeek]
Return fields: title, source, author, likes, comments, collects, shares, link/id.
Filter out irrelevant entertainment content.
Keep only items that can be converted into practical public-account topics.
```

## B. Topic Ranking Prompt

```text
Rank topic candidates for a WeChat public-account article.
Score dimensions:
1) Attention potential
2) Commercial relevance
3) Actionability
4) Risk/compliance
Output top 3 topics with:
- one-sentence angle
- why-now reason
- target reader
- expected engagement signal
```

## C. Article Writing Prompt (Low AI Tone)

```text
Write a Chinese long-form article for WeChat public account.
Requirements:
- Human style, natural rhythm, no empty AI buzzwords
- Start with a real scenario and conflict
- 3-5 actionable sections, each: method + example + pitfall
- Add concrete details (time/action/result)
- End with one clear CTA and a teaser for next article
Length target: 1200-1800 Chinese characters.
```

## D. "De-AI-Tone" Rewrite Prompt

```text
Rewrite the article to reduce AI tone.
Rules:
- Remove generic phrases (赋能/闭环/重塑/降本增效 if not concrete)
- Replace abstract claims with specific actions and outcomes
- Vary sentence length and syntax
- Keep clear personality and viewpoint
- Keep all factual content unchanged
```

## E. Gemini 3 Image Prompt Template

Use this template for each image:

```text
[Image Type]: cover / scene / infographic / flowchart / closing
Aspect Ratio: [e.g., 16:9 or 4:3]
Style: realistic editorial, natural light, subtle film grain, not 3D
Scene: [what is happening]
Key Objects: [3-6 objects]
Mood: [e.g., focused, urgent, optimistic]
Typography: Chinese title text [optional], clean layout, readable
Color Direction: [e.g., warm amber + neutral gray]
Output: high detail, publication-ready
```

### Example Set

1. Cover
```text
Aspect Ratio: 16:9
Style: realistic editorial
Scene: creator working late at desk with WeChat draft editor on screen
Key Objects: laptop, notebook, sticky notes, coffee mug, phone
Mood: determined and focused
Typography: “一个人，也能跑通内容流水线”
Color Direction: warm amber with slate gray
```

2. Method Infographic
```text
Aspect Ratio: 4:3
Style: clean infographic
Scene: five-step workflow diagram
Key Objects: nodes and arrows labeled in Chinese:
抓爆点 -> 选题评分 -> 起稿 -> 去AI味 -> 草稿箱
Mood: clear and operational
Typography: high readability, mobile-first
Color Direction: white background, black text, orange accent
```

## F. Draftbox Payload Template (Reserved)

```json
{
  "title": "string",
  "digest": "string",
  "content_markdown": "string",
  "cover_image_plan": {
    "primary_prompt": "string",
    "alternate_prompt": "string"
  },
  "inline_images": [
    {"slot": 1, "purpose": "problem-scene", "prompt": "string"},
    {"slot": 2, "purpose": "method-infographic", "prompt": "string"},
    {"slot": 3, "purpose": "flowchart", "prompt": "string"}
  ],
  "tags": ["AI", "智能体", "内容运营"],
  "publish": {
    "mode": "draft_only",
    "requires_user_confirmation": true
  }
}
```
