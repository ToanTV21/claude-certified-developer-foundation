# Cheat Sheet — CCDV-F

## Exam Blueprint (8 domains)
| Domain | Weight |
|--------|--------|
| 1. Agents and Workflows | 14.7% |
| 2. Applications and Integration | 33.1% |
| 3. Claude Code | 3.1% |
| 4. Eval, Testing, and Debugging | 2.6% |
| 5. Model Selection and Optimization | 16.8% |
| 6. Prompt and Context Engineering | 11.0% |
| 7. Security and Safety | 8.1% |
| 8. Tools and MCPs | 10.6% |

## Key Gotchas (luôn nhớ)
| Gotcha | Đúng | Sai |
|--------|------|-----|
| Batch vs realtime | Batch API cho non-urgent, cost-sensitive, high-volume | Sync parallel calls không giảm per-token cost |
| Prompt injection | Cô lập untrusted content, dùng guardrails/hooks | Sửa system prompt "xin đừng" không phải enforceable control |
| Reusable tool integration | MCP server cho khả năng tái sử dụng cross-app | Hard-code logic vào từng system prompt |
| Model selection | Cân bằng quality/latency/cost theo use case | Luôn chọn model nhỏ nhất để tiết kiệm cost bất kể quality |
| Temperature | Không liên quan đến bảo mật / prompt injection | Tăng temperature để "khó đoán hơn" không phải mitigation |

## Điều kiện thi
- 53 câu (multiple-choice + multiple-response, mỗi câu ghi rõ số đáp án cần chọn), 120 phút, passing 720/1000 (scale 100-1000), lệ phí $125, hiệu lực 12 tháng, thi qua Pearson VUE (online proctor hoặc test center).
- Criterion-referenced: đạt chuẩn tuyệt đối (720), không so với thí sinh khác.
- Retake: fail lần 1 chờ 14 ngày, lần 2 chờ 30 ngày, lần 3 chờ 90 ngày. Tối đa 4 lần / 12 tháng. Mỗi lần thi đều mất phí.
- Renew: trong hạn 12 tháng — làm free assessment không cần proctor. Hết hạn — phải thi lại full exam + phí.

## Chi tiết skill theo từng domain (weight con)
### 1. Agents and Workflows (14.7%)
- Agent Architecture (4.5%): workflow vs agent, manager/supervisor hierarchy, subagents.
- Agent Construction with Claude (5.3%): Claude Agent SDK, custom loop/harness, self-hosted vs Anthropic-hosted, hooks.
- Agent Patterns and Frameworks (4.9%): tool-use loop, sub-agents, memory, context-window mgmt, frameworks (Strands, LangGraph, PydanticAI).

### 2. Applications and Integration (33.1%) — domain nặng nhất
- Understanding Requirements (3.4%), Systems Life Cycle (2.8%)
- Claude API Mechanics (6.8%): messages, tools, streaming, vision, thinking, caching, third-party vendors, batch vs realtime.
- Software Engineering Foundations (7.4%): REST, JSON, async, version control, SDLC, code review, refactor.
- Claude Application Design (8.6%): Claude across interfaces (Code/Desktop/claude.ai/API/SDK), content boundaries, schema design, session hygiene, plugin mgmt.
- Configuration Management (4.1%): CLAUDE.md, settings.json, model version pinning, prompt versioning, plugin deps.

### 3. Claude Code (3.1%)
- Claude Code Operation: Rules/Skills/Commands/Agents/Agent Memory, session mgmt, slash commands, headless/streaming/auto-mode, CLAUDE.md hierarchy, repo init, settings.json.

### 4. Eval, Testing, and Debugging (2.6%)
- Debugging/Error Handling: error type ID, recovery strategy, trace analysis, phân biệt lỗi integration layer vs model output.

### 5. Model Selection and Optimization (16.8%)
- LLM Fundamentals (5.2%): tokens, context window, sampling, non-determinism, fast/extended/adaptive thinking, effort levels, zero/single/multi-shot.
- Technical Fundamentals (6.1%): SDK wrap REST, websockets.
- Model Selection and Tradeoffs (2.7%): Opus vs Sonnet vs Haiku, adaptive thinking support, quality/latency/cost, breaking changes across releases.
- Cost and Token Management (2.8%): token tracking, cost modeling, prompt caching, cache checkpointing.

### 6. Prompt and Context Engineering (11.0%)
- Context Engineering (3.8%): context window mgmt, chống drift/bloat (tool output pruning, compaction), context isolation qua subagent.
- Prompt Engineering (4.6%): instruction clarity, few-shot, system vs user placement, output constraints, iterative refinement, input sanitization.
- Output Handling (2.6%): structured output, response validation, defensive parsing, skepticism với confident output.

### 7. Security and Safety (8.1%)
- AI Application Security (3.2%): prompt injection, jailbreak defense, untrusted input, data leakage, PII, AuthN/AuthZ/CIA.
- Guardrails and Safe Deployment (2.3%): content policy, guardrail layering, least privilege.
- Claude Hooks (1.0%): hooks để chặn destructive actions.
- Identity, Secrets, and Key Management (1.6%): secrets/credentials/API key mgmt, access approval, monitoring.

### 8. Tools and MCPs (10.6%)
- Tool Implementation (4.4%): function calling, tool description, error handling, agentic harness dispatch, client-side vs server-side tools, approval patterns.
- MCP Server Development (2.1%): server authoring/deploy, resources/tools/prompts, stdio/sockets, client vs server.
- Agentic Customization (4.1%): tradeoff built-in Tools vs custom Tools vs Skills vs MCPs.
