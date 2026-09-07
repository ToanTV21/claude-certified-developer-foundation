"""
Exercise 01: Agent wiring paths — cùng 1 loop, 3 cách wire, constraint chọn path trước
Domain: Agents and Workflows
Objective:
    1. Encode quy tắc "governing constraint chọn wiring path TRƯỚC khi wire":
       choose_wiring_path(...) -> "raw_loop" | "agent_sdk" | "managed_agents".
       ZDR/PHI -> KHÔNG BAO GIỜ được ra "managed_agents".
    2. Implement 1 agent loop TỐI THIỂU trên RAW Messages API theo đúng 4 bước
       (register tools -> scope system prompt -> handle tool-use loop -> exit conditions).
       Đây là phần "loop giữ nguyên trên mọi path".
    3. Sketch (chỉ comment, KHÔNG chạy) cách CÙNG agent definition đó re-express
       sang Agent SDK config và sang Managed Agents versioned-resource payload —
       minh hoạ "re-expression step, not a direct export".
    4. main(): in quyết định path cho 3 scenario + chạy raw loop 1 lần.

Chạy được với 1 API key thường. 2 tool đều read-only nên KHÔNG cần HITL ở bài này
(HITL + destructive tool đã có ở domain 06 exercise 05).
"""
import sys                              # để ép stdout sang UTF-8 (console Windows mặc định cp1252)
from dotenv import load_dotenv          # nạp ANTHROPIC_API_KEY từ .env, không hardcode
import anthropic                        # SDK chính thức của Anthropic
import json                             # serialize tool input/result cho dễ đọc

# Console Windows mặc định cp1252 -> print tiếng Việt sẽ raise UnicodeEncodeError.
# reconfigure() ép stdout dùng UTF-8; errors="replace" để không bao giờ crash vì ký tự lạ.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()                           # đọc file .env vào biến môi trường
client = anthropic.Anthropic()         # client tự lấy key từ env

# Rule 1 CLAUDE.md: haiku cho bài tập dev/test.
MODEL = "claude-haiku-4-5"


# ===========================================================================
# PHẦN 1 — choose_wiring_path: constraint chọn path TRƯỚC khi wire
# ===========================================================================
def choose_wiring_path(has_zdr_or_phi: bool,
                       task_runs_long_minutes_to_hours: bool,
                       want_managed_sandbox: bool,
                       need_full_in_process_control: bool) -> str:
    """
    Trả về wiring path đề xuất theo notes domain 01.

    Tham số:
      - has_zdr_or_phi                 : workload dưới Zero Data Retention requirement,
                                         hoặc mang Protected Health Information (PHI).
      - task_runs_long_minutes_to_hours: 1 lần chạy agent kéo dài phút -> giờ.
      - want_managed_sandbox           : muốn Anthropic lo execution sandbox cho tool call.
      - need_full_in_process_control   : cần kiểm soát từng bước trong process của mình
                                         (ràng buộc library không đáp ứng / đang tự học loop).

    Thứ tự ưu tiên (governing constraint đi trước convenience):
      1) ZDR/PHI  -> Managed Agents BỊ LOẠI (session stateful, lưu server-side,
                     không eligible ZDR / HIPAA BAA). Nếu vẫn cần full control -> raw_loop,
                     ngược lại -> agent_sdk (trên covered config).
      2) Cần full in-process control -> raw_loop.
      3) Task chạy lâu + muốn managed sandbox -> managed_agents.
      4) Còn lại -> agent_sdk (cấu trúc loop có sẵn, vẫn in-process).
    """
    # (1) Compliance constraint chốt hạ — quyết định trước tiên, không đàm phán.
    if has_zdr_or_phi:
        # Managed Agents ruled out no matter how well it fits operationally.
        return "raw_loop" if need_full_in_process_control else "agent_sdk"

    # (2) Cần soi/điều khiển từng iteration -> tự viết loop.
    if need_full_in_process_control:
        return "raw_loop"

    # (3) Long-running + không muốn tự build/secure sandbox -> để Anthropic chạy.
    if task_runs_long_minutes_to_hours and want_managed_sandbox:
        return "managed_agents"

    # (4) Mặc định hợp lý: SDK cho cấu trúc, vẫn giữ tool execution trong process mình.
    return "agent_sdk"


# ===========================================================================
# PHẦN 2 — Agent loop tối thiểu trên RAW Messages API (loop "giữ nguyên trên mọi path")
# ===========================================================================

# --- Bước 1: Register tools (cả 2 đều read-only) ---------------------------
GET_TIMEZONE_TOOL = {
    "name": "get_timezone",                        # identifier ngắn, cụ thể
    "description": (
        "Trả về IANA timezone của 1 thành phố (vd 'Asia/Tokyo'). "
        "Dùng khi cần biết múi giờ của 1 địa điểm. "
        "KHÔNG dùng để tính chênh lệch giờ giữa 2 nơi."   # exclusion condition
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "Tên thành phố tiếng Anh, vd 'Tokyo'"},
        },
        "required": ["city"],   # thiếu city thì call vô nghĩa -> required
    },
}

GET_UTC_OFFSET_TOOL = {
    "name": "get_utc_offset",
    "description": (
        "Trả về offset so với UTC (giờ) của 1 IANA timezone, vd '+9'. "
        "Dùng SAU khi đã có timezone, để so sánh giờ giữa các nơi."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "timezone": {"type": "string", "description": "IANA tz, vd 'Asia/Tokyo'"},
        },
        "required": ["timezone"],
    },
}

# Tập tool TỐI THIỂU cho task "trả lời câu hỏi về múi giờ" — không nhồi thêm "just in case".
AGENT_TOOLS = [GET_TIMEZONE_TOOL, GET_UTC_OFFSET_TOOL]

# --- Bước 2: Scope system prompt vào đúng task + nêu tên tool --------------
SYSTEM_PROMPT = (
    "Bạn là trợ lý trả lời câu hỏi về múi giờ. "
    "Chỉ dùng 2 tool: get_timezone (lấy IANA tz của 1 thành phố) và "
    "get_utc_offset (lấy offset UTC của 1 tz). "
    "Khi đã đủ dữ liệu để trả lời, hãy trả lời NGẮN bằng văn bản và DỪNG — không gọi thêm tool."
)


# --- Tool executors: code CỦA BẠN chạy, không phải Claude -----------------
_FAKE_TZ = {"tokyo": "Asia/Tokyo", "hanoi": "Asia/Ho_Chi_Minh", "london": "Europe/London"}
_FAKE_OFFSET = {"Asia/Tokyo": "+9", "Asia/Ho_Chi_Minh": "+7", "Europe/London": "+0"}


def run_get_timezone(city: str) -> str:
    """Tra IANA tz từ tên thành phố (case-insensitive)."""
    tz = _FAKE_TZ.get(city.strip().lower())
    if tz is None:
        return json.dumps({"error": f"Không biết timezone của '{city}'"})
    return json.dumps({"city": city, "timezone": tz})


def run_get_utc_offset(timezone: str) -> str:
    """Tra offset UTC từ IANA tz."""
    off = _FAKE_OFFSET.get(timezone)
    if off is None:
        return json.dumps({"error": f"Không biết offset của '{timezone}'"})
    return json.dumps({"timezone": timezone, "utc_offset": off})


def execute_tool(name: str, tool_input: dict) -> str:
    """Dispatch tên tool -> executor tương ứng (trả JSON string)."""
    if name == "get_timezone":
        return run_get_timezone(**tool_input)
    if name == "get_utc_offset":
        return run_get_utc_offset(**tool_input)
    # Tool chưa implement -> trả lỗi để Claude biết đường xử lý
    return json.dumps({"error": f"Tool '{name}' chưa được implement"})


# --- Bước 3 + 4: handle tool-use loop + exit conditions -------------------
def run_agent(user_request: str, max_turns: int = 5) -> str:
    """
    Agent loop tối thiểu trên RAW Messages API — ĐÂY là phần không đổi giữa 3 wiring path.

    Exit conditions (bước 4) — loop DỪNG khi 1 trong các điều kiện sau, KHÔNG phụ
    thuộc Claude tự nguyện dừng:
      (a) stop_reason != "tool_use"  -> Claude đã trả lời văn bản cuối.
      (b) đạt max_turns              -> chặn agent xin tool call vô hạn.
    """
    messages = [{"role": "user", "content": user_request}]

    for _turn in range(max_turns):                    # (b) hard cap số vòng lặp
        resp = client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=SYSTEM_PROMPT,                      # bước 2: top-level, không nằm trong messages
            tools=AGENT_TOOLS,                         # bước 1: tools đã register
            messages=messages,
        )

        # (a) EXIT: Claude không còn muốn gọi tool -> ghép text trả về
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text") or "(hết, không text)"

        # Giữ NGUYÊN cả content array của assistant turn (kể cả text block nếu có)
        messages.append({"role": "assistant", "content": resp.content})

        # Bước 3: xử lý MỌI tool_use block trong turn này, resolve cùng nhau
        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            result_str = execute_tool(block.name, block.input)   # code của bạn execute
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,          # phải khớp CHÍNH XÁC id của tool_use
                "content": result_str,
                "is_error": '"error"' in result_str,   # cờ lỗi thô sơ cho demo
            })

        # tool_result nằm ở user turn NGAY sau assistant turn vừa rồi
        messages.append({"role": "user", "content": tool_results})

    # (b) EXIT: hết max_turns mà chưa xong -> dừng cứng
    return f"Đạt giới hạn {max_turns} turn mà agent chưa hoàn tất — dừng để tránh loop vô hạn."


# ===========================================================================
# PHẦN 3 — CÙNG agent definition re-express sang SDK / Managed Agents (chỉ sketch)
# ===========================================================================
# LƯU Ý: các block dưới KHÔNG chạy — chỉ để thấy "loop không đổi, chỉ đổi cách khai báo".
#
# --- (a) Agent SDK: định nghĩa ở code-level + filesystem config -------------
#   from claude_agent_sdk import Agent
#   agent = Agent(
#       model=MODEL,
#       system_prompt=SYSTEM_PROMPT,       # y hệt string ở trên
#       tools=[get_timezone, get_utc_offset],   # cùng schema, nhưng đăng ký qua SDK
#   )
#   # SDK lo: iterate loop, context management, parallel tool handling.
#   # BẠN vẫn tự viết thân hàm get_timezone / get_utc_offset (tool execution).
#
# --- (b) Managed Agents: định nghĩa như 1 VERSIONED API RESOURCE -----------
#   agent = client.beta.agents.create(          # tạo resource, nhận về 1 agent ID
#       model=MODEL,
#       system_prompt=SYSTEM_PROMPT,            # cùng nội dung, khác nơi lưu
#       tools=[GET_TIMEZONE_TOOL, GET_UTC_OFFSET_TOOL],
#       # + mcp_servers=[...], skills=[...] nếu có
#   )
#   # Sau đó chỉ gửi user event theo agent.id; Anthropic chạy loop + sandbox,
#   # kết quả stream về qua SSE. Session stateful server-side
#   # -> KHÔNG dùng path này nếu workload có PHI / dưới ZDR.
#
# => Chuyển từ SDK sang Managed Agents là bước RE-EXPRESS (đổi format khai báo),
#    không phải export thẳng. Phần loop 4 bước ở PHẦN 2 là cái giữ nguyên.


def main():
    # --- PHẦN 1: quyết định wiring path cho 3 scenario --------------------
    print("== choose_wiring_path ==")

    # Scenario 1: bệnh viện, workload có PHI, cần soi từng bước -> raw_loop (managed BỊ LOẠI)
    print(" PHI + cần full control        ->",
          choose_wiring_path(has_zdr_or_phi=True,
                             task_runs_long_minutes_to_hours=True,
                             want_managed_sandbox=True,
                             need_full_in_process_control=True))

    # Scenario 2: research agent chạy nhiều giờ, không PHI, muốn managed sandbox -> managed_agents
    print(" Long-running + managed sandbox ->",
          choose_wiring_path(has_zdr_or_phi=False,
                             task_runs_long_minutes_to_hours=True,
                             want_managed_sandbox=True,
                             need_full_in_process_control=False))

    # Scenario 3: internal tool bình thường -> agent_sdk (mặc định hợp lý)
    print(" Task thường, không ràng buộc   ->",
          choose_wiring_path(has_zdr_or_phi=False,
                             task_runs_long_minutes_to_hours=False,
                             want_managed_sandbox=False,
                             need_full_in_process_control=False))

    # --- PHẦN 2: chạy raw loop 1 lần ------------------------------------
    print("\n== raw Messages API agent loop ==")
    answer = run_agent("Tokyo và London chênh nhau mấy tiếng?")
    print(" ->", answer)


if __name__ == "__main__":
    main()
