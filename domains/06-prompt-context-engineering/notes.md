# Domain 6: Prompt and Context Engineering (11.0%)

## Skills trong domain này (theo exam blueprint)
- [x] Context Engineering (3.8%) — context window management, prevention of context drift/bloat (tool output pruning, compaction), context isolation qua subagents/multi-step workflows
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
- **Worked example 2 (edge case làm vỡ parser)**: extract order total từ email khách hàng để billing
  service charge tiền.
  - **Prompt happy-path** (chỉ lo đường thẳng, chưa có rule cho variant):
    ```
    Extract the order total from the email. Return JSON: {"amount": <number>, "currency": <string>}.

    <email>{{email_body}}</email>
    ```
    Parser downstream: `float(data["amount"])`.
  - **Test pass hết** trên input sạch: `"Total: $49.00"` → `{"amount": 49.00, "currency": "USD"}`;
    `"120 EUR"`, `"£15.50"`... đều OK.
  - **Vỡ trên input lạ chưa test**:
    - **Thousands separator**: `"Total: $1,299.00"` → Claude trả `{"amount": "1,299.00"}` (string có
      dấu phẩy) → `float("1,299.00")` ném `ValueError`, request crash.
    - **Không có amount** (email xác nhận giao hàng, không có giá): prompt chưa nói làm gì khi thiếu
      data → Claude lúc thì bịa `{"amount": 0}` (charge nhầm), lúc thì `{"amount": null}` (vỡ ở dòng
      parser khác), không nhất quán qua các lần chạy.
    - **Refund/credit**: `"We've credited you $30.00"` → Claude trả `{"amount": 30.00}` không dấu →
      billing charge $30 thay vì hoàn tiền.
  - **Chẩn đoán**: đúng hàng cuối bảng — output sạch với input đã test, vỡ với variant → thiếu
    **constraint bao phủ variant đó** (không phải lỗi wording).
  - **The fix — a constraint covering each variant** (KHÔNG phải "reword the instruction" — mà là
    **gọi tên từng variant** ra trong constraint):
    ```
    Extract the order total from the email.

    Return ONLY this JSON, no preamble:
    {"amount": <number>, "currency": <3-letter ISO code>, "direction": "charge" | "refund"}

    Rules:
    - amount: a plain number, no thousands separators, no currency symbol. Always positive.
    - If the email describes a credit/refund, set direction to "refund", else "charge".
    - If no monetary amount is present, return {"amount": null, "currency": null, "direction": null}.

    <email>{{email_body}}</email>
    ```
    Mỗi rule vá đúng 1 variant đã làm vỡ parser ở trên:
    - *"no thousands separators, no currency symbol, always positive"* → chặn case `"$1,299.00"` trả
      string, và case refund trả số không dấu.
    - *field `direction`* → tách bạch charge vs refund ngay trong shape, billing service không đoán mò.
    - *"If no monetary amount is present → {…null}"* → định nghĩa rõ **làm gì khi thiếu data**, hết
      tình trạng lúc bịa `0` lúc trả `null`.
  - Hoặc chuyển hẳn sang **structured outputs** với JSON schema (`amount` là `number` + `minimum: 0`,
    `direction` là `enum`, cho phép `null` tường minh) → string `"1,299.00"` **không thể được sinh ra**
    ngay từ lúc decode.
- **Khi nào stack đủ 4 kỹ thuật / khi nào đơn giản hoá / khi nào dừng lại chẩn đoán**:
  - **Stack cả 4 kỹ thuật**: task có output contract rõ ràng, nhiều edge case có thể minh hoạ bằng ví dụ.
  - **Đơn giản hoá**: task đơn giản (vd "summarize this paragraph") không cần few-shot + output schema
    — thêm cả 4 kỹ thuật vào task đơn giản là thừa, chỉ làm prompt dài không cần thiết.
  - **Dừng lại để chẩn đoán**: nếu đã re-prompt **5 lần** mà output vẫn sai và prompt cứ dài thêm mỗi
    lần → đó là dấu hiệu đang bỏ qua bước chẩn đoán, chỉ thêm chữ chứ không thêm đúng kỹ thuật.
- **System prompt** = "hợp đồng hành vi" cho toàn bộ session — viết 1 lần, coi là lớp instruction bền
  vững (persistent instruction layer), định nghĩa role, output format, và các rule không được đổi giữa
  các turn/conversation.

### When to reach for each technique — chi tiết từng kỹ thuật

- **System prompts** — mang "behavioral contract" cho **toàn bộ session**. Viết 1 lần, coi là
  *persistent instruction layer*. Định nghĩa: role của Claude, output format, và mọi rule **không được
  đổi giữa các conversation**.
- **XML tags** — dùng khi prompt **trộn lẫn input với instruction**. Ví dụ điển hình: yêu cầu Claude
  debug code dựa trên documentation cung cấp kèm — không có tag thì code và docs **nhìn giống hệt nhau**
  với Claude. Bọc bằng tên tag **mô tả cụ thể** như `<my_code>` và `<docs>` → ranh giới rõ ràng. Không
  cần dùng tên tag XML "chính thức"; tên tự đặt khớp với nội dung là tốt nhất.
- **Few-shot examples** — hữu ích vì **cho xem (show) thay vì chỉ mô tả (tell)**. Thay vì cố tả bằng
  lời format mong muốn, đưa **1 cặp input–output đúng** và để Claude tự suy ra pattern. Cách dùng: bọc
  ví dụ bằng **cấu trúc XML nhất quán** (vd `<sample_input>` / `<ideal_output>`) để ranh giới ví dụ ↔
  prompt rõ ràng. Có thể lấy luôn ví dụ từ **các output đạt điểm cao nhất trong eval** thay vì tự viết
  mới.
- **Output constraints** — là **tuyến phòng thủ cuối** trước khi response tới parser. Chỉ định **chính
  xác** thứ cần: field name, type, giới hạn độ dài, có/không preamble, và **làm gì khi thiếu data**.
  Khi format bắt buộc phải machine-readable → dùng **structured output features** (xem mục dưới).

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

### Extended Thinking — bật reasoning, hiệu chỉnh effort, và đọc lại kết quả cho đúng
- **Prompting techniques** định hình *cái Claude tạo ra*. **Extended thinking** định hình *lượng công
  việc Claude làm trước khi trả lời*. Bật lên → model viết ra reasoning từng bước trước, rồi mới đưa
  ra câu trả lời cuối. Việc của bạn: quyết định khi nào phần công sức thêm đó đáng chi phí, và xử lý
  đúng phần reasoning mà API trả về.
- **Extended thinking làm gì**: model "nghĩ thành tiếng" trước khi response. Reasoning về dưới dạng 1
  **thinking block** riêng, đứng ngay **trước** block chứa câu trả lời thật. Trên các model mới nhất,
  **nội dung** thinking block bị **ẩn mặc định** — phải yêu cầu 1 bản tóm tắt đọc được qua **display
  setting** mới thấy.
- **Reasoning trên model hiện hành là adaptive**: bạn *bật* nó bằng param `thinking` (ở đâu chưa bật
  sẵn mặc định), rồi **model tự quyết** mỗi request cần bao nhiêu reasoning. Bạn tinh chỉnh độ sâu
  bằng **`effort` setting**, không phải bằng token budget cố định.
  - `budget_tokens` (cách điều khiển cũ) đã **deprecated**, và trên các thế hệ model mới nhất **trả
    lỗi 400**.
- **Reasoning không miễn phí**: thinking token **tính phí bằng output token**. Chạy task đơn giản ở
  effort cao = trả tiền cho độ chính xác không cần tới. Nguyên tắc giống hệt chọn tool: **match tool
  với task** — đừng mặc định bật extended thinking, chỉ dùng có chiến lược ở nơi cần.

**Khi nào dùng extended thinking**

| Task shape | Gọi extended thinking? | Lý do |
|---|---|---|
| Multi-step reasoning giữ nhiều constraint cùng lúc: suy diễn toán học, bài logic multi-hop, lập kế hoạch chuỗi hành động phụ thuộc nhau | **Bật**, chọn `effort` khớp độ sâu bài toán | Pass reasoning là nơi model xử lý các dependency mà nếu không nó sẽ bỏ qua |
| Task máy móc / tra cứu: classification, format conversion, extract 1 field, câu hỏi factual ngắn | **Tắt** | Extended thinking không cải thiện câu trả lời, chỉ trả thêm token vô ích. Bare prompt + output constraint mới là đúng tool |
| Agentic loop nơi model lập kế hoạch qua nhiều tool call | **Bật**, và budget cho bước *planning* thay vì cho từng call | Reasoning trước khi lập plan giảm việc chọn nhầm tool ở downstream. Chú ý carry-back rule bên dưới |

**Carry-back rule: thinking block phải trả về API nguyên vẹn**
- Khi extended thinking bật **và** conversation có dùng **tool**: mỗi thinking block nhận được **phải
  gửi lại API y hệt như lúc nhận** ở turn kế tiếp.
- Mỗi block kèm 1 **signature** xác nhận reasoning không bị chỉnh sửa. Nếu bạn **sửa / tóm tắt / bỏ**
  nó → signature không khớp → **API reject request**.
- **Redacted thinking block** hoạt động y vậy: nội dung được mã hoá, không dành cho người đọc, nhưng
  vẫn phải trả lại **nguyên vẹn**.
- Đây là **yêu cầu cấu trúc**, không phải lựa chọn prompting. Lỗi hay gặp nhất: **strip thinking
  block để tiết kiệm context** → làm hỏng request kế tiếp. Nếu lo context phình to vì reasoning tích
  luỹ → fix bằng **context engineering** (phần sau của module này), không phải bằng cách xoá block.
- **Forward pointer**: bài này bật reasoning + hiệu chỉnh `effort`; **không** đụng tới **model
  selection**. Chọn *model nào để chạy* (khác với *có bật reasoning hay không*) học ở module **MSO
  Foundations** (đứng trước module này).

| | |
|---|---|
| **Handles well** | Task reasoning/planning khó, nơi câu trả lời sai thì đắt và token thêm mua được độ chính xác |
| **Adds cost / complexity** | Carry-back requirement trong tool-use loop, và 1 `effort` setting giờ bạn phải tự hiệu chỉnh |
| **Use a different approach** | Với classification / extraction / format: prompt ràng buộc tốt vừa rẻ hơn vừa chính xác ngang |

### Tool Schemas — cái Claude đọc để **chọn đúng tool**, và tool-use loop
- **Chuyển góc nhìn**: các kỹ thuật trước định hình *ngôn ngữ Claude sinh ra*. Với tool-use, bạn
  không lái ngôn ngữ nữa — bạn **giao 1 tập action** và tin Claude chọn đúng cái. Lựa chọn đó gần như
  hoàn toàn do **schema bạn viết** quyết định.
- **Hiểu lầm phổ biến nhất**: Claude **không chạy tool**. Claude đọc tool definition → quyết định tool
  nào hợp → trả về cho app tên tool + input. **App bạn** execute tool, lấy kết quả, gửi lại; rồi Claude
  dùng kết quả đó để tiếp tục. Ranh giới "Claude sở hữu gì / code bạn sở hữu gì" là nơi phần lớn bug
  tool-use nằm.
- **6 bước của loop**: (1) Define schema → (2) Send message → (3) Claude trả `tool_use` block →
  (4) **App execute tool** → (5) App trả `tool_result` → (6) Claude tiếp tục. **Loop không tự động** —
  bước 4 & 5 là việc code bạn phải làm. Nếu miss **có hệ thống** (systematic) → lỗi nằm ở **bước 1
  (schema definition)**, không phải ở prompt.

**Message block structure trong 1 tool-use conversation**
- Conversation là **list các block có cấu trúc**, không phải plain text. Mỗi assistant/user turn là 1
  list block. 4 loại block:

| Block type | Role | Chứa gì | Quy tắc bắt buộc |
|---|---|---|---|
| `text` | Assistant | Prose của Claude | Claude có thể trả `text` **cùng turn** với `tool_use`. Khi append turn đó vào history, **giữ nguyên cả content array** (gồm cả text block). Bỏ text block → hỏng context cho turn sau |
| `tool_use` | Assistant | Tên tool, 1 **unique ID**, input arguments | Mỗi `tool_use` phải được đáp bằng 1 `tool_result` ở **user turn ngay kế tiếp**, mang **đúng ID** đó. Thiếu → API reject request kế |
| `tool_result` | User | `tool_use_id` khớp, nội dung kết quả, cờ `is_error: true` khi tool fail | `tool_use_id` phải khớp **chính xác** với `tool_use` gốc — Claude dùng ID này để nối kết quả về đúng call (quan trọng khi 1 turn phát nhiều tool call và kết quả về không cùng thứ tự) |
| `thinking` | Assistant (chỉ khi extended thinking bật) | Reasoning nội bộ | Phải gửi lại API **nguyên vẹn** ở turn sau. Signature xác nhận reasoning chưa bị sửa — mọi edit/summary phá signature → API reject. Redacted thinking: cùng quy tắc, trả lại y như nhận dù nội dung mã hoá (xem [carry-back rule] ở mục Extended Thinking) |

- **Invariant cốt lõi**: mọi `tool_use` block từ 1 assistant turn **phải** có `tool_result` tương ứng
  ở **user turn ngay sau đó**. Thiếu, hoặc `tool_result` xuất hiện ở turn muộn hơn thay vì turn ngay
  kế → **API validation error**. Đây là **cấu trúc**, không sửa được bằng cách chỉnh prompt.

**Schema anatomy — 3 phần Claude đọc để ra quyết định chọn tool**
- **`name`** — identifier ngắn, **cụ thể**. `get_account_balance` hữu ích hơn `get_data`.
- **`description`** — phần **quyết định** chọn đúng/sai tool. Luôn viết **2 phần: khi nào dùng + khi
  nào KHÔNG dùng**. "use this to find information" → chọn sai vì không phân biệt được với bất kỳ tool
  retrieve nào khác. "retrieve the current balance for a specific account ID, do not use for
  transaction history" → cho Claude 1 **exclusion condition** để làm việc.
- **`input_schema`** — định nghĩa params bằng **JSON Schema**. Mark `required` khi Claude **bắt buộc**
  phải có để gọi đúng; để optional khi tool chạy được mà không cần. **Overlapping parameter types
  giữa các tool là nguồn gây sai-tool phổ biến nhất.**

**Decision table — 5 lựa chọn thiết kế schema**

| Quyết định | Cách xử lý | Vì sao quan trọng |
|---|---|---|
| **Subtask dependency** | Output tool A feed vào tool B → **chạy tuần tự** (call B không dựng được cho tới khi có kết quả A) → model hoá thành **turn riêng biệt**. Subtask độc lập → để Claude phát nhiều `tool_use` trong **1 turn**, code chạy song song | Đây là quyết định **duy nhất** đổi cách thiết kế schema. Model hiện hành **mặc định parallel** khi call độc lập. Dùng `disable_parallel_tool_use: true` để ép 1 call/turn khi cần |
| **Required fields** | Mark `required` **chỉ khi** call vô nghĩa nếu thiếu. Đặt trong mảng `required` của input schema | Mark tất cả là required → ép Claude **bịa giá trị** cho field nó không có cơ sở điền |
| **Optional fields** | Param có default hợp lý, hoặc absence mang ý nghĩa → **để ngoài** `required`, cho default trong function signature | Optional field cho Claude **bỏ qua** thông tin nó không có, thay vì đoán |
| **Description length** | **3–4 câu/tool**: tool làm gì, khi nào Claude nên với tới, trả về gì. Kèm ví dụ input hợp lệ khi format quan trọng | Quá ngắn → Claude đoán vì thiếu tín hiệu phân biệt. Quá dài → trigger condition bị chôn dưới chi tiết Claude không đọc lúc quyết định |
| **Overlapping parameter types** | 2 tool nhận cùng shape param → thêm câu **disambiguating** vào mỗi description, nêu rõ domain/trigger mà tool đó nhắm tới | Claude route theo **name + description**, param type chỉ là tín hiệu phụ. Signature giống nhau → route sụp về **chỉ còn description** |

**Worked example — schema gây chọn sai tool và cách fix** *(ví dụ minh hoạ, không phải hệ production thật)*
- Dev đăng ký 2 tool: `search_knowledge_base` và `get_cached_result`. Tên khác nhau nhưng **cả 2
  description đều mở đầu "use this to find information"** → Claude chọn sai thường xuyên trên input mơ hồ.
- **Nguyên nhân**: 2 description **nhìn giống hệt** tại điểm ra quyết định. Tên tool phân biệt không đủ
  — Claude cân description nặng hơn.
- **Fix** = thêm 1 câu exclusion/điều kiện cho mỗi cái:
  - `search_knowledge_base`: *"Use this to search the knowledge base when the user asks a question
    that requires looking up current information. Do not use this if the result of a prior search in
    this session already covers the question."*
  - `get_cached_result`: *"Use this to retrieve a result that was already fetched during this session.
    Only use this if search_knowledge_base was called earlier in this conversation for the same query."*
- **Cảnh báo**: exclusion condition dựa trên **toàn bộ conversation history được truyền mỗi request**.
  Nếu turn trước bị truncate/drop → Claude không đánh giá được → **exclusion logic fail âm thầm**.
- **Poor fit**: 2 tool làm việc na ná nhau, cần description dài mãi để tách → **gộp thành 1 tool có
  param `type`** thay vì cố phân biệt.

**MCP — thay thế cho việc tự viết schema thủ công**
- Mọi thứ trên giả định **bạn tự viết** name/description/input_schema + function execute. **MCP
  (Model Context Protocol)** = lớp giao tiếp chuẩn hoá, đưa tool definition + execution **ra khỏi
  code app**, vào **dedicated server**. Có MCP server cho service bạn cần → connect thẳng, khỏi tự build.
- **Ví dụ GitHub**: tự build đầy đủ = viết schema + execute function cho từng repo/PR/issue/project và
  maintain khi API GitHub đổi. MCP server GitHub **đã làm sẵn** → app connect, nhận full tool list,
  Claude chọn bằng **đúng cơ chế description-based routing** ở trên. Cơ chế y hệt — chỉ khác **ai viết
  và ai sở hữu** tool definition.
- **Loop không đổi khi thêm MCP**: Claude vẫn phát `tool_use`, app vẫn execute + trả `tool_result`,
  quy tắc pairing block vẫn áp dụng. Khác **duy nhất ở bước setup**: client gửi `ListToolsRequest` →
  server trả full tool list → pass vào Claude. Với Claude, các tool đó **không phân biệt được** với
  tool bạn tự viết.
- **Chi phí context**: MCP server **thêm tool definition vào context window kể cả khi không dùng** ở
  turn hiện tại. Connect nhiều server cùng lúc → tool definition ăn budget **trước cả message đầu
  tiên**. Kỷ luật: chỉ register server đang thực sự dùng.
- **API MCP Connector** — kiểm soát chi phí load qua object `mcp_toolset` trong mảng `tools`:
  - `mcp_toolset` mang block `default_config` (áp cho mọi tool trên server) + `configs` keyed theo tên
    tool để override từng tool.
  - `defer_loading` (bool, trong `default_config` hoặc per-tool) — **hoãn load** tool definition tới
    khi model cần → giảm chi phí context upfront khi server có tool list lớn.
  - `enabled` (bool) — bật/tắt từng tool → register server nhưng chỉ expose tool muốn model thấy
    (allowlist/denylist per server).
  - Cần **beta header `mcp-client-2025-11-20`** trên request, nếu không `mcp_toolset` config **không
    áp dụng**.
- **2 transport**: **local server → stdio** (app spawn server làm subprocess, giao tiếp qua stdin/
  stdout). **Remote server → Streamable HTTP** (POST cho client→server, optional GET-based SSE stream
  cho server→client). SSE-only cũ đã **deprecated** — integration mới dùng Streamable HTTP.
- **Ràng buộc quan trọng**: **API MCP Connector chỉ hỗ trợ remote (HTTP) server.** stdio server cần
  **Claude Desktop hoặc Claude Code** làm client — không connect thẳng qua API được, phải tự quản MCP
  client connection qua SDK.
- **Khi nào dùng gì**:
  - **MCP**: có server được maintain tốt, phủ đúng operation bạn cần → tự viết schema chỉ thêm việc,
    không thêm capability.
  - **Tự viết schema**: không có MCP server phủ use case, HOẶC cần kiểm soát chính xác **description
    quality** (không phải scope — scope thì `MCPToolset` allowlist/denylist làm được).
  - **Cả hai**: connect MCP để có **breadth**, rồi apply description-tuning cho các tool bạn thực sự
    route tới. Narrow tool set (allowlist) và sharpen description là **2 lever riêng biệt** — dùng cả 2.

### Model Selection & Context Window Budget — nền của mọi quyết định context engineering
- **1 lựa chọn sớm nhất**: model nào chạy workload. Model quyết định **sàn** về cost + latency +
  capability mà mọi quyết định sau đó chỉ xoay trong phạm vi đó.
- **4 tier hiện hành**: **Fable** (mạnh nhất — reasoning phức tạp, advanced coding, research synthesis,
  agentic workflow cần intelligence tối đa) → **Opus** (việc nặng vượt envelope của Sonnet) →
  **Sonnet** (default cân bằng cho hầu hết production workload) → **Haiku** (tối ưu speed + cost cho
  task nằm trong capability envelope của nó). Luôn xác nhận lineup + model ID với `platform.claude.com/docs`
  tại thời điểm build.
- **Quy tắc di chuyển model = phải là quyết định có đo lường (measured), không phải cảm tính**:
  - Bắt đầu ở **Sonnet**.
  - Lên **Opus** *chỉ khi* eval set cho thấy Sonnet không đạt chất lượng cần.
  - Xuống **Haiku** *chỉ khi* eval set cho thấy mức regression chất lượng **chấp nhận được cho task
    đó** — không phải chỉ vì muốn tiết kiệm cost.
- **Phân biệt với domain này**: *chọn model nào* học ở module **MSO (Model Selection & Optimization)**.
  Domain 06 lo phần *sau khi model đã chốt*: quản lý **context window**. (Đây cũng là phân biệt với
  Extended Thinking: bật reasoning ≠ chọn model.)

**Context window không phải tài nguyên miễn phí**
- Context window = toàn bộ text model nhận vào 1 lúc: prompt + conversation so far + **mọi tool result**.
  Mỗi tool result Claude trả về **được append vào context window và nằm đó tới hết session**.
- Single-turn: không thấy. Multi-step agent chạy 10–20 tool call: window đầy nhanh. Đầy rồi → agent
  hoặc **compact** (mất chi tiết) hoặc **stall** trước khi xong task.
- **API xử lý thế nào khi vượt** (không im lặng cắt content cũ):
  - Request **đã lớn hơn** context window → Messages API **reject bằng validation error trước khi
    generate**.
  - Request vừa, nhưng generation **chạm trần giữa chừng** → model hiện hành trả về **phần output đã
    sinh** kèm `stop_reason: "model_context_window_exceeded"`.
  - Muốn session chạy tiếp quá giới hạn → **app tự phải** trim / summarize history **trước** request kế.
- **Vì sao dev không thấy, production mới vỡ**: test input nhỏ + session ngắn → window hiếm khi đầy.
  Production: tool output thường **dài gấp 3–5 lần** test fixture, session nhiều turn hơn → window đầy
  ở **turn 8** thay vì turn 50. Chi phí của việc không plan trước = **production outage**.

**4 strategy giữ session trong budget** (mỗi token trong window = tốn tiền input + tăng latency; session
dài cộng dồn cả 2)

| Strategy | Làm gì | Khi nào dùng | Mất continuity gì |
|---|---|---|---|
| **Pruning** (jump back) | Quay lại 1 message cũ, tiếp tục từ đó, **xoá phần hội thoại sau điểm rewind** | Sau khi Claude đi vào hướng vô ích, hoặc tích luỹ debug qua lại không giúp task tiếp theo | Toàn bộ việc làm sau điểm rewind mất. Claude học được gì trong đoạn đó phải **học lại** |
| **Compaction** (`/compact` ở Claude Code; **server-side compaction (beta)** ở API — platform tự làm khi config trên request; manual summarization là bản client-side thay thế) | Tóm tắt history thành bản cô đọng giữ key info Claude đã học. Summary tốn ít token hơn các turn gốc | Session gần trần nhưng **muốn làm tiếp cùng feature** với kiến thức Claude đã build | Chi tiết có thể mất trong lúc tóm tắt. Gì không nằm trong summary → Claude không còn thấy |
| **Clearing** (`/clear`; new session ở API) | Bắt đầu conversation mới, context rỗng. Không gì carry forward | Task tiếp theo **hoàn toàn khác**, context cũ chỉ gây bias/confusion | Toàn bộ context session mất. Gì cần nhớ xuyên session phải để ở **nơi persistent** (vd `CLAUDE.md`) |
| **Subagent Handoffs** | Spawn subagent trong **context window riêng biệt**, chỉ đưa task description + system prompt nó cần. Subagent làm việc → trả về **1 summary** | Subtask **đủ tự chứa để delegate**, đặc biệt việc exploration mà hành trình làm rối main context nhưng kết quả thì ngắn | Visibility vào **cách** subagent đi tới kết luận. Các bước trung gian bị bỏ cùng context của subagent |

**2 lever thêm — không quản *cái gì vào* window mà giảm *chi phí cho cái đã ở trong***
- **Prompt caching**: lưu lại phần xử lý đã làm trên 1 **prefix ổn định** của request → request sau
  gửi content **giống hệt tới điểm đó** dùng lại thay vì xử lý lại.
  - Request đầu **ghi** prefix vào cache; request sau trả **1 phần nhỏ** cost gốc.
  - Ứng viên mạnh nhất: phần **hiếm đổi qua các turn** — system prompt dài, tool definition set lớn,
    reference document query lặp lại.
  - Bật bằng cách đánh dấu **cache breakpoint**: field `cache_control` type `ephemeral` trên **block
    cuối cùng** muốn cache. Tối đa **4 breakpoint**.
  - Multi-turn session có system prompt + tool schema ổn định → cache prefix đó 1 lần rồi reuse xuyên
    turn = **giảm cost đòn bẩy cao nhất** có sẵn.
- **Token counting**: đo **context pressure trước khi** request đi ra, thay vì sau khi nó fail.
  - Endpoint `count_tokens` nhận **cùng request body** như `messages` call, trả **token count** mà
    **không chạy inference**.
  - Dùng lúc dev: verify giả định context budget đúng với **tool output thật**, không chỉ test fixture.
  - Dùng ở production: **gate** request sẽ vượt window **trước khi** nó error.

**Compaction sâu hơn — cái gì được giữ tuỳ cách viết summarizer**
- `/compact` ở Claude Code: tool tự quyết cái gì vào summary.
- API: strategy chính documented = **server-side compaction (beta)** — platform tóm tắt cho bạn khi
  được config trên request.
- **Manual compaction** ở API session: **bạn tự viết prompt summarizer**. Prompt đó quyết định agent
  biết gì ở các turn sau.
  - Yếu: *"summarize the conversation so far"*
  - Mạnh: *"summarize the conversation, preserving all file paths modified, all decisions made, and
    any errors encountered and their resolutions"*
  - **Task-critical state loss vì summarizer viết sơ sài là 1 trong các nguồn failure phổ biến nhất
    của multi-session agent** — không phải edge case.

**Subagent handoffs — quản long-horizon task**
- Task quá lớn cho 1 context window → **tăng window KHÔNG phải giải pháp**. Giải pháp = **decompose**
  và chỉ pass context liên quan cho mỗi subagent.
- 1 subagent nhận: **scoped task** + **minimum context nó cần** + **kết quả các bước trước trực tiếp
  liên quan** + **tools nó cần** + **exit condition rõ ràng**. Parent agent thu kết quả.
- Pattern này giữ **per-turn cost thấp** và làm long-horizon task **tractable**.
- Như compaction/pruning, subagent handoff **thêm implementation overhead** → chỉ dùng nơi context
  cost là **ràng buộc thật**. Single-turn prompt / short workflow **không cần**.
  - **Handles well**: multi-step agent session vượt token budget, cần decompose. Thiết kế tốt nhất ở
    **giai đoạn kiến trúc**, không phải vá lúc production.
  - **Dùng cách khác**: pipeline không bao giờ gần giới hạn window. **Đo token usage thật** so với
    context limit của model **trước khi** thêm overhead quản lý.

**RAG — 3 chỗ 1 retrieval path có thể vỡ**
- **Chunking** (đơn vị context truy xuất được là gì): chia **quá nhỏ** → 1 chunk thiếu context xung
  quanh để hữu ích. Chia **quá lớn** → 1 chunk pha loãng match với text không liên quan. Default hợp
  lý: **sentence-based / section-based + 1 chút overlap**. Overlap quan trọng vì fact **vắt qua ranh
  giới** nếu không sẽ bị tách rời và khó retrieve.
- **Embedding match** (chunk nào được trả về): dùng **similarity search** → lấy content **semantically
  close**, **không phải luôn** cái chứa đúng term cần. Query 1 **identifier cụ thể** có thể **miss**
  chunk đúng nếu 1 kết quả semantically similar hơn xếp trên. → Đây là lý do đôi khi chạy **lexical
  match song song** với semantic.
- **Assembly** (ghép chunk vào prompt): chunk retrieved phải tới model **đúng cấu trúc prompt kỳ vọng**,
  nếu không model **trả lời từ memory thay vì từ text đã retrieve**.
- **Fetch-once (index) vs search-across-rounds (agentic search)**:
  - *Fetch-once*: system **reason được** — inspect được chunk nào retrieved cho 1 query, test retrieval
    trực tiếp. Chi phí = **infrastructure**: index phải build, store, **kept in sync** khi corpus đổi,
    và secure ở mọi nơi nó nằm.
  - *Search-across-rounds*: bỏ infrastructure đó + bỏ staleness (model đọc file hiện tại lúc query),
    đổi lại **tốn nhiều token + time hơn/query** và process **kém inspectable** hơn.
  - **Chọn**: corpus reference **ổn định** + lookup đơn giản → index đáng sở hữu. Corpus **đổi liên
    tục** hoặc câu hỏi **multi-step** → iterative search thường là system đơn giản hơn dù đắt hơn/query.
  - Con số performance gain của single-agent agentic search so với retrieval index là **version-pinned**
    — xác nhận với reference layer lúc build, đừng tin số trong module.

**Forward pointer**: điểm mấu chốt không phải "biết cách quản pressure" mà là **không biết pressure tồn
tại cho tới khi session vỡ**. Workload pass hết test ở dev rồi fail ở production **vì đúng 1 lý do**:
tool output to ra, session dài ra, window từng giữ 20 turn gọn giờ đầy ở turn 8. Section sau = worked
postmortem của 1 agent chạy ổn trên test fixture rồi chạm trần khi document thật chảy qua.

## Important APIs / Parameters
| Name | Type | Default | Notes |
|------|------|---------|-------|
| `system` | str hoặc list[dict] | — | Top-level param của `messages.create()`, không nằm trong `messages` — thiết lập "hợp đồng hành vi" cho session |
| `output_config.format` | dict | — | `{"type": "json_schema", "schema": {...}}` — ràng buộc response cuối cùng khớp JSON schema (constrained decoding); thay cho `output_format` cũ đã deprecated |
| `strict` (trên tool definition) | bool | `False` | Set `True` để validate `tool_use.input` khớp `input_schema` trước khi code tự viết chạy — schema cần `additionalProperties: false` + `required` đầy đủ |
| `thinking` | dict | tắt (trừ model bật sẵn) | Bật extended thinking. Trên model hiện hành reasoning là adaptive — model tự quyết lượng reasoning |
| `effort` | str (`low`/`medium`/`high`...) | — | Tinh chỉnh độ sâu reasoning. Thay cho `budget_tokens` cũ |
| `budget_tokens` | int | — | **Deprecated** — trên model mới nhất trả **lỗi 400**. Dùng `effort` thay thế |
| tool `name` | str | — | Identifier ngắn, cụ thể (`get_account_balance` > `get_data`) |
| tool `description` | str | — | Phần quyết định routing. Viết 2 phần: **khi nào dùng + khi nào KHÔNG** (exclusion condition). 3–4 câu |
| tool `input_schema` | dict (JSON Schema) | — | Params + mảng `required`. Overlapping param types giữa tool = nguồn sai-tool phổ biến nhất |
| `disable_parallel_tool_use` | bool | `False` (model mặc định parallel khi call độc lập) | Set `True` ép 1 tool call/turn — dùng khi có dependency thật giữa các call |
| `is_error` (trên `tool_result`) | bool | `False` | Set `True` khi tool execute fail, để Claude biết mà xử lý |
| `tool_use_id` (trên `tool_result`) | str | — | Phải khớp **chính xác** ID của `tool_use` gốc; `tool_result` phải ở user turn **ngay sau** |
| `mcp_toolset` | dict (trong mảng `tools`) | — | API MCP Connector. Có `default_config` + `configs` (keyed theo tên tool) |
| `defer_loading` | bool | `False` | Trong `mcp_toolset` — hoãn load tool definition tới khi model cần, giảm context upfront |
| `enabled` (trong `mcp_toolset`) | bool | `True` | Bật/tắt từng MCP tool — register server nhưng chỉ expose tool cần |
| beta header `mcp-client-2025-11-20` | header | — | Bắt buộc để `mcp_toolset` config có hiệu lực |
| `cache_control` | dict | — | `{"type": "ephemeral"}` đặt trên **block cuối** muốn cache. Tối đa **4 breakpoint**/request. Cache cho prefix ổn định (system prompt dài, tool set, reference doc) |
| `client.messages.count_tokens(...)` | method | — | Nhận **cùng request body** như `messages.create`, trả token count **không chạy inference**. Gate request trước khi vượt window |
| `stop_reason: "model_context_window_exceeded"` | str | — | Generation chạm trần window giữa chừng → trả phần output đã sinh. **Không** im lặng truncate content cũ |
| server-side compaction | beta strategy (API) | — | Platform tự tóm tắt conversation khi config trên request. Manual summarization = bản client-side thay thế (bạn tự viết prompt summarizer) |

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
- [ ] Extended thinking: **KHÔNG** được strip/sửa/tóm tắt thinking block trong tool-use loop —
  signature không khớp → API reject. Bỏ block để "tiết kiệm context" là lỗi kinh điển.
- [ ] Thinking token tính phí **bằng output token** — bật extended thinking cho task máy móc
  (classification/extract) là trả tiền thừa, không cải thiện gì.
- [ ] `budget_tokens` deprecated, trả **lỗi 400** trên model mới nhất — hiệu chỉnh bằng `effort`.
- [ ] Nội dung thinking block **ẩn mặc định** trên model mới — phải bật qua display setting mới đọc
  được bản summary.
- [ ] Tool-use: **Claude không chạy tool**. App bạn execute (bước 4) + trả `tool_result` (bước 5) —
  loop **không tự động**. Miss có hệ thống → sửa ở **schema definition**, không phải prompt.
- [ ] Mỗi `tool_use` phải có `tool_result` khớp ID ở **user turn ngay kế tiếp** — thiếu / sai thứ tự
  / để turn muộn hơn → **API validation error**. Không fix được bằng prompt.
- [ ] Khi Claude trả `text` **cùng turn** với `tool_use` — append **cả content array** vào history,
  đừng drop text block.
- [ ] Description "use this to find information" → chọn sai tool. Luôn viết **khi nào dùng + khi nào
  KHÔNG dùng**. Overlapping param types = nguồn sai-tool #1.
- [ ] 2 tool na ná nhau + description dài mãi để tách → **gộp thành 1 tool có param `type`**.
- [ ] Exclusion condition trong description dựa vào **full conversation history mỗi request** — turn
  bị truncate → logic fail **âm thầm**.
- [ ] Mark **mọi** field là `required` → ép Claude bịa giá trị. Chỉ mark required khi call vô nghĩa
  nếu thiếu.
- [ ] Model hiện hành **mặc định parallel tool call** khi call độc lập. Có dependency thật → model
  hoá thành turn riêng, hoặc `disable_parallel_tool_use: true`.
- [ ] MCP server **ăn context window kể cả khi tool không dùng** — chỉ register server đang thực sự
  cần. Kiểm soát bằng `defer_loading` / `enabled` trong `mcp_toolset` (+ beta header `mcp-client-2025-11-20`).
- [ ] **API MCP Connector chỉ hỗ trợ remote HTTP server.** stdio (local) server cần Claude Desktop
  hoặc Claude Code làm client, không connect thẳng qua API.
- [ ] MCP transport: integration mới dùng **Streamable HTTP**; SSE-only cũ đã **deprecated**.
- [ ] Model selection: **bắt đầu ở Sonnet**. Lên Opus / xuống Haiku **chỉ khi eval set** nói vậy —
  xuống Haiku phải vì regression *chấp nhận được cho task*, KHÔNG phải chỉ để tiết kiệm cost.
- [ ] Context window vượt → API **KHÔNG im lặng cắt content cũ**: request quá to → validation error
  trước generate; chạm trần giữa chừng → `stop_reason: "model_context_window_exceeded"` + phần đã sinh.
  App tự phải trim/summarize để chạy tiếp.
- [ ] Prod tool output thường **dài gấp 3–5 lần** test fixture → window đầy ở turn 8 chứ không phải
  turn 50. Dev pass hết không có nghĩa prod an toàn — đo bằng `count_tokens` trên output THẬT.
- [ ] Manual compaction: summarizer viết sơ sài ("summarize the conversation") làm **mất task-critical
  state** — phải liệt kê rõ cái cần giữ (file paths modified, decisions, errors + resolutions).
- [ ] Task quá lớn cho context window → **decompose + subagent handoff**, KHÔNG phải "tăng window".
- [ ] `cache_control` type `ephemeral` đặt trên **block cuối** muốn cache; tối đa **4 breakpoint**.
- [ ] RAG vỡ ở 3 chỗ: **chunking** (nhỏ quá thiếu context / lớn quá pha loãng), **embedding match**
  (similarity ≠ exact term → chạy lexical match song song), **assembly** (sai cấu trúc → model trả lời
  từ memory).

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
- Extended thinking: đề có thể cho 1 task và hỏi có nên bật reasoning không — map theo bảng: multi-step
  reasoning/planning → bật + chọn `effort`; classification/extraction/format → tắt, dùng prompt ràng buộc.
- Nhớ **carry-back rule**: trong tool-use loop, thinking block (kể cả redacted) phải trả lại API
  nguyên vẹn cùng signature — đây là câu bẫy hay hỏi. Vấn đề context phình to → giải bằng context
  engineering, không phải xoá block.
- Phân biệt **enable reasoning** (bài này, param `thinking` + `effort`) vs **model selection** (module
  MSO, chọn model nào chạy) — 2 quyết định độc lập.
- Tool-use loop 6 bước: nếu đề hỏi "Claude gọi tool nhưng không có gì xảy ra / loop treo" → nguyên
  nhân là **app không execute + trả `tool_result`** (bước 4–5), không phải lỗi model.
- "Claude chọn sai tool có hệ thống" → fix ở **schema `description`** (thêm exclusion condition), KHÔNG
  phải đổi prompt, KHÔNG phải thêm câu "hãy chọn cẩn thận".
- Câu hỏi "khi nào chạy tool song song": model **mặc định parallel khi call độc lập**; chỉ tuần tự
  khi output tool này feed vào tool kia → khi đó model hoá thành **turn riêng biệt**.
- MCP không đổi tool-use loop — chỉ đổi **bước setup** (client gửi `ListToolsRequest` thay vì bạn
  register schema tự viết). Pairing rule `tool_use`↔`tool_result` vẫn nguyên.
- Bẫy MCP: (1) API MCP Connector **chỉ remote HTTP**, stdio cần Claude Desktop/Code; (2) mỗi server
  **ăn context kể cả tool không dùng** → `defer_loading` / `enabled` + beta header `mcp-client-2025-11-20`.
- Phân biệt 2 lever kiểm soát tool khi dùng MCP: **allowlist/denylist (`MCPToolset`)** = thu hẹp
  *scope*; **description tuning** = tăng *precision routing*. Dùng cả hai, không thay thế nhau.

- Model selection: đề cho tình huống "muốn giảm cost" → đáp án đúng là **chạy eval để đo regression
  trước**, KHÔNG phải "đổi sang Haiku ngay". Default luôn là **Sonnet**.
- Đề hỏi "session dài chạm giới hạn window, xử lý sao" → map theo bảng 4 strategy: cùng feature giữ
  kiến thức → **compaction**; đi nhầm hướng → **pruning**; task mới hoàn toàn → **clearing**; subtask
  tự chứa → **subagent handoff**.
- Bẫy: "tăng context window" **không bao giờ** là đáp án đúng cho long-horizon task — luôn là decompose.
- `count_tokens` = **đo trước** (không inference); `stop_reason` = **phát hiện sau**. Đề có thể hỏi
  "làm sao biết request sẽ vượt window trước khi gọi" → `count_tokens`.
- Prompt caching: nhớ **4 breakpoint tối đa**, `cache_control: {"type": "ephemeral"}`, đặt trên **prefix
  ổn định** (system prompt / tool schema), không phải phần đổi mỗi turn.
- Compaction manual: câu hỏi "vì sao agent quên file đã sửa sau khi compact" → **summarizer prompt
  under-specified**, không liệt kê state cần giữ.

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

```python
# Tool schema: name + description (2 phần: khi nào dùng / khi nào KHÔNG) + input_schema
SEARCH_KB_TOOL = {
    "name": "search_knowledge_base",
    "description": (
        "Use this to search the knowledge base when the user asks a question that "
        "requires looking up current information. "
        "Do not use this if a prior search in this session already covers the question."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],  # chỉ mark required cái mà call vô nghĩa nếu thiếu
    },
}

# Tool-use loop tối giản — app (không phải Claude) execute tool rồi trả tool_result
messages = [{"role": "user", "content": "What's our refund policy?"}]
resp = client.messages.create(model=MODEL_DEV, max_tokens=500,
                              tools=[SEARCH_KB_TOOL], messages=messages)
if resp.stop_reason == "tool_use":
    messages.append({"role": "assistant", "content": resp.content})  # giữ NGUYÊN cả content array
    tool_results = []
    for block in resp.content:
        if block.type == "tool_use":
            result = run_search(block.input["query"])  # code CỦA BẠN chạy tool
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,      # phải khớp CHÍNH XÁC id của tool_use
                "content": result,
            })
    messages.append({"role": "user", "content": tool_results})  # user turn NGAY sau
    resp = client.messages.create(model=MODEL_DEV, max_tokens=500,
                                  tools=[SEARCH_KB_TOOL], messages=messages)
```

## Questions / Unclear Points
- ?
