# A3-4: Skills Frequency & Duplicate Analysis

## A3: Frequency Assessment

### 🔴 HIGH (7) — Essential to daily workflow

| Skill | Reason |
|-------|--------|
| `car-evolution` | Boss's main YouTube project |
| `car-evolution-chart-creation` | Chart output for videos |
| `youtube-shorts-competitor-analysis` | Core YouTube strategy |
| `humanizer` | Remove AI-isms for Cantonese content |
| `hermes-cron-telegram-delivery` | Daily reports to Telegram |
| `hermes-operations` | System maintenance |
| `plan-approve-execute` | Required workflow protocol |

### 🟡 MEDIUM (16) — Used for specific tasks

| Skill | Reason |
|-------|--------|
| `cantonese-tts-setup` | TTS for daily conversation |
| `youtube-content` | YouTube transcript analysis |
| `spotify` | Music generation |
| `gif-search` | Visual content |
| `blogwatcher` | RSS monitoring |
| `google-trends-workaround` | Trend research |
| `llm-wiki` | Knowledge wiki |
| `comfyui` | Image/video generation |
| `notion` / `obsidian` | Notes integration |
| `linear` | Project tracking |
| `google-workspace` | Workspace integration |
| `touchdesigner-mcp` | Visual programming |
| `hermes-agent` | Agent configuration |
| `plan` / `writing-plans` | Planning |

### 🟢 LOW (28) — Niche or rare use

| Category | Skills |
|----------|--------|
| Academic | `arxiv`, `research-paper-writing` |
| ML Training | `axolotl`, `fine-tuning-with-trl`, `unsloth`, `dspy` |
| LLM Serving | `llama-cpp`, `serving-llms-vllm`, `weights-and-biases` |
| Coding | `claude-code`, `codex`, `opencode`, `github-*` (6 skills) |
| Music | `heartmula`, `audiocraft-audio-generation`, `songwriting-and-ai-music`, `songsee` |
| Gaming | `minecraft-modpack-server`, `pokemon-player` |
| Visual | `manim-video`, `pixel-art`, `baoyu-infographic`, `excalidraw` |
| Other | `godmode`, `polymarket`, `segment-anything-model`, `webhook-subscriptions` |

### ⚪ UNASSESSED (44)
Need deeper review for: `himalaya`, `airtable`, `maps`, `nano-pdf`, `powerpoint`, `ocr-and-documents`, `openhue`, `xurl`, `spike`, `subagent-driven-development`, `systematic-debugging`, `test-driven-development`, `requesting-code-review`, `python-debugpy`, `node-inspect-debugger`, `codebase-inspection`, `github-auth`, `github-issues`, etc.

---

## A4: Duplicate / Outdated Identification

### 9 Groups Identified (31 skills affected)

#### 1. Planning (2 skills)
- `plan`, `writing-plans`
- Issue: Duplicate functionality
- **Recommendation:** Keep `writing-plans`, deprecate `plan`

#### 2. LLM Serving (2 skills)
- `llama-cpp`, `serving-llms-vllm`
- Issue: Overlapping purpose
- **Recommendation:** Keep `llama-cpp`, deprecate `serving-llms-vllm`

#### 3. Fine-tuning (3 skills)
- `axolotl`, `fine-tuning-with-trl`, `unsloth`
- Issue: Different tools for same purpose
- **Recommendation:** Keep all 3 — each serves different approach

#### 4. Coding Delegation (3 skills)
- `claude-code`, `codex`, `opencode`
- Issue: All delegate coding tasks
- **Recommendation:** Keep `claude-code` + `opencode` (PR review), deprecate `codex`

#### 5. GitHub Suite (6 skills)
- `github-pr-workflow`, `github-code-review`, `github-issues`, `github-repo-management`, `github-auth`, `codebase-inspection`
- Issue: Too many fragmented skills
- **Recommendation:** Consolidate into 2-3 skills under `github` umbrella

#### 6. Hermes Core (4 skills)
- `hermes-agent`, `hermes-operations`, `hermes-agent-skill-authoring`, `debugging-hermes-tui-commands`
- Issue: Scattered functionality
- **Recommendation:** Consolidate into `hermes-operations` (main) + separate skill authoring

#### 7. Car Evolution (3 skills)
- `car-evolution`, `car-evolution-chart-creation`, `car-evolution-v4-deployment`
- Issue: Overlapping names
- **Recommendation:** Keep all 3 — different purposes

#### 8. Music/Audio (5 skills)
- `heartmula`, `songwriting-and-ai-music`, `audiocraft-audio-generation`, `songsee`, `spotify`
- Issue: Overlapping purposes
- **Recommendation:** Keep `heartmula` + `spotify`, deprecate rest

#### 9. Image Generation (3 skills)
- `comfyui`, `touchdesigner-mcp`, `baoyu-infographic`
- Issue: Different tools
- **Recommendation:** Keep `comfyui` + `touchdesigner` (specialized)

---

## Summary

| Metric | Count |
|--------|-------|
| Total Skills | 95 |
| Assessed | 51 |
| HIGH frequency | 7 |
| MEDIUM frequency | 16 |
| LOW frequency | 28 |
| Unassessed | 44 |
| Duplicate groups | 9 |
| Skills affected by dedup | 31 |
| Skills to deprecate | ~15-20 |

---

## Recommended Actions

1. **Immediate:** Deprecate `plan` → use `writing-plans`
2. **Immediate:** Deprecate `serving-llms-vllm` → use `llama-cpp`
3. **Medium-term:** Consolidate GitHub suite into `github` umbrella skill
4. **Medium-term:** Consolidate Hermes core into clearer structure
5. **Low-priority:** Review 44 unassessed skills for potential deprecation