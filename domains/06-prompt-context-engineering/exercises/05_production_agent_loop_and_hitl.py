"""
Exercise 05: Building a production agent — the loop, wiring, HITL, exit conditions
Domain: Prompt and Context Engineering
Objective:
    1. Trả lời câu hỏi "task này có cần agent không" bằng 1 checklist workflow-vs-agent.
    2. Wire 1 agent loop tối thiểu trên RAW Messages API theo đúng 4 bước:
       register tools -> scope system prompt -> handle tool-use loop -> define exit conditions.
    3. Chèn 1 human-in-the-loop (HITL) checkpoint TRƯỚC destructive tool call.
    4. Minh hoạ over-tooling: tool surface phình + description trùng -> routing kém.
    5. Ghi chú compliance: constraint (PHI/ZDR/GDPR/FedRAMP) chọn endpoint TRƯỚC khi wire.

Chạy được với 1 API key thường (không thực sự gửi email / xoá gì — tool "destructive"
chỉ mô phỏng). HITL ở đây đọc input() từ terminal; trong prod đó là 1 review queue.
"""
from dotenv import load_dotenv          # load ANTHROPIC_API_KEY từ .env, không hardcode
import anthropic                        # SDK chính thức của Anthropic
import json                             # in tool input cho người review đọc

load_dotenv()                           # nạp biến môi trường từ .env
client = anthropic.Anthropic()         # client tự đọc key từ env

# Rule 1 CLAUDE.md: dùng haiku cho bài tập dev/test.
# Nguyên tắc bài giảng: production BẮT ĐẦU ở Sonnet, chỉ di chuyển khi eval set nói vậy.
MODEL = "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# BƯỚC 0 — Quyết định TRƯỚC dòng code đầu: workflow hay agent?
# ---------------------------------------------------------------------------
def needs_agent(can_enumerate_steps: bool,
                inputs_well_constrained: bool,
                needs_standard_observability: bool,
                path_known_in_advance: bool) -> str:
    """
    Trả về "workflow" hoặc "agent" theo bảng quyết định trong notes.

    - can_enumerate_steps        : liệt kê được chính xác các bước bằng code?
    - inputs_well_constrained     : input thuộc 1 tập đã biết, ít biến thiên?
    - needs_standard_observability: bắt buộc observability bằng tooling operational chuẩn?
    - path_known_in_advance       : path xuyên qua công việc biết trước?

    Chỉ cần 1 tín hiệu "đây là việc có cấu trúc cố định" đủ mạnh -> chọn workflow.
    Agent là BẬC CUỐI: chỉ khi pattern đơn giản hơn (1 API call / workflow) không
    xử lý nổi độ biến thiên của task.
    """
    workflow_signals = [
        can_enumerate_steps,
        inputs_well_constrained,
        needs_standard_observability,
        path_known_in_advance,
    ]
    # Đa số tín hiệu nghiêng về "có cấu trúc" -> workflow
    if sum(workflow_signals) >= 3:
        return "workflow"
    return "agent"


# ---------------------------------------------------------------------------
# BƯỚC 1 — Register tools (mỗi tool cùng schema structure: name + description + input_schema)
# ---------------------------------------------------------------------------
# Tool đọc — không destructive, không cần HITL.
LOOKUP_ORDER_TOOL = {
    "name": "lookup_order",                       # identifier ngắn, cụ thể
    "description": (
        "Tra cứu trạng thái và tổng tiền của 1 đơn hàng theo order_id. "
        "Dùng khi user hỏi về tình trạng đơn / số tiền đã thanh toán. "
        "KHÔNG dùng để thay đổi đơn hay gửi thông báo cho khách."   # exclusion condition
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "description": "Mã đơn hàng, vd 'A-1029'"},
        },
        "required": ["order_id"],   # call vô nghĩa nếu thiếu -> required
    },
}

# Tool GHI / GỬI — destructive (irreversible): phải đi qua HITL checkpoint.
SEND_REFUND_EMAIL_TOOL = {
    "name": "send_refund_email",
    "description": (
        "Gửi email xác nhận hoàn tiền cho khách hàng. "
        "Chỉ dùng sau khi đã xác nhận đơn hàng đủ điều kiện hoàn tiền. "
        "Đây là hành động KHÔNG hoàn tác được (email đã gửi không thu hồi)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {"type": "string"},
            "to_email": {"type": "string"},
            "amount": {"type": "number", "description": "Số tiền hoàn, đơn vị USD, luôn dương"},
        },
        "required": ["order_id", "to_email", "amount"],
        "additionalProperties": False,
    },
}

# Tập tool TỐI THIỂU cho task "trợ lý xử lý yêu cầu hoàn tiền".
AGENT_TOOLS = [LOOKUP_ORDER_TOOL, SEND_REFUND_EMAIL_TOOL]

# Tên các tool được coi là destructive -> cần human review trước khi execute.
DESTRUCTIVE_TOOLS = {"send_refund_email"}


# ---------------------------------------------------------------------------
# BƯỚC 2 — Scope system prompt vào ĐÚNG task + nêu tên tools dành cho nó
# ---------------------------------------------------------------------------
# System prompt rộng -> routing rộng, kém tin cậy.
# System prompt nêu task cụ thể + tool tương ứng -> hành vi nhất quán hơn.
SYSTEM_PROMPT = (
    "Bạn là trợ lý xử lý yêu cầu hoàn tiền của bộ phận CSKH. "
    "Nhiệm vụ: với mỗi yêu cầu của khách, (1) tra cứu đơn hàng bằng lookup_order, "
    "(2) nếu đơn đủ điều kiện hoàn tiền thì gửi email xác nhận bằng send_refund_email. "
    "Chỉ dùng đúng 2 tool này. Khi đã gửi email hoàn tiền (hoặc xác định đơn KHÔNG đủ "
    "điều kiện), hãy trả lời khách bằng văn bản và DỪNG — không gọi thêm tool."
)


# ---------------------------------------------------------------------------
# Tool executors — code CỦA BẠN chạy, không phải Claude
# ---------------------------------------------------------------------------
# "DB" giả lập.
_FAKE_ORDERS = {
    "A-1029": {"status": "delivered", "amount": 49.0, "email": "khach1@example.com", "refundable": True},
    "A-2087": {"status": "shipped", "amount": 120.0, "email": "khach2@example.com", "refundable": False},
}


def run_lookup_order(order_id: str) -> str:
    """Trả về JSON string trạng thái đơn (hoặc lỗi nếu không tìm thấy)."""
    order = _FAKE_ORDERS.get(order_id)
    if order is None:
        return json.dumps({"error": f"Không tìm thấy đơn {order_id}"})
    return json.dumps(order)


def run_send_refund_email(order_id: str, to_email: str, amount: float) -> str:
    """Mô phỏng gửi email — trong bài tập chỉ in ra, không gửi thật."""
    print(f"    [EMAIL ĐÃ GỬI] tới {to_email}: hoàn ${amount:.2f} cho đơn {order_id}")
    return json.dumps({"sent": True, "order_id": order_id})


def execute_tool(name: str, tool_input: dict) -> str:
    """Dispatch tên tool -> executor tương ứng."""
    if name == "lookup_order":
        return run_lookup_order(**tool_input)
    if name == "send_refund_email":
        return run_send_refund_email(**tool_input)
    # Tool chưa được implement -> trả lỗi để Claude biết mà xử lý (is_error phía dưới)
    return json.dumps({"error": f"Tool '{name}' chưa được implement"})


# ---------------------------------------------------------------------------
# BƯỚC 4 (HITL) — checkpoint TRƯỚC destructive tool call
# ---------------------------------------------------------------------------
def human_approves(tool_name: str, tool_input: dict) -> bool:
    """
    Pause agent execution -> route sang human review.
    Câu hỏi quyết định chỗ chèn: worst-case nếu step này chạy không có human check?
    send_refund_email = irreversible -> chèn ở High risk point.

    Prod: đây là 1 review queue / Slack approve. Bài tập: đọc input() từ terminal.
    """
    print(f"\n  [HITL] Agent muốn gọi tool destructive: {tool_name}")
    print(f"         input = {json.dumps(tool_input, ensure_ascii=False)}")
    answer = input("         Duyệt? (y/n): ").strip().lower()
    return answer == "y"


# ---------------------------------------------------------------------------
# BƯỚC 3 + 5 — Handle tool-use loop + define exit conditions
# ---------------------------------------------------------------------------
def run_agent(user_request: str, max_turns: int = 6) -> str:
    """
    Agent loop tối thiểu trên RAW Messages API.

    Exit conditions (BƯỚC 5) — loop DỪNG khi 1 trong các điều kiện sau đúng,
    KHÔNG phụ thuộc Claude tự nguyện dừng:
      (a) stop_reason != "tool_use"  -> Claude đã trả lời văn bản cuối cùng.
      (b) max_turns đạt tới          -> chặn agent xin tool call vô hạn.
      (c) human từ chối 1 destructive tool call -> abort task.
    """
    messages = [{"role": "user", "content": user_request}]

    for turn in range(max_turns):                     # (b) hard cap số vòng
        resp = client.messages.create(
            model=MODEL,
            max_tokens=800,
            system=SYSTEM_PROMPT,                      # BƯỚC 2: system prompt top-level
            tools=AGENT_TOOLS,                         # BƯỚC 1: tools đã register
            messages=messages,
        )

        # (a) EXIT: Claude không còn muốn gọi tool -> trả lời cuối cùng
        if resp.stop_reason != "tool_use":
            final_text = "".join(
                b.text for b in resp.content if b.type == "text"
            )
            return final_text or "(agent kết thúc, không có text)"

        # Giữ NGUYÊN cả content array của assistant turn (gồm cả text block nếu có)
        messages.append({"role": "assistant", "content": resp.content})

        # BƯỚC 3: xử lý MỌI tool_use block trong turn này, resolve cùng nhau
        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue

            # HITL checkpoint cho destructive tool
            if block.name in DESTRUCTIVE_TOOLS:
                if not human_approves(block.name, block.input):
                    # (c) EXIT: human từ chối -> abort, không execute
                    return "Task bị huỷ: người review không duyệt hành động hoàn tiền."

            result_str = execute_tool(block.name, block.input)   # code CỦA BẠN execute
            is_error = '"error"' in result_str                    # cờ lỗi thô sơ cho demo
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,        # phải khớp CHÍNH XÁC id của tool_use
                "content": result_str,
                "is_error": is_error,
            })

        # tool_result phải nằm ở user turn NGAY sau assistant turn vừa rồi
        messages.append({"role": "user", "content": tool_results})

    # (b) EXIT: hết max_turns mà chưa kết thúc -> dừng cứng, không để loop chạy mãi
    return f"Đã đạt giới hạn {max_turns} turn mà agent chưa hoàn tất — dừng để tránh loop vô hạn."


# ---------------------------------------------------------------------------
# Minh hoạ OVER-TOOLING — tool surface phình + description trùng -> routing kém
# ---------------------------------------------------------------------------
def demo_over_tooling() -> list:
    """
    Trả về 1 danh sách tool "just in case" với description mở đầu giống hệt nhau.
    Đây KHÔNG phải cách làm đúng — chỉ để thấy vì sao selection quality tụt:
    tại điểm ra quyết định, Claude thấy 4 description na ná -> route thất thường.

    Fix: thu hẹp về tập tối thiểu (như AGENT_TOOLS ở trên), chỉ thêm tool khi
    xác nhận 1 gap capability cụ thể.
    """
    bad = []
    for n in ["find_order", "search_order", "query_order", "get_order_info"]:
        bad.append({
            "name": n,
            "description": "Use this to find information about an order.",  # trùng -> xấu
            "input_schema": {
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
            },
        })
    return bad


# ---------------------------------------------------------------------------
# Ghi chú compliance — constraint chọn endpoint TRƯỚC khi wire (không có code chạy)
# ---------------------------------------------------------------------------
COMPLIANCE_ROUTING = {
    # workload PHI -> BAA-covered config; Managed Agents bị loại (session stateful server-side)
    "HIPAA_PHI": "Direct API/SDK trên BAA-covered config, hoặc Bedrock/Vertex HIPAA-eligible. "
                 "KHÔNG Managed Agents, KHÔNG Console/Workbench/beta/consumer.",
    # ZDR requirement -> Managed Agents bị loại
    "ZDR": "Agent SDK hoặc raw loop trên covered config. Managed Agents không eligible ZDR.",
    # EU data residency -> direct Anthropic API không có EU residency
    "GDPR_EU_RESIDENCY": "Bedrock hoặc Vertex với region PIN trong client config. "
                         "KHÔNG gọi direct Anthropic API.",
    # FedRAMP -> chỉ 3 route authorized
    "FEDRAMP": "Claude for Government (C4G) / Bedrock GovCloud / Vertex Assured Workloads. "
               "Claude Enterprise trên AWS Marketplace KHÔNG FedRAMP authorized.",
}


def main():
    # BƯỚC 0 — ví dụ quyết định pattern
    print("== Workflow hay agent? ==")
    print(" - Pipeline ETL cố định, input schema biết trước:",
          needs_agent(True, True, True, True))          # -> workflow
    print(" - Trợ lý CSKH, yêu cầu khách biến thiên tự do:",
          needs_agent(False, False, False, False))      # -> agent

    # BƯỚC 1-5 — chạy agent loop (case đủ điều kiện hoàn tiền -> sẽ hỏi HITL)
    print("\n== Agent: yêu cầu hoàn tiền đơn A-1029 (refundable) ==")
    print(run_agent("Khách yêu cầu hoàn tiền cho đơn A-1029, email khach1@example.com."))

    # Case KHÔNG đủ điều kiện -> agent trả lời văn bản, không gọi send_refund_email
    print("\n== Agent: yêu cầu hoàn tiền đơn A-2087 (không refundable) ==")
    print(run_agent("Khách muốn hoàn tiền đơn A-2087."))

    # Over-tooling
    print("\n== Over-tooling: 4 tool description trùng nhau (anti-pattern) ==")
    for t in demo_over_tooling():
        print(f" - {t['name']}: {t['description']}")

    # Compliance routing
    print("\n== Compliance -> endpoint routing (quyết định TRƯỚC khi wire) ==")
    for k, v in COMPLIANCE_ROUTING.items():
        print(f" - {k}: {v}")


if __name__ == "__main__":
    main()
