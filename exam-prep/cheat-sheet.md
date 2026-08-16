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
- 53 câu, 120 phút, passing 720/1000, lệ phí $125, hiệu lực 12 tháng.
