# Domain 1: Agents and Workflows (14.7%)

## Skills trong domain này (theo exam blueprint)
- [x] Agent Architecture (4.5%) — decision criteria workflow vs. agent, manager/supervisor hierarchies, vai trò của subagents
  - Lesson này phủ: **workflow-vs-agent decision**. CHƯA phủ: manager/supervisor hierarchies, subagent roles.
- [ ] Agent Construction with Claude (5.3%) — Claude Agent SDK, custom agent loops/harnesses, managed deployment (self-hosted vs. Anthropic-hosted), hooks cho deterministic actions
  - Lesson này phủ **về mặt khái niệm**: 3 wiring path (raw loop / Agent SDK / Managed Agents) + 4 bước wire loop. CHƯA có hands-on SDK / hooks.
- [x] Agent Patterns and Frameworks (4.9%) — tool-use loops, sub-agents, memory, context-window management, agentic frameworks (Strands, LangGraph, PydanticAI)
  - Lesson này phủ: **tool-use loop**, exit conditions, over/under-tooling. CHƯA phủ: memory, Strands / LangGraph / PydanticAI.

## Key Concepts

### Agent = multi-step tool-use loop + managed context + defined goal
- Agent **không phải** 1 thứ mới — nó là **3 mảnh đã học ghép lại**: tool schema (Claude chọn tool),
  context management (giữ window không vỡ), + 1 **loop** chạy tới khi đạt goal. Section này thêm lớp
  mà 2 topic kia không tự có: **orchestration** (bao nhiêu tool, mô tả thế nào) + **human-in-the-loop**.
- **Failure mode mới chỉ lộ khi các component chạy chung nhiều turn** — isolated single-turn test
  không bắt được:
  - routing đúng ở 1 turn bắt đầu **cộng dồn sai** qua nhiều vòng;
  - context **đầy nhanh hơn dự tính** (tool output tích lũy);
  - 1 step nhận **nhầm input** vì tool call ở turn trước cấu trúc sai.
- **Câu hỏi phải hỏi TRƯỚC dòng code đầu tiên**: *task này có thật sự cần agent không?*
  Agent mang **coordination overhead + context cost phình + nhiều bề mặt lỗi hơn** pattern đơn giản.

### Workflow hay agent — quyết định trước dòng code đầu tiên
- Sai lầm nặng nhất trong agent dev = **chọn nhầm pattern ngay từ đầu**.
  - **Agent khi workflow là đủ** → thêm behavioral complexity mà **không thêm capability**.
  - **Workflow khi cần agent** → hệ **vỡ mỗi khi user input lệch khỏi path định sẵn**.

| Chọn **workflow** khi… | Chọn **agent** khi… |
|---|---|
| Liệt kê được **chính xác các bước** bằng code | Chỉ định được **goal + tools**, KHÔNG định được path |
| Error cost thật, cần **step-level guardrail** | Path xuyên qua công việc **không enumerate trước được** |
| Cần **observability bằng tooling chuẩn** (operational logging) | Non-determinism chấp nhận được; action bị **giới hạn bởi registered toolset** |
| Input **well-constrained** vào 1 tập đã biết | User input **biến thiên khó lường** về nội dung + cấu trúc |
| Mọi lần chạy đi **cùng 1 sequence** | Task cần **creative sequencing** các tool có sẵn |

- **Progression bắt buộc**: **1 API call → workflow → agent**. Chỉ lên bậc khi pattern đơn giản hơn
  **không xử lý nổi** độ biến thiên của task. **Agent là bậc cuối, không phải mặc định.**
- Đã quyết "cần agent" = đã quyết pattern: **1 loop gọi tool, quản context, chạy tới khi đạt goal**.
  Với single-agent, pattern này **không đổi** trên cả 3 wiring path. Multi-agent (planner / executor /
  evaluator handoff qua structured artifact) = thêm design decision, học sau.

### 3 wiring path — ai chạy loop, bạn gánh gì
Khác nhau đúng **1 biến**: bao nhiêu phần runtime của agent **bạn sở hữu**. Xếp theo mức infra bạn *nhường đi*, nhiều dần.
**Chọn theo deployment + compliance constraint — KHÔNG chọn vì prototype nhanh nhất.**

| Path | Ai chạy loop | Bạn gánh gì | Chọn khi |
|---|---|---|---|
| **Raw Messages API loop** | **Code bạn** chạy từng iteration: send request → đọc `tool_use` block → execute tool → append `tool_result` | **Toàn bộ**: loop, tool execution, context management, retry, exit condition. Không có gì cho sẵn | Cần full control từng step; có ràng buộc library không đáp ứng; đang tự học loop trước khi thêm abstraction |
| **Agent SDK** | Cùng loop đó nhưng **trong process của bạn**; SDK cho sẵn cấu trúc register tool / set system prompt / iterate loop | Code bạn **vẫn tự execute tool**. Context management + parallel tool handling do SDK cấp | Muốn cấu trúc loop có sẵn nhưng vẫn in-process; workload PHI/ZDR (trên covered config) |
| **Claude Managed Agents** (public beta) | **Anthropic** chạy loop + sandbox server-side; app bạn stream event vào, nhận kết quả qua **SSE** | Định nghĩa agent **1 lần** như **versioned API resource** (model, system prompt, tools, MCP servers, skills), tham chiếu bằng **ID**; + 1 app layer gửi event & consume stream | Task chạy **lâu (phút–giờ)**; muốn **managed sandbox**; không muốn tự build loop + sandbox + tool-exec runtime |

- **Managed Agents — thôi sở hữu gì / nhận lại gì**:
  - Thôi sở hữu: iteration loop, execution sandbox, retry trong loop, tool-execution runtime,
    long-running execution management, sandbox provisioning/teardown.
  - Nhận lại: **agent-as-API-resource** (versioned), app layer stream event, **server-side stateful
    session** (Anthropic lưu, theo data-handling policy của họ), phụ thuộc tool set + execution model
    của managed sandbox, **beta surface có thể đổi giữa các release**.
- **Constraint chốt hạ cho regulated work**: Managed Agent session **stateful + lưu server-side** →
  **KHÔNG** eligible cho **Zero Data Retention (ZDR)** hay **HIPAA BAA**. Workload mang **PHI** hoặc
  dưới **ZDR requirement** → path này **bị loại thẳng**, route sang Agent SDK / raw loop trên covered
  config. **Governing constraint chọn path TRƯỚC khi convenience có tiếng nói.**
- **Progression thường gặp**: prototype **Agent SDK** local → prod **Managed Agents**. Agent definition
  **mang theo về khái niệm**, nhưng **format đổi** (SDK = code + filesystem config; Managed = versioned
  API resource) → phải **re-express**, không phải export thẳng.

### Wiring the loop — 4 bước giữ nguyên trên mọi path
1. **Register tools** — mỗi tool cùng schema structure; đăng ký để Claude biết có gì available.
2. **Set system prompt** — **scope vào đúng task của agent**. Prompt rộng → routing rộng, kém tin cậy.
   Prompt **nêu tên task cụ thể + tools dành cho nó** → hành vi nhất quán hơn.
3. **Handle tool-use loop** — dù bạn tự iterate hay SDK iterate, **code bạn execute**. Mọi `tool_use`
   Claude phát ra phải được execute + trả về trong `tool_result` block. **Mọi `tool_use` từ 1 assistant
   turn phải resolve cùng nhau** trước assistant turn kế.
4. **Define exit conditions** — loop chạy tới khi nhận **stop condition**. Không có exit condition rõ →
   agent **cứ xin thêm tool call vượt mức task cần**. Tự định nghĩa *done nghĩa là done*, **không phụ
   thuộc Claude tự nguyện dừng**.

### Loop wiring checklist (verify bất kể path nào)

| # | Item | Verify gì |
|---|---|---|
| 1 | Tools registered | Mọi tool agent có thể cần đều trong list. **Không** reference tool chưa register trong system prompt |
| 2 | System prompt scoped | Nêu task + tools có sẵn. **Không** tả tool agent không có. **Không** bỏ sót guidance scoping cho tool agent có |
| 3 | Tool-use loop implemented | Xử lý **mọi** `tool_use` block + trả 1 `tool_result` cho từng cái trước assistant turn kế. Tất cả `tool_use` từ 1 turn resolve cùng nhau |
| 4 | HITL insertion point defined | Ít nhất **1 điểm** trong loop có human-in-the-loop check |
| 5 | Exit conditions defined | Có stopping criterion rõ, **không** phụ thuộc Claude tự dừng |

### Human-in-the-loop (HITL) — chèn ở đâu
HITL checkpoint = **pause execution → route sang human review** trước khi đi tiếp.
Câu hỏi quyết định chỗ chèn: *worst-case nếu step này chạy mà KHÔNG có human check là gì?*

| Insertion point | Trigger | Risk level |
|---|---|---|
| **Trước 1 destructive tool call** | Agent sắp execute write / delete / send | **High** — irreversible, gọi sai không undo được |
| **Sau 1 planning step** | Agent đã sinh plan, sắp bắt đầu execute | **Medium** — plan sai → outcome sai dù mọi step chạy đúng |
| **Trên unexpected output** | Tool result có error flag, empty, hoặc value ngoài bound kỳ vọng | **Variable** — bắt failure mode mà retry logic không tự giải |

### Over-tooling vs under-tooling
- Routing behavior của agent bị định hình bởi **(a) tool được mô tả thế nào** + **(b) register bao nhiêu tool**.
- **Over-tooling** (phổ biến hơn ở prod): team register mọi tool "just in case" → **selection quality
  tụt khi tool surface phình**. Description trùng lặp → routing thất thường.
- **Under-tooling**: quá ít tool → agent **hallucinate 1 path** hoặc trả kết quả **incomplete**.
- **Kỷ luật**: bắt đầu bằng **tập tối thiểu** cần cho task; chỉ thêm tool khi **xác nhận 1 gap
  capability cụ thể**.

### Regulated data constraint chọn endpoint + credential TRƯỚC khi bạn wire
Data có ràng buộc đặc thù (attorney-client privilege, HIPAA, GDPR/data-residency, FedRAMP, internal
policy) → constraint đó quyết định **code gọi endpoint nào, mang credential gì, log đổ đâu** — trước
mọi quyết định về prompt/tool/memory. Dev thường không chọn surface, nhưng **viết code target endpoint
cụ thể + attach credential + config region + emit log** → phải **nêu tên governing constraint từ đầu**
(sửa client config sai *sau khi* agent đã wire đắt hơn nhiều).

| Constraint | Thường loại bỏ (trong code) | Thường qua được code review |
|---|---|---|
| **Attorney-client privilege** | Call từ consumer Claude.ai surface firm không audit end-to-end; gửi privileged content tới endpoint chưa được firm approve | Direct API/SDK từ trong app của firm, auth qua SSO, qua **firm-approved LLM gateway có full request/response logging**. Anthropic **không capture** conversation content mặc định trên direct API → **app layer tự log** về approved destination |
| **HIPAA (PHI)** | Gửi PHI tới endpoint/route **không cover bởi BAA** cho đúng config đang dùng; kể cả logging/retention path chưa scope trong cùng BAA | Direct API/SDK trên **BAA-covered config** (Anthropic provision 1 HIPAA-enabled org riêng); hoặc route qua **AWS Bedrock / GCP Vertex** trên cloud account HIPAA-eligible. BAA **không** cover Console, Workbench, beta features, consumer plans |
| **GDPR / data residency** | Route mà **region model execution không pin được trong code**; default global endpoint không chỉ định region | Route qua **Bedrock / Vertex** với **region pin trong client config** vào jurisdiction được cover. **Direct Anthropic API hiện KHÔNG có EU data residency** → dùng Bedrock/Vertex |
| **FedRAMP / government** | Endpoint không nằm trên authorized cloud ở impact level yêu cầu; dev/test hit commercial endpoint còn prod hit authorized (credential + pattern leak giữa 2) | 3 route authorized: **Claude for Government (C4G)** (FedRAMP High qua PFCS-SS), **Bedrock GovCloud** (FedRAMP High + DoD IL4/5), **Vertex AI Assured Workloads**. Claude Enterprise trên AWS Marketplace **không** FedRAMP authorized. Verify tại `trust.anthropic.com` |
| **Internal data-residency policy** | SDK client config chống lại cloud vendor **ngoài approved list** — kể cả khi năng lực kỹ thuật đủ. Procurement-level constraint loại code path trước khi engineering preference lên tiếng | Route trên **cloud vendor CIO đã clear**; build đúng SDK client + endpoint đó, không đổi giữa chừng vì route khác "trông dễ hơn" |

- **SOC 2 không thuộc phạm vi này** — nó quản *cách hệ thống được build/vận hành*, không quản *code gọi
  endpoint nào* (học ở Module 4 cùng security posture / audit).

## Important APIs / Parameters
| Name | Type | Default | Notes |
|------|------|---------|-------|
| `tools` | list[dict] | — | Top-level param của `messages.create()` — danh sách tool đã register cho agent (name + description + `input_schema`) |
| `tool_use` block | content block (assistant) | — | Claude phát ra khi muốn gọi tool; có `id`, `name`, `input`. `stop_reason == "tool_use"` báo còn tool call chờ xử lý |
| `tool_result` block | content block (user) | — | Code bạn trả về sau khi execute; `tool_use_id` phải **khớp chính xác** `id` của `tool_use`. `is_error: true` khi tool fail |
| `stop_reason` | str | — | Exit signal của loop: `"tool_use"` = còn lặp; `"end_turn"` / khác = agent đã trả lời cuối |
| Agent SDK | library | — | Chạy loop **in-process**; cấp sẵn register tool / iterate / context management; **bạn vẫn tự execute tool** |
| Managed Agents | hosted (public beta) | — | Anthropic chạy loop + sandbox; agent = **versioned API resource** (ref bằng ID); event/kết quả qua **SSE**; session stateful server-side → **không** ZDR/HIPAA-BAA |

## Gotchas
- [ ] Dùng **agent khi workflow là đủ** → thêm complexity mà không thêm capability. Ngược lại: workflow khi cần agent → vỡ khi input lệch path.
- [ ] **Managed Agents KHÔNG eligible ZDR / HIPAA BAA** (session stateful, lưu server-side) — PHI/ZDR workload phải dùng Agent SDK / raw loop trên covered config.
- [ ] **Không chọn wiring path vì prototype nhanh nhất** — chọn theo deployment + compliance constraint.
- [ ] **Exit condition không được phụ thuộc Claude tự nguyện dừng** — phải có `max_turns` / stop_reason check trong code, nếu không agent xin tool call vô hạn.
- [ ] **Mọi `tool_use` từ 1 assistant turn phải resolve cùng nhau** — trả đủ `tool_result` cho từng `tool_use_id` trước khi gọi API lần kế.
- [ ] **Direct Anthropic API hiện không có EU data residency** — GDPR residency requirement → phải qua Bedrock/Vertex với region pin.
- [ ] Prototype Agent SDK → prod Managed Agents: agent definition **re-express**, không export thẳng (format khác nhau).
- [ ] Over-tooling là failure phổ biến hơn under-tooling ở prod — bắt đầu tập tool tối thiểu.

## Exam Tips
- Câu hỏi "workflow hay agent": tìm tín hiệu **"enumerate được các bước / input well-constrained / cùng 1 sequence mỗi lần"** → **workflow**. "Goal + tools nhưng không định được path / input biến thiên" → **agent**.
- "Ai chạy loop?" → **Raw loop = code bạn**; **Agent SDK = code bạn, in-process, SDK cho cấu trúc**; **Managed Agents = Anthropic chạy server-side**.
- Câu có **PHI / ZDR** + hỏi chọn path → loại **Managed Agents** ngay. Câu có **EU data residency** → loại **direct Anthropic API**, chọn Bedrock/Vertex.
- **Compliance constraint chọn endpoint + credential TRƯỚC** mọi quyết định prompt/tool/memory.
- HITL: chèn ở đâu = trả lời câu *"worst-case nếu step này chạy không có human check?"* → destructive call = High = chèn trước.
- Progression: **1 API call → workflow → agent**. Agent là bậc cuối.

## Code Snippets
```python
# Raw Messages API agent loop — khung tối thiểu (4 bước wire nằm ở đây)
messages = [{"role": "user", "content": user_request}]
for turn in range(MAX_TURNS):                 # exit (b): hard cap, không để loop vô hạn
    resp = client.messages.create(
        model=MODEL,
        max_tokens=800,
        system=SYSTEM_PROMPT,                  # bước 2: scope vào đúng task
        tools=AGENT_TOOLS,                     # bước 1: tools đã register
        messages=messages,
    )
    if resp.stop_reason != "tool_use":         # exit (a): Claude trả lời cuối -> dừng
        break
    messages.append({"role": "assistant", "content": resp.content})
    results = []
    for block in resp.content:                 # bước 3: xử lý MỌI tool_use trong turn
        if block.type != "tool_use":
            continue
        out = execute_tool(block.name, block.input)   # code CỦA BẠN execute
        results.append({
            "type": "tool_result",
            "tool_use_id": block.id,           # phải khớp chính xác id của tool_use
            "content": out,
        })
    messages.append({"role": "user", "content": results})
```

## Questions / Unclear Points
- Manager/supervisor hierarchies + multi-agent (planner / executor / evaluator handoff qua structured
  artifact) — blueprint có, lesson này chưa dạy.
- Subagent memory / handoff artifact format cụ thể.
- Agentic frameworks: Strands, LangGraph, PydanticAI — khác nhau thế nào, khi nào chọn cái nào.
- Hooks cho deterministic actions trong Agent SDK — cơ chế, insertion point.
