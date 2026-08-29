"""
Exercise 03: Tool Schemas Claude Selects Correctly — schema anatomy, tool-use loop, disambiguation
Domain: Prompt and Context Engineering
Objective:
    1. Định nghĩa 1 tool schema đúng bài bản: name cụ thể + description 2 phần
       (khi nào dùng / khi nào KHÔNG dùng) + input_schema với `required` tối thiểu.
    2. Tự chạy tool-use loop 6 bước bằng CODE: Claude chỉ trả `tool_use`, còn app
       (file này) mới execute tool và trả `tool_result` ở user turn NGAY sau, với
       `tool_use_id` khớp chính xác.
    3. Minh hoạ selection-disambiguation: 2 tool có description mơ hồ giống nhau ->
       Claude dễ chọn sai; thêm exclusion condition -> routing ổn định.

Ghi chú tương thích: cấu trúc block (`tool_use` / `tool_result`) và param `tools`
là API hiện hành. Nếu SDK báo lỗi field, đối chiếu skill `claude-api`.
"""
from dotenv import load_dotenv          # load API key từ .env, không hardcode
import anthropic                        # SDK chính thức của Anthropic
import json                             # in message/args cho dễ đọc

load_dotenv()                           # đọc ANTHROPIC_API_KEY vào biến môi trường
client = anthropic.Anthropic()         # client tự lấy key từ env

MODEL = "claude-haiku-4-5"             # dùng haiku cho bài tập dev/test (rule 1 trong CLAUDE.md)


# ---------------------------------------------------------------------------
# Phần 1: Hai phiên bản schema — mơ hồ (gây chọn sai) vs có exclusion condition
# ---------------------------------------------------------------------------

# --- Phiên bản MƠ HỒ: cả 2 description đều mở đầu "use this to find information" ---
# Claude route chủ yếu theo description; description giống nhau -> tên tool không đủ phân biệt.
VAGUE_TOOLS = [
    {
        "name": "search_knowledge_base",           # name cụ thể nhưng chưa đủ cứu
        "description": "Use this to find information.",  # quá ngắn -> Claude phải đoán
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},  # tham số: chuỗi truy vấn
            "required": ["query"],                         # không có query thì call vô nghĩa
        },
    },
    {
        "name": "get_cached_result",
        "description": "Use this to find information.",  # trùng ý -> routing sụp về mình description
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},  # cùng shape param -> overlapping types
            "required": ["query"],
        },
    },
]

# --- Phiên bản FIX: mỗi description thêm 1 câu "khi nào KHÔNG dùng" (exclusion condition) ---
CLEAR_TOOLS = [
    {
        "name": "search_knowledge_base",
        "description": (
            "Use this to search the knowledge base when the user asks a question that "
            "requires looking up current information. "
            "Do not use this if the result of a prior search in this session already "
            "covers the question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                # mô tả rõ format input mong đợi ngay trong schema
                "query": {"type": "string", "description": "Natural-language search query."}
            },
            "required": ["query"],   # chỉ field thực sự bắt buộc — không mark thừa
        },
    },
    {
        "name": "get_cached_result",
        "description": (
            "Use this to retrieve a result that was already fetched during this session. "
            "Only use this if search_knowledge_base was called earlier in this "
            "conversation for the same query."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The exact query used in the earlier search."}
            },
            "required": ["query"],
        },
    },
]


def which_tool_did_claude_pick(tools, user_message):
    """
    Gửi 1 message + tool list, chỉ đọc xem Claude ĐỊNH gọi tool nào (bước 3 của loop).
    Không execute gì — mục đích là quan sát quyết định routing thay đổi ra sao
    giữa schema mơ hồ và schema có exclusion condition.
    """
    resp = client.messages.create(
        model=MODEL,
        max_tokens=400,
        tools=tools,                                  # danh sách tool Claude được chọn
        messages=[{"role": "user", "content": user_message}],
    )
    # resp.content là 1 LIST block: có thể gồm text block + tool_use block cùng lúc
    picked = [b.name for b in resp.content if b.type == "tool_use"]
    print(f"  stop_reason = {resp.stop_reason}")     # 'tool_use' nếu Claude muốn gọi tool
    print(f"  tool(s) picked = {picked or '(none — trả text thẳng)'}")
    return resp


# ---------------------------------------------------------------------------
# Phần 2: Tool-use loop đầy đủ 6 bước — APP execute tool, không phải Claude
# ---------------------------------------------------------------------------

# Bước 1 (một phần): 1 tool "thật" để chạy loop end-to-end
GET_WEATHER_TOOL = {
    "name": "get_weather",
    "description": (
        "Get the current weather for a specific city. "
        "Use this when the user asks about temperature, rain, or conditions in a named "
        "location. Do not use this for weather forecasts more than 24 hours ahead."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name, e.g. 'Tokyo'."},
            # optional: để NGOÀI 'required' -> Claude được phép bỏ qua nếu không có
            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
        },
        "required": ["city"],   # chỉ 'city' là bắt buộc
    },
}


def run_weather_tool(city, unit="celsius"):
    """
    'Tool' thật do APP sở hữu — ở đây fake dữ liệu cho gọn.
    Trong thực tế đây là chỗ gọi API thời tiết / DB / hệ thống nội bộ.
    """
    fake_db = {"Tokyo": 24, "Hanoi": 31, "London": 12}     # dữ liệu giả lập
    temp_c = fake_db.get(city, 20)                          # default 20 nếu không có city
    temp = temp_c if unit == "celsius" else round(temp_c * 9 / 5 + 32)  # đổi đơn vị nếu cần
    return json.dumps({"city": city, "temp": temp, "unit": unit})       # tool trả string


def full_tool_use_loop(user_message):
    """
    Chạy trọn loop:
      (2) send message -> (3) Claude trả tool_use -> (4) app execute
      -> (5) app trả tool_result (user turn NGAY sau, id khớp) -> (6) Claude tiếp tục.
    """
    # messages là conversation history — phải TỰ tay bồi đắp đúng thứ tự block
    messages = [{"role": "user", "content": user_message}]

    # --- Bước 2: send message lần đầu ---
    resp = client.messages.create(
        model=MODEL, max_tokens=500, tools=[GET_WEATHER_TOOL], messages=messages
    )

    # Lặp tới khi Claude không còn muốn gọi tool nữa
    while resp.stop_reason == "tool_use":
        # --- QUAN TRỌNG: append NGUYÊN cả content array của assistant turn ---
        # (kể cả text block đi kèm) — drop text block sẽ hỏng context turn sau
        messages.append({"role": "assistant", "content": resp.content})

        tool_results = []                       # gom mọi tool_result cho user turn kế tiếp
        for block in resp.content:
            if block.type == "tool_use":
                # --- Bước 4: APP execute tool (Claude KHÔNG tự chạy) ---
                print(f"  -> Claude yêu cầu: {block.name}({json.dumps(block.input)})")
                try:
                    out = run_weather_tool(**block.input)   # unpack input Claude gửi
                    is_error = False
                except Exception as e:                       # tool fail -> báo lại cho Claude
                    out, is_error = str(e), True
                # --- Bước 5 (dựng block): tool_use_id phải KHỚP CHÍNH XÁC block.id ---
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,     # nối kết quả về đúng call
                    "content": out,
                    "is_error": is_error,        # cờ báo lỗi (optional, mặc định False)
                })

        # --- Bước 5 (gửi): tool_result nằm ở user turn NGAY SAU assistant turn ---
        messages.append({"role": "user", "content": tool_results})

        # --- Bước 6: gọi lại API để Claude dùng kết quả tool mà tiếp tục ---
        resp = client.messages.create(
            model=MODEL, max_tokens=500, tools=[GET_WEATHER_TOOL], messages=messages
        )

    # Hết loop: Claude trả lời cuối cùng bằng text
    final_text = "".join(b.text for b in resp.content if b.type == "text")
    print(f"  Câu trả lời cuối: {final_text}")
    return final_text


# ---------------------------------------------------------------------------
# main: chạy lần lượt 3 quan sát
# ---------------------------------------------------------------------------
def main():
    # Câu hỏi mơ hồ: chưa từng search trước đó -> đáp án ĐÚNG là search_knowledge_base
    ambiguous_q = "What is our current refund policy?"

    print("=== 1a. Schema MƠ HỒ (2 description trùng ý) ===")
    which_tool_did_claude_pick(VAGUE_TOOLS, ambiguous_q)

    print("\n=== 1b. Schema CÓ exclusion condition ===")
    which_tool_did_claude_pick(CLEAR_TOOLS, ambiguous_q)

    print("\n=== 2. Tool-use loop đầy đủ (app execute get_weather) ===")
    full_tool_use_loop("How warm is it in Tokyo right now, in fahrenheit?")


if __name__ == "__main__":
    main()
