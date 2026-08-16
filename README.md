# Claude Certified Developer – Foundations (CCDV-F) Study Workspace — ToanTV

Workspace học + ghi chú + làm bài tập chuẩn bị thi **CCDV-F (Claude Certified Developer –
Foundations)**.

- **Owner:** ToanTV — Senior Android Automotive Engineer, FPT Software Japan
- **Target:** Pass CCDV-F (720/1000)
- **Stack:** Python 3.10+, `anthropic` SDK, `python-dotenv`, `mcp`

Chi tiết layout, conventions, và AI behavior khi làm việc trong project này:
xem [CLAUDE.md](CLAUDE.md).

## Quick Start

```bash
git clone https://github.com/ToanTV21/claude-certified-developer-foundation.git
cd claude-certified-developer-foundation
pip install -r requirements.txt
cp .env.example .env   # rồi điền ANTHROPIC_API_KEY của bạn
python src/client.py   # health check — in ra response mẫu từ Claude
```

## Domain Progress (theo exam blueprint CCDV-F)

Mỗi domain nằm trong 1 folder riêng dưới `domains/`, gồm `notes.md` (ghi chú lý thuyết)
+ `exercises/` (code thực hành).

| # | Domain folder | Domain | Weight | Status |
|---|----------------|--------|--------|--------|
| 01 | [domains/01-agents-and-workflows](domains/01-agents-and-workflows/notes.md) | Agents and Workflows | 14.7% | ⬜ Todo |
| 02 | [domains/02-applications-and-integration](domains/02-applications-and-integration/notes.md) | Applications and Integration | 33.1% | ⬜ Todo |
| 03 | [domains/03-claude-code](domains/03-claude-code/notes.md) | Claude Code | 3.1% | ⬜ Todo |
| 04 | [domains/04-eval-testing-debugging](domains/04-eval-testing-debugging/notes.md) | Eval, Testing, and Debugging | 2.6% | ⬜ Todo |
| 05 | [domains/05-model-selection-optimization](domains/05-model-selection-optimization/notes.md) | Model Selection and Optimization | 16.8% | ⬜ Todo |
| 06 | [domains/06-prompt-context-engineering](domains/06-prompt-context-engineering/notes.md) | Prompt and Context Engineering | 11.0% | ⬜ Todo |
| 07 | [domains/07-security-and-safety](domains/07-security-and-safety/notes.md) | Security and Safety | 8.1% | ⬜ Todo |
| 08 | [domains/08-tools-and-mcps](domains/08-tools-and-mcps/notes.md) | Tools and MCPs | 10.6% | ⬜ Todo |

## Layout

- `domains/` — 1 folder / exam domain: `notes.md` + `exercises/`
- `exam-prep/` — ôn thi CCDV-F — [**bản đồ ôn thi / thứ tự đọc**](exam-prep/README.md) ← bắt đầu từ đây
  ([study plan](exam-prep/study-plan.md),
  [flashcards](exam-prep/flashcards.md),
  [cheat-sheet](exam-prep/cheat-sheet.md),
  [practice questions](exam-prep/practice-questions.md),
  [mock exam log](exam-prep/mock-exam-log.md),
  [wrong answers log](exam-prep/wrong-answers.md),
  [official guide references](exam-prep/references.md))
- `docs/` — official exam guide PDF từ Anthropic
- `src/` — shared utilities (Anthropic client)
