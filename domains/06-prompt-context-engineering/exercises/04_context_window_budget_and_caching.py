"""
Exercise 04: Model selection + Context window budget (context engineering)
Domain: Prompt and Context Engineering
Objective:
    1. Đo context pressure TRƯỚC khi request đi ra bằng endpoint `count_tokens`
       (không chạy inference) -> gate request sẽ vượt window.
    2. Bật prompt caching trên 1 prefix ổn định (system prompt dài) bằng
       `cache_control: {"type": "ephemeral"}` và đọc `usage` để thấy cache write/read.
    3. Manual compaction: so sánh summarizer YẾU vs MẠNH -> summarizer sơ sài làm mất
       task-critical state (file paths, decisions, errors).
    4. Phác pattern subagent handoff: parent chỉ pass scoped task + minimum context,
       subagent trả về 1 summary ngắn.

Ghi chú tương thích: field/tên trong `usage` (cache_creation_input_tokens,
cache_read_input_tokens) có thể lệch nhẹ giữa version SDK; nếu SDK báo lỗi param,
xem lại skill `claude-api`. Model selection ("chọn model nào") thuộc module MSO —
ở đây chỉ minh hoạ nguyên tắc "bắt đầu ở Sonnet, di chuyển khi eval nói vậy".
"""
from dotenv import load_dotenv          # load API key từ .env, không hardcode
import anthropic                        # SDK chính thức của Anthropic

load_dotenv()                           # đọc ANTHROPIC_API_KEY vào biến môi trường
client = anthropic.Anthropic()         # client tự lấy key từ env

# Rule 1 CLAUDE.md: dùng haiku cho bài tập dev/test.
# Nguyên tắc bài giảng: production BẮT ĐẦU ở Sonnet, chỉ xuống Haiku khi eval set cho
# thấy regression chất lượng chấp nhận được cho task -> đây là quyết định CÓ ĐO LƯỜNG.
MODEL = "claude-haiku-4-5"

# Ngưỡng context window để demo gate (con số thật tùy model — xác nhận ở platform docs).
# Ở đây đặt ngưỡng nhỏ giả định để thấy logic gate hoạt động.
DEMO_WINDOW_LIMIT = 8_000


# ---------------------------------------------------------------------------
# Phần 1: Token counting — đo TRƯỚC khi gọi, gate nếu sẽ vượt
# ---------------------------------------------------------------------------
def gate_request_by_token_count(messages, system=None, tools=None):
    """
    `count_tokens` nhận CÙNG request body như `messages.create` nhưng KHÔNG chạy
    inference -> rẻ và nhanh. Dùng để verify giả định context budget với tool output
    THẬT (thường dài gấp 3-5 lần test fixture), và để chặn request sẽ error.
    """
    # Gọi endpoint đếm token; truyền đúng các field sẽ dùng ở messages.create
    kwargs = {"model": MODEL, "messages": messages}
    if system is not None:
        kwargs["system"] = system
    if tools is not None:
        kwargs["tools"] = tools
    count = client.messages.count_tokens(**kwargs)

    input_tokens = count.input_tokens           # số token phía input của request
    print(f"[count_tokens] input_tokens = {input_tokens}")

    # Gate: nếu input đã gần trần thì KHÔNG gửi — thay vào đó trim/summarize history.
    if input_tokens >= DEMO_WINDOW_LIMIT:
        print(f"[GATE] {input_tokens} >= {DEMO_WINDOW_LIMIT} -> phải compact/trim trước khi gửi")
        return None

    # Còn budget -> gửi thật
    resp = client.messages.create(model=MODEL, max_tokens=256, **_without_model(kwargs))
    print("[sent] stop_reason:", resp.stop_reason)
    return resp


def _without_model(kwargs):
    """Bỏ key 'model' ra khỏi dict (messages.create nhận model qua positional ở trên)."""
    return {k: v for k, v in kwargs.items() if k != "model"}


# ---------------------------------------------------------------------------
# Phần 2: Prompt caching — cache prefix ổn định để giảm cost xuyên turn
# ---------------------------------------------------------------------------
# System prompt dài, HIẾM đổi qua các turn -> ứng viên lý tưởng để cache.
LONG_STABLE_SYSTEM = (
    "Bạn là trợ lý phân tích hợp đồng. Luôn trả lời bằng tiếng Việt, giọng trung tính.\n"
    + ("Quy tắc nội bộ (không được vi phạm): " + "x" * 2000 + "\n")  # độn cho đủ dài để đáng cache
)


def prompt_caching_demo():
    """
    Đánh dấu cache breakpoint bằng field `cache_control` type `ephemeral` trên BLOCK
    CUỐI CÙNG muốn cache. Tối đa 4 breakpoint/request.
    - Request đầu: GHI prefix vào cache -> usage.cache_creation_input_tokens > 0
    - Request sau (content giống hệt tới điểm đó): ĐỌC từ cache -> cache_read_input_tokens > 0,
      chỉ trả 1 phần nhỏ cost gốc.
    """
    # system truyền dạng list block để gắn được cache_control lên block cuối
    system_blocks = [
        {
            "type": "text",
            "text": LONG_STABLE_SYSTEM,
            "cache_control": {"type": "ephemeral"},   # <-- cache breakpoint
        }
    ]

    for i, question in enumerate(["Điều khoản phạt chậm thanh toán thường gồm gì?",
                                  "Còn điều khoản bảo mật thì sao?"]):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=128,
            system=system_blocks,                    # prefix ổn định -> được cache
            messages=[{"role": "user", "content": question}],
        )
        u = resp.usage
        print(f"\n[caching] request #{i + 1}")
        # 2 field này cho thấy cache có hoạt động không
        print("  cache_creation_input_tokens:", getattr(u, "cache_creation_input_tokens", None))
        print("  cache_read_input_tokens    :", getattr(u, "cache_read_input_tokens", None))
        print("  input_tokens (không cache) :", u.input_tokens)


# ---------------------------------------------------------------------------
# Phần 3: Manual compaction — summarizer YẾU vs MẠNH
# ---------------------------------------------------------------------------
# Giả lập 1 đoạn history agent đã làm việc: có sửa file, có quyết định, có lỗi + cách fix.
FAKE_HISTORY = """
User: Thêm retry cho HTTP client.
Assistant: Đã sửa src/net/client.py — thêm hàm _retry() với backoff 3 lần.
Assistant: Đã sửa src/net/__init__.py — export _retry.
Assistant: Chạy test: test_timeout FAIL do mock chưa raise TimeoutError.
Assistant: Đã fix bằng cách set side_effect=TimeoutError trong tests/test_net.py. Test PASS.
User: OK giờ thêm logging.
Assistant: Đã sửa src/net/client.py — thêm logger.debug ở mỗi lần retry.
""".strip()

WEAK_SUMMARIZER = "Summarize the conversation so far."

STRONG_SUMMARIZER = (
    "Summarize the conversation, preserving ALL file paths modified, ALL decisions made, "
    "and any errors encountered and their resolutions."
)


def compaction_demo():
    """
    Cùng history, khác prompt summarizer -> khác hẳn cái agent 'biết' ở turn sau.
    Summarizer sơ sài làm mất task-critical state (file paths, quyết định, lỗi+fix) —
    1 trong các nguồn failure phổ biến nhất của multi-session agent.
    """
    for label, summarizer in [("WEAK", WEAK_SUMMARIZER), ("STRONG", STRONG_SUMMARIZER)]:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=400,
            system=summarizer,                       # prompt summarizer = system
            messages=[{"role": "user", "content": FAKE_HISTORY}],
        )
        print(f"\n=== COMPACTION SUMMARY ({label}) ===")
        print(_join_text(resp.content))


# ---------------------------------------------------------------------------
# Phần 4: Subagent handoff — parent chỉ pass scoped task + minimum context
# ---------------------------------------------------------------------------
def subagent_handoff_demo():
    """
    Task exploration làm rối main context nhưng kết quả ngắn -> delegate.
    Subagent nhận: scoped task + minimum context + exit condition rõ ràng.
    Nó trả về 1 SUMMARY; các bước trung gian bị bỏ cùng context của subagent.
    """
    # 'context tối thiểu' subagent cần — KHÔNG đổ cả lịch sử của parent vào đây
    scoped_task = (
        "Nhiệm vụ: liệt kê tối đa 3 rủi ro bảo mật khi lưu API key trong biến môi trường. "
        "Exit condition: trả về đúng 1 danh sách bullet, tối đa 3 gạch đầu dòng, không giải thích dài."
    )
    sub = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system="Bạn là subagent chuyên rà soát bảo mật. Chỉ trả về kết quả cuối, không kể quá trình.",
        messages=[{"role": "user", "content": scoped_task}],
    )
    summary = _join_text(sub.content)
    print("\n=== SUBAGENT RETURNED SUMMARY ===")
    print(summary)

    # Parent chỉ nhét SUMMARY ngắn này vào context của mình, không phải toàn bộ reasoning
    parent_messages = [
        {"role": "user", "content": "Dựa trên rà soát bảo mật dưới đây, có nên dùng .env không?\n\n"
                                    + summary}
    ]
    parent = client.messages.create(model=MODEL, max_tokens=150, messages=parent_messages)
    print("\n=== PARENT DECISION (context gọn) ===")
    print(_join_text(parent.content))


def _join_text(content_blocks) -> str:
    """Gộp text từ các block type == 'text' thành 1 chuỗi."""
    return "".join(b.text for b in content_blocks if b.type == "text")


def main():
    # Phần 1: đo token + gate. messages nhỏ -> qua được gate.
    gate_request_by_token_count(
        messages=[{"role": "user", "content": "Tóm tắt 1 câu: hợp đồng thuê nhà 12 tháng."}]
    )
    prompt_caching_demo()      # Phần 2: cache prefix ổn định
    compaction_demo()          # Phần 3: summarizer yếu vs mạnh
    subagent_handoff_demo()    # Phần 4: handoff giữ context parent gọn


if __name__ == "__main__":
    main()
