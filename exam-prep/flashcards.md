# Flashcards — CCDV-F

Format: **Q:** ... / **A:** ...

## Domain 2 — Applications and Integration
- **Q:** Khi cần xử lý 10,000 documents overnight, không urgent, ưu tiên cost — dùng gì?
  **A:** Message Batches API (xử lý async trong 24h, giá rẻ hơn realtime).

## Domain 7 — Security and Safety
- **Q:** Trang web bị nhúng hidden text yêu cầu Claude tiết lộ system prompt — cách mitigate hiệu quả nhất?
  **A:** Coi content lấy từ web là untrusted input, tách biệt khỏi trusted instructions, dùng guardrails/hooks để chặn injected instructions kích hoạt sensitive actions.

## Domain 8 — Tools and MCPs
- **Q:** Cần Claude gọi 1 internal REST API, tái sử dụng được across nhiều app, maintain độc lập — chọn gì?
  **A:** Xây MCP server expose các operations đó thành tools.

---
Thêm flashcard mới khi học domain mới hoặc gặp câu hỏi sai trong mock exam.
