# CLAUDE.md — Claude Certified Developer, Foundations Study Project

## Project Purpose
Workspace học + ghi chú + làm bài tập để chuẩn bị thi **CCDV-F (Claude Certified Developer –
Foundations)**.

**Owner:** ToanTV — Senior Android Automotive Engineer, FPT Software Japan
**Target:** Pass CCDV-F (720/1000)
**Stack:** Python 3.10+, `anthropic` SDK, `python-dotenv`, `mcp`
**Official course path:** https://anthropic-partners.skilljar.com/path/claude-certified-developer-foundations
**Official exam guide:** [docs/exam-guide.pdf](docs/exam-guide.pdf)

---

## Directory Layout
```
claudeCertDev_foundation/
├── CLAUDE.md                   ← You are here (project context)
├── AGENTS.md                   ← pointer to CLAUDE.md cho agent khác
├── README.md                   ← progress table + quick start
├── .env / .env.example
├── .gitignore
├── requirements.txt
├── docs/
│   └── exam-guide.pdf          ← official CCDV-F exam guide (Anthropic)
│
├── domains/                    ← 1 folder / exam domain (theo blueprint chính thức)
│   ├── _domain-template.md
│   ├── 01-agents-and-workflows/
│   │   ├── notes.md
│   │   └── exercises/
│   ├── 02-applications-and-integration/
│   ├── 03-claude-code/
│   ├── 04-eval-testing-debugging/
│   ├── 05-model-selection-optimization/
│   ├── 06-prompt-context-engineering/
│   ├── 07-security-and-safety/
│   └── 08-tools-and-mcps/
│       (mỗi domain-NN/ có notes.md + exercises/ riêng)
│
├── exam-prep/                  ← Ôn thi CCDV-F
│   ├── README.md               ← bản đồ ôn thi, bắt đầu từ đây
│   ├── study-plan.md
│   ├── flashcards.md
│   ├── cheat-sheet.md
│   ├── practice-questions.md
│   ├── mock-exam-log.md
│   ├── wrong-answers.md
│   └── references.md
│
└── src/                        ← Shared utilities
    ├── __init__.py
    └── client.py                ← Khởi tạo Anthropic client dùng chung
```

---

## CCDV-F Exam Overview
- **Exam code:** CCDV-F
- **Format:** 53 câu (multiple-choice / multiple-response), 120 phút, passing score 720/1000
- **Lệ phí:** $125 USD, hiệu lực 12 tháng
- **Domains (theo weight, xem chi tiết ở [exam-prep/cheat-sheet.md](exam-prep/cheat-sheet.md)):**

| Domain | Weight |
|--------|--------|
| Agents and Workflows | 14.7% |
| Applications and Integration | 33.1% |
| Claude Code | 3.1% |
| Eval, Testing, and Debugging | 2.6% |
| Model Selection and Optimization | 16.8% |
| Prompt and Context Engineering | 11.0% |
| Security and Safety | 8.1% |
| Tools and MCPs | 10.6% |

- **Đối tượng thi:** AI/ML engineer, technical lead, senior software engineer — build/integrate/ship Claude-powered apps, agents, workflows ở mức foundational.

---

## Coding Conventions
### Python Setup
```python
# Mọi script đều dùng pattern này
from dotenv import load_dotenv
import anthropic
import os
load_dotenv()
client = anthropic.Anthropic()  # tự đọc ANTHROPIC_API_KEY từ .env
# Dev: dùng haiku để tiết kiệm cost
# Prod/test: dùng sonnet
MODEL_DEV  = "claude-haiku-4-5"
MODEL_MAIN = "claude-sonnet-4-6"
```

### Key Gotchas (luôn nhớ)
| Gotcha | Đúng | Sai |
|--------|------|-----|
| Temperature default | `1.0` | `0.7` |
| `system` field | top-level param, không nằm trong `messages` | `messages[0]["role"] = "system"` |
| Batch vs realtime | Batch API cho non-urgent/cost-sensitive | Sync parallel không giảm cost |
| Prompt injection | Cô lập untrusted input + guardrails/hooks | Sửa system prompt "xin đừng" |
| Reusable integration | MCP server cho khả năng tái sử dụng cross-app | Hard-code logic vào prompt |

---

## Common Commands
```bash
# Setup
pip install -r requirements.txt
# Run an exercise
python domains/02-applications-and-integration/exercises/01_example.py
# Start Claude Code interactive session
claude
# Continue last session
claude --continue
```

---

## AI Behavior in This Project
Khi làm việc trong project này, Claude Code nên:
1. **Ưu tiên dùng `claude-haiku-4-5`** cho các bài tập dev/test để tiết kiệm cost
2. **Luôn dùng `python-dotenv`** để load API key, không bao giờ hardcode
3. **Viết code có comments giải thích** vì đây là môi trường học — mỗi đoạn code, mỗi hàm, và mỗi parameter bên trong đều phải có comment giải thích rõ nó làm gì / dùng để làm gì
4. **Khi tạo file note mới** dùng template trong `domains/_domain-template.md`
5. **Khi tạo bài tập mới** đặt trong đúng `domains/NN-ten-domain/exercises/`
6. **Sau khi làm xong bài tập** cập nhật status trong progress table ở `README.md`
6b. **Sau mỗi lần write/edit file** phải `git add` + `git commit` (message ngắn gọn) rồi `git push` lên remote GitHub ngay, không gộp nhiều thay đổi rồi mới commit 1 lần
7. **Ngôn ngữ:**
   - **Khi chat trực tiếp với user:** luôn dùng **tiếng Anh**.
   - **Khi ghi note vào file** (notes.md, comment trong code...): luôn viết phần giải thích bằng **tiếng Việt**. Keyword/thuật ngữ kỹ thuật giữ nguyên **tiếng Anh**, không dịch.
8. **Khi user yêu cầu "giải thích chi tiết code"**, áp dụng đúng format sau:
   - Explain theo **từng đoạn code ngắn** (1 block nhỏ mỗi lần), không giải thích dồn cả file trong 1 đoạn văn dài
   - Với mỗi đoạn: trích lại code block đó trước, rồi giải thích ý nghĩa từng phần/cú pháp bên dưới
   - **User là Senior Android Automotive Engineer, code chính là Java** — khi giải thích cú pháp Python lạ, nếu có khái niệm tương đương trong Java/Android thì đối chiếu ngắn gọn để dễ liên tưởng
   - Kết thúc bằng phần **"Tóm tắt luồng chạy"** ngắn gọn, liệt kê các bước theo thứ tự
   - Nếu file đích là bài tập trong `exercises/`, lưu giải thích vào file `.md` riêng cùng cấp, đặt tên `<tên_file_exercise>_notes.md`, rồi git add/commit/push theo rule 6b

---

## Note-Taking Template
Mỗi `notes.md` trong `domains/NN-ten-domain/` theo cấu trúc:
```markdown
# Domain N: [Tên domain] (X% weight)
## Skills trong domain này (theo exam blueprint)
- [ ] Skill 1 (X.X%)
## Key Concepts
- ...
## Important APIs / Parameters
| Name | Type | Default | Notes |
|------|------|---------|-------|
## Gotchas
- [ ] ...
## Exam Tips
- ...
## Code Snippets
\`\`\`python
# snippet
\`\`\`
## Questions / Unclear Points
- ?
```

## Exercise Template
Mỗi file trong `domains/NN-ten-domain/exercises/` theo cấu trúc:
```python
"""
Exercise XX-YY: [Tên bài tập]
Domain: [Tên domain]
Objective: [Mục tiêu]
"""
from dotenv import load_dotenv
import anthropic
load_dotenv()
client = anthropic.Anthropic()
MODEL = "claude-haiku-4-5"  # dùng haiku cho dev
def main():
    # TODO: implement
    pass
if __name__ == "__main__":
    main()
```
