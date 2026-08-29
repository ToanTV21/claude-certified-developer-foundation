"""
Exercise 02: Extended Thinking — bật reasoning, hiệu chỉnh effort, và carry-back rule
Domain: Prompt and Context Engineering
Objective:
    1. Thấy khác biệt khi BẬT vs TẮT extended thinking trên 1 task multi-step reasoning
       (và vì sao KHÔNG bật cho task máy móc như classification).
    2. Hiệu chỉnh độ sâu reasoning bằng `effort` setting (thay cho `budget_tokens` đã deprecated).
    3. Minh hoạ carry-back rule: trong tool-use loop, thinking block phải được trả lại API
       NGUYÊN VẸN (kèm signature) ở turn kế tiếp — sửa/tóm tắt/bỏ đi -> API reject.

Ghi chú tương thích: bài giảng dạy param `thinking` (adaptive) + `effort`. Tên/So sánh cụ thể
của field có thể lệch nhẹ giữa các version SDK; nếu SDK báo lỗi param, xem lại skill `claude-api`.
`budget_tokens` là control cũ, trên model mới nhất trả HTTP 400 — bài này cố tình không dùng.
"""
from dotenv import load_dotenv          # load API key từ .env, không hardcode
import anthropic                        # SDK chính thức của Anthropic
import json                             # để in cấu trúc message cho dễ đọc

load_dotenv()                           # đọc ANTHROPIC_API_KEY vào biến môi trường
client = anthropic.Anthropic()         # client tự lấy key từ env

MODEL = "claude-haiku-4-5"             # dùng haiku cho bài tập dev/test (rule 1 trong CLAUDE.md)


# ---------------------------------------------------------------------------
# Phần 1: BẬT vs TẮT extended thinking trên 1 task multi-step reasoning
# ---------------------------------------------------------------------------
def multi_step_reasoning_task():
    """
    Task giữ nhiều constraint cùng lúc (logic multi-hop) -> đúng loại task NÊN bật thinking.
    """
    # Prompt cùng 1 bài cho cả 2 lần chạy, chỉ khác việc có bật `thinking` hay không
    prompt = (
        "Ba người An, Bình, Chi ngồi 3 ghế liên tiếp. "
        "An không ngồi cạnh Chi. Bình không ngồi ghế giữa. "
        "Hỏi thứ tự ngồi từ trái sang phải là gì? Giải thích ngắn gọn."
    )

    # --- Lần 1: TẮT extended thinking (mặc định) ---
    # Không truyền param `thinking` -> model trả lời thẳng, không có reasoning block.
    resp_off = client.messages.create(
        model=MODEL,                    # model đang test
        max_tokens=512,                 # giới hạn độ dài response
        messages=[{"role": "user", "content": prompt}],
    )
    print("=== THINKING OFF ===")
    # response.content là list các block; ở đây chỉ có text block
    print(_join_text(resp_off.content))
    print("stop_reason:", resp_off.stop_reason)

    # --- Lần 2: BẬT extended thinking, effort = "high" vì bài toán cần giữ nhiều constraint ---
    resp_on = client.messages.create(
        model=MODEL,
        max_tokens=1024,                # cần rộng hơn: thinking token cũng nằm trong output budget
        messages=[{"role": "user", "content": prompt}],
        # `thinking` bật reasoning; trên model hiện hành reasoning là adaptive (model tự
        # quyết lượng reasoning). `effort` tinh chỉnh độ sâu — KHÔNG dùng `budget_tokens`.
        thinking={"type": "enabled", "effort": "high"},
    )
    print("\n=== THINKING ON (effort=high) ===")
    for block in resp_on.content:       # duyệt từng block để phân biệt thinking vs text
        if block.type == "thinking":
            # Trên model mới nội dung có thể bị ẩn; nếu có summary thì in ra để quan sát
            print("[thinking block]", getattr(block, "thinking", "<hidden>")[:400], "...")
            # signature là thứ API dùng để verify block không bị sửa -> phải giữ nguyên
            print("[thinking signature present]:", bool(getattr(block, "signature", None)))
        elif block.type == "redacted_thinking":
            # nội dung mã hoá, không đọc được, nhưng vẫn phải carry-back nguyên vẹn
            print("[redacted_thinking block] (encrypted, must be returned untouched)")
        elif block.type == "text":
            print("[answer]", block.text)
    print("stop_reason:", resp_on.stop_reason)


# ---------------------------------------------------------------------------
# Phần 2: Task máy móc (classification) — KHÔNG bật extended thinking
# ---------------------------------------------------------------------------
def mechanical_task_no_thinking():
    """
    Classification là task tra cứu/máy móc: extended thinking không cải thiện kết quả,
    chỉ tốn thêm thinking token (tính phí bằng output token). Dùng bare prompt + output
    constraint là đúng tool.
    """
    ticket = "Tôi bị tính phí 2 lần trong tháng này, xin kiểm tra lại hoá đơn."
    resp = client.messages.create(
        model=MODEL,
        max_tokens=16,                  # câu trả lời cực ngắn -> giới hạn chặt
        system=(
            "Bạn là bộ phân loại ticket. Chỉ trả về đúng 1 nhãn trong "
            "{BILLING, TECHNICAL, ESCALATION}. Không thêm chữ nào khác."
        ),
        messages=[{"role": "user", "content": ticket}],
        # KHÔNG truyền `thinking` -> không tốn thinking token cho việc không cần reasoning
    )
    print("\n=== MECHANICAL TASK (no thinking) ===")
    print("label:", _join_text(resp.content))


# ---------------------------------------------------------------------------
# Phần 3: Carry-back rule trong tool-use loop
# ---------------------------------------------------------------------------
# Định nghĩa 1 tool đơn giản để tạo ra 1 vòng tool-use
GET_WEATHER_TOOL = {
    "name": "get_weather",             # tên tool model sẽ gọi
    "description": "Lấy nhiệt độ hiện tại của 1 thành phố (đơn vị Celsius).",
    "input_schema": {                  # schema cho argument model truyền vào
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "Tên thành phố"},
        },
        "required": ["city"],
    },
}


def fake_get_weather(city: str) -> str:
    """Giả lập kết quả tool — bài tập không gọi API thời tiết thật."""
    return json.dumps({"city": city, "temp_c": 31})


def tool_use_loop_with_thinking():
    """
    Khi extended thinking BẬT và conversation có tool: mọi thinking block model trả về
    ở turn N phải được đưa NGUYÊN VẸN vào messages của turn N+1 (cùng với tool_result).
    Nếu bỏ block đi -> signature không khớp -> API trả lỗi.
    """
    # messages tích luỹ toàn bộ hội thoại; ta sẽ append từng turn vào đây
    messages = [
        {"role": "user", "content": "Trời ở Đà Nẵng bây giờ có nên mặc áo khoác không?"}
    ]

    # --- Turn 1: model suy nghĩ rồi quyết định gọi tool ---
    turn1 = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=messages,
        tools=[GET_WEATHER_TOOL],       # cung cấp tool để model có thể gọi
        thinking={"type": "enabled", "effort": "medium"},
    )
    print("\n=== TOOL-USE LOOP: turn 1 ===")
    print("stop_reason:", turn1.stop_reason)   # kỳ vọng: "tool_use"

    # QUAN TRỌNG: append NGUYÊN list block model trả về (gồm cả thinking block + tool_use)
    # -> đây chính là carry-back: không lọc bỏ, không tóm tắt thinking block.
    messages.append({"role": "assistant", "content": turn1.content})

    # Tìm tool_use block để chạy tool tương ứng
    tool_use = next(b for b in turn1.content if b.type == "tool_use")
    result_text = fake_get_weather(**tool_use.input)   # chạy tool giả lập

    # Gửi tool_result về cho model ở turn 2
    messages.append({
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": tool_use.id,   # phải khớp id của tool_use block
            "content": result_text,
        }],
    })

    # --- Turn 2: model đọc tool_result + thinking block cũ (nguyên vẹn) rồi trả lời cuối ---
    turn2 = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=messages,              # messages đã chứa thinking block turn 1 -> hợp lệ
        tools=[GET_WEATHER_TOOL],
        thinking={"type": "enabled", "effort": "medium"},
    )
    print("\n=== TOOL-USE LOOP: turn 2 (final) ===")
    print(_join_text(turn2.content))
    print("stop_reason:", turn2.stop_reason)

    # --- Minh hoạ VI PHẠM carry-back: bỏ thinking block ra khỏi assistant turn 1 ---
    broken_messages = list(messages[:-1])   # bỏ tool_result cuối để tái tạo state turn 2
    # thay assistant content bằng bản ĐÃ LỌC BỎ thinking block -> signature mismatch
    broken_messages[1] = {
        "role": "assistant",
        "content": [b for b in turn1.content if b.type != "thinking"],
    }
    broken_messages.append(messages[-1])
    try:
        client.messages.create(
            model=MODEL,
            max_tokens=256,
            messages=broken_messages,
            tools=[GET_WEATHER_TOOL],
            thinking={"type": "enabled", "effort": "medium"},
        )
        print("\n[UNEXPECTED] request không bị reject")
    except anthropic.BadRequestError as e:
        # Đây là hành vi mong đợi: API từ chối vì thinking block bị strip
        print("\n=== CARRY-BACK VIOLATION (mong đợi lỗi) ===")
        print("API rejected:", str(e)[:300])


def _join_text(content_blocks) -> str:
    """Gộp text từ các block type == 'text' thành 1 chuỗi."""
    return "".join(b.text for b in content_blocks if b.type == "text")


def main():
    multi_step_reasoning_task()   # Phần 1: on vs off cho task reasoning
    mechanical_task_no_thinking() # Phần 2: task máy móc -> để off
    tool_use_loop_with_thinking() # Phần 3: carry-back rule + minh hoạ vi phạm


if __name__ == "__main__":
    main()
