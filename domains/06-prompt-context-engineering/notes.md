# Domain 6: Prompt and Context Engineering (11.0%)

## Skills trong domain này (theo exam blueprint)
- [ ] Context Engineering (3.8%) — context window management, prevention of context drift/bloat (tool output pruning, compaction), context isolation qua subagents/multi-step workflows
- [ ] Prompt Engineering (4.6%) — instruction clarity, few-shot examples, system vs. user placement, output constraints, prompt/instruction placement across components, iterative refinement, prompt adjustment, input sanitization
- [ ] Output Handling (2.6%) — structured output patterns, response validation, defensive parsing, skepticism toward confident output

## Key Concepts

### Bốn kỹ thuật "production-grade prompting" (System Prompts, XML, Few-shot, Output Constraints)
- Một prompt chạy tốt trong tương tác thủ công (interactive) thường **vỡ khi lên production** vì gặp
  input chưa test tới. Cách sửa **không phải** thêm chữ vào prompt rồi chạy lại — đó là phản xạ khiến
  vấn đề khó chẩn đoán hơn và hiếm khi thực sự fix được lỗi, vì rewording chỉ đổi *cách nói*, không bổ
  sung *phần cấu trúc còn thiếu*.
- **Quy tắc chẩn đoán**: mỗi loại lỗi output tương ứng đúng 1 trong 4 kỹ thuật đang thiếu. Phải xác
  định đúng loại lỗi trước, rồi thêm đúng kỹ thuật đó, chạy lại để kiểm tra — nếu vẫn sai thì chẩn đoán
  lại, không thêm chữ tràn lan.

| Quan sát được (failure mode) | Kỹ thuật còn thiếu | Vì sao đây là kỹ thuật cần thêm |
|---|---|---|
| Output sai **hình dạng** (shape): câu văn thay vì label, prose thay vì JSON | **Output constraint** | Prompt chưa quy định form/field name/điểm dừng của response — thiếu constraint thì model trả về text hợp lý nhưng parser downstream không chấp nhận được |
| Nội dung **lệch hướng**: scope trôi, đổi tone, trả lời rộng hơn câu hỏi, càng về sau conversation càng tệ | **System prompt** (hoặc system prompt cụ thể hơn) | System prompt là "hợp đồng hành vi" áp dụng cho mọi turn — nếu mơ hồ thì không có gì giữ role/scope/format ổn định khi conversation kéo dài |
| Task đúng nhưng **cấu trúc bị bịa ra**: model hiểu đúng việc cần làm nhưng tự nghĩ ra 1 format khác | **Few-shot examples** | Model không thể suy luận ra cấu trúc chính xác chỉ từ mô tả bằng lời — cần *cho xem* mẫu (1 cặp input/output đúng), không chỉ *mô tả* |
| Output sạch với input đã test nhưng **vỡ với input lạ** (edge case, field bất thường) | **Constraint bao phủ variant đó** | Prompt mới chỉ validate trên tập input hẹp (happy path), chưa có rule/ví dụ cho case gây vỡ parser |

- **Worked example (classification prompt)**: bài toán phân loại ticket hỗ trợ thành 3 nhóm
  `BILLING` / `TECHNICAL` / `ESCALATION`.
  - **Prompt lỗi (bare instruction)**: `system: "You are a support classifier. Classify the ticket."`
    → output không nhất quán qua các lần chạy: "Billing", "billing", hoặc cả câu văn "This looks like
    a billing issue." → router phía sau vỡ vì không parse được.
  - **Chẩn đoán**: đúng kiểu lỗi ở hàng đầu bảng trên → thiếu **output constraint**.
  - **Fix**: thêm output constraint kéo theo 2 kỹ thuật khác đi kèm — 3 kỹ thuật làm 3 việc khác nhau:
    - **System prompt** quy định rõ tập nhãn cố định + "return only the label, no other text" (= hợp
      đồng output).
    - **Few-shot examples** (`<sample_input>`/`<ideal_output>`) cho đúng casing/format cần trả về (=
      cho xem hình dạng chính xác).
    - **XML tags** bọc riêng từng ví dụ, để model không hiểu nhầm ví dụ là 1 phần của instruction (=
      phân ranh giới nội dung).
- **Khi nào stack đủ 4 kỹ thuật / khi nào đơn giản hoá / khi nào dừng lại chẩn đoán**:
  - **Stack cả 4 kỹ thuật**: task có output contract rõ ràng, nhiều edge case có thể minh hoạ bằng ví dụ.
  - **Đơn giản hoá**: task đơn giản (vd "summarize this paragraph") không cần few-shot + output schema
    — thêm cả 4 kỹ thuật vào task đơn giản là thừa, chỉ làm prompt dài không cần thiết.
  - **Dừng lại để chẩn đoán**: nếu đã re-prompt **5 lần** mà output vẫn sai và prompt cứ dài thêm mỗi
    lần → đó là dấu hiệu đang bỏ qua bước chẩn đoán, chỉ thêm chữ chứ không thêm đúng kỹ thuật.
- **System prompt** = "hợp đồng hành vi" cho toàn bộ session — viết 1 lần, coi là lớp instruction bền
  vững (persistent instruction layer), định nghĩa role, output format, và các rule không được đổi giữa
  các turn/conversation.

### Structured Outputs — chuyển quyền kiểm soát output từ prompt sang API
- **Vấn đề của cách làm bằng prompt**: mọi kỹ thuật ở trên (system prompt, XML, few-shot, output
  constraint bằng lời) đều chỉ là **yêu cầu** (request) tới model — model vẫn có thể trả về câu lạc đề,
  sai field name, hoặc JSON hỏng ở input chưa test tới.
- **Structured Outputs** = cơ chế của Claude API tách biệt khỏi prompt: thay vì mô tả hình dạng output
  bằng lời, đưa thẳng 1 **JSON schema** cho API, model bị ràng buộc tại thời điểm sinh token
  (**constrained decoding**) — output vi phạm schema **không thể được sinh ra** ngay từ đầu.
- **2 cơ chế con** (dùng riêng hoặc kết hợp trong cùng 1 request):
  - **JSON outputs** — ràng buộc **response cuối cùng**: set `output_config.format` với
    `type: "json_schema"` + `schema`. Dùng khi chính model tạo ra payload có cấu trúc mà code
    downstream cần đọc (vd extract field từ support ticket) — loại bỏ code parse-and-retry.
  - **Strict tool use** — ràng buộc **input Claude truyền vào tool**: set `strict: true` trên tool
    definition, argument Claude gửi được validate theo `input_schema` **trước khi** code tự viết chạy.
    Dùng trong agentic loop, nơi 1 tool argument sai format có thể crash function hoặc trigger nhầm
    hành động.
- **Vì sao đây là việc của production code, không chỉ của prompt**: instruction "chỉ trả JSON thôi" ở
  mức prompt đúng với case đã test rồi trượt ở edge case chưa test (đúng lỗi ở worked example
  classification phía trên). Schema constraint **không trượt** vì API enforce trên **từng token**,
  chuyển "output đúng format" từ *kiểm tra sau khi nhận response* thành *API loại trừ khả năng sai ngay
  từ lúc sinh*.
- **Chi phí phải cân nhắc trước khi bật mặc định everywhere**:
  - Request đầu tiên trên 1 schema mới **chậm hơn** — API compile schema thành "grammar" trước khi
    ràng buộc được. Grammar cache 24h từ lần dùng gần nhất.
  - **Input token tăng nhẹ** — API tự chèn thêm 1 system prompt mô tả format, tính phí như input token.
  - **Schema đảm bảo ≠ request đảm bảo thành công** — vẫn có **refusal** (`stop_reason: "refusal"`) và
    **truncation** (`stop_reason: "max_tokens"`) khiến response không khớp schema. Luôn check
    `stop_reason` trước khi giả định response parse được.
  - **Không kết hợp được với message prefilling** — 2 pattern xung khắc trong cùng 1 request.

## Important APIs / Parameters
| Name | Type | Default | Notes |
|------|------|---------|-------|
| `system` | str hoặc list[dict] | — | Top-level param của `messages.create()`, không nằm trong `messages` — thiết lập "hợp đồng hành vi" cho session |
| `output_config.format` | dict | — | `{"type": "json_schema", "schema": {...}}` — ràng buộc response cuối cùng khớp JSON schema (constrained decoding); thay cho `output_format` cũ đã deprecated |
| `strict` (trên tool definition) | bool | `False` | Set `True` để validate `tool_use.input` khớp `input_schema` trước khi code tự viết chạy — schema cần `additionalProperties: false` + `required` đầy đủ |

## Gotchas
- [ ] Đừng phản xạ "thêm chữ vào prompt" khi output sai — luôn **chẩn đoán loại lỗi trước** rồi mới
  thêm đúng 1 trong 4 kỹ thuật tương ứng. Prompt dài dần qua mỗi lần sửa là dấu hiệu đang bỏ qua bước
  chẩn đoán này.
- [ ] Ví dụ (few-shot) luôn đặt **sau** phần instruction/guideline chính trong prompt, và tên tag XML
  phải **mô tả cụ thể** (vd `<athlete_information>`), không dùng tên chung chung như `<data>`.
- [ ] Structured outputs (`output_config.format`, `strict: true`) không tương thích với **message
  prefilling** — chỉ chọn 1 trong 2 pattern cho cùng 1 request.
- [ ] Structured outputs đảm bảo **schema** khớp, không đảm bảo **request thành công** — vẫn phải check
  `stop_reason` vì có thể là `refusal` (model từ chối) hoặc `max_tokens` (bị cắt giữa chừng).
- [ ] `output_format` (param cũ) đã deprecated — dùng `output_config: {"format": {...}}` trên
  `messages.create()`.

## Exam Tips
- Đề thi có thể cho 1 mô tả failure mode (vd "output đúng nội dung nhưng sai hình dạng") và hỏi kỹ
  thuật nào cần thêm — map đúng theo bảng chẩn đoán 4 dòng ở trên, không chọn theo cảm tính.
- Thứ tự áp dụng 4 kỹ thuật chuẩn khi xây prompt từ đầu: **Clear & Direct → Specific → XML Tags →
  Examples**; nhưng khi *chẩn đoán* 1 prompt đã lỗi, chọn kỹ thuật theo đúng failure mode quan sát
  được, không nhất thiết theo thứ tự này.
- Phân biệt rõ **prompt-level output constraint** (yêu cầu bằng lời, có thể trượt ở edge case chưa
  test) vs **Structured Outputs ở API level** (`output_config.format`, `strict: true` — ràng buộc bằng
  constrained decoding, không thể sinh ra output vi phạm schema).
- Structured Outputs không "miễn phí" — biết đánh đổi: latency ở request đầu trên schema mới (cache
  24h), input token tăng nhẹ, và vẫn phải check `stop_reason` (`refusal`/`max_tokens`).

## Code Snippets
```python
# JSON outputs — ép response cuối cùng khớp JSON schema (constrained decoding)
response = client.messages.create(
    model=MODEL_DEV,
    max_tokens=300,
    messages=[{"role": "user", "content": "Extract info: John Smith (john@example.com), Enterprise plan."}],
    output_config={
        "format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "plan": {"type": "string"},
                },
                "required": ["name", "email", "plan"],
                "additionalProperties": False,
            },
        }
    },
)

# Strict tool use — ép argument truyền vào tool khớp input_schema trước khi code chạy
BOOK_FLIGHT_TOOL = {
    "name": "book_flight",
    "description": "Book a flight to a destination",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "destination": {"type": "string"},
            "date": {"type": "string", "format": "date"},
            "passengers": {"type": "integer", "enum": [1, 2, 3, 4, 5, 6, 7, 8]},
        },
        "required": ["destination", "date", "passengers"],
        "additionalProperties": False,
    },
}
```

## Questions / Unclear Points
- ?
