"""
Exercise 06-01: Diagnosing Prompt Failures & Structured Outputs
Domain: Prompt and Context Engineering
Objective: (1) Minh hoạ worked example "classification prompt" — từ 1 prompt sơ
khai gây lỗi output không nhất quán, chẩn đoán đúng loại lỗi ("thiếu output
constraint"), rồi fix bằng cách kết hợp System Prompt + XML Tags + Few-shot
Examples. (2) Minh hoạ Structured Outputs ở cấp API — dùng output_config.format
(json_schema) để ép response luôn là JSON hợp lệ, và strict tool use để ép
argument truyền vào tool luôn khớp input_schema.
"""

import json  # dùng để parse JSON trả về từ Structured Outputs (phần 2)

from dotenv import load_dotenv  # nạp biến môi trường từ file .env (ANTHROPIC_API_KEY)
import anthropic  # SDK chính thức của Anthropic để gọi Claude API

load_dotenv()  # đọc .env vào os.environ, để client tự lấy API key
client = anthropic.Anthropic()  # khởi tạo client, tự đọc ANTHROPIC_API_KEY từ env

MODEL_DEV = "claude-haiku-4-5"  # dùng haiku cho dev/test để tiết kiệm cost (đúng convention project)
MODEL_MAIN = "claude-sonnet-4-6"  # model dùng cho prod/test thật, không dùng trong bài tập này

# Ticket mẫu dùng xuyên suốt phần 1 (worked example classification)
SAMPLE_TICKET = "I was charged twice for the same month."


# ---------------------------------------------------------------------------
# PHẦN 1 — Diagnosing Prompt Failures: worked example classification prompt
# ---------------------------------------------------------------------------

# BARE_SYSTEM_PROMPT: prompt sơ khai, không có output constraint nào.
# Lỗi quan sát được khi chạy nhiều lần: model trả về "Billing", "billing", hoặc
# cả câu văn "This looks like a billing issue." — router phía sau parse sẽ vỡ
# vì không có 1 hình dạng output cố định để bám vào.
BARE_SYSTEM_PROMPT = "You are a support classifier. Classify the ticket."

# FIXED_SYSTEM_PROMPT: sau khi chẩn đoán đúng loại lỗi ("sai hình dạng output"
# -> thiếu output constraint), fix kéo theo 2 kỹ thuật khác đi kèm:
#   - Output constraint: quy định rõ đúng 1 trong 3 nhãn cố định, "return only
#     the label, no other text".
#   - (Few-shot + XML tags nằm ở FEW_SHOT_EXAMPLES bên dưới, được nối vào cùng
#     system prompt này trước khi gửi request.)
FIXED_SYSTEM_PROMPT = (
    "You are a support classifier. Classify each ticket into exactly one of: "
    "BILLING, TECHNICAL, ESCALATION. Return only the label. No other text."
)

# FEW_SHOT_EXAMPLES: mỗi ví dụ bọc trong <sample_input>/<ideal_output> — dùng
# XML tags để model không hiểu nhầm ví dụ là 1 phần của instruction, và few-shot
# để "cho xem" đúng casing/format cần trả (chữ hoa, không kèm câu văn thừa).
FEW_SHOT_EXAMPLES = """
<sample_input>My account shows two charges for April.</sample_input>
<ideal_output>BILLING</ideal_output>

<sample_input>The API keeps returning a 429 error.</sample_input>
<ideal_output>TECHNICAL</ideal_output>
"""


def classify_bare(ticket: str) -> str:
    """Gọi Claude với prompt sơ khai (chưa chẩn đoán/fix) để tái hiện lỗi."""
    # ticket: str — nội dung ticket cần phân loại
    response = client.messages.create(
        model=MODEL_DEV,  # model dùng để classify (haiku cho dev/test)
        max_tokens=50,  # output kỳ vọng ngắn (chỉ 1 label hoặc 1 câu ngắn khi lỗi)
        system=BARE_SYSTEM_PROMPT,  # system prompt sơ khai, không ràng buộc hình dạng output
        messages=[{"role": "user", "content": f"<ticket>{ticket}</ticket>"}],
    )
    return response.content[0].text.strip()  # lấy text, bỏ khoảng trắng thừa


def classify_fixed(ticket: str) -> str:
    """Gọi Claude sau khi đã fix bằng System Prompt + XML Tags + Few-shot."""
    # ticket: str — nội dung ticket cần phân loại
    # Nối few-shot examples vào sau system prompt chính — ví dụ luôn đặt sau
    # phần instruction/guideline chính, không đặt trước.
    full_system = FIXED_SYSTEM_PROMPT + "\n" + FEW_SHOT_EXAMPLES
    response = client.messages.create(
        model=MODEL_DEV,
        max_tokens=10,  # chỉ cần đủ cho 1 label (vd "ESCALATION" là dài nhất)
        system=full_system,  # system prompt đã fix, kèm few-shot examples bọc XML tag
        messages=[{"role": "user", "content": f"<ticket>{ticket}</ticket>"}],
    )
    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# PHẦN 2 — Structured Outputs: JSON schema ở cấp API (output_config.format)
# ---------------------------------------------------------------------------

# CONTACT_SCHEMA: JSON schema mô tả chính xác field cần trích xuất.
# additionalProperties: False + required đầy đủ là bắt buộc để API compile
# được "grammar" ràng buộc decoding.
CONTACT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "email": {"type": "string"},
        "plan": {"type": "string"},
        "demo_requested": {"type": "boolean"},
    },
    "required": ["name", "email", "plan", "demo_requested"],
    "additionalProperties": False,
}


def extract_contact_structured(text: str) -> dict:
    """Trích xuất thông tin liên hệ, ép response luôn là JSON khớp CONTACT_SCHEMA."""
    # text: str — đoạn văn bản chứa thông tin cần trích xuất
    response = client.messages.create(
        model=MODEL_DEV,
        max_tokens=300,
        messages=[{"role": "user", "content": f"Extract info: {text}"}],
        output_config={
            "format": {
                "type": "json_schema",  # loại format: ràng buộc theo JSON schema
                "schema": CONTACT_SCHEMA,  # schema cụ thể — API constrain decoding theo đây
            }
        },
    )
    # output_config.format đảm bảo block đầu tiên là text chứa JSON hợp lệ theo
    # schema — nhưng vẫn phải check stop_reason trước khi tin response parse
    # được (refusal/max_tokens là 2 trường hợp response không khớp schema dù
    # đã bật structured outputs).
    if response.stop_reason == "refusal":
        raise RuntimeError("Model từ chối trả lời (refusal) — không có JSON để parse.")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Response bị cắt vì chạm max_tokens — JSON có thể chưa hoàn chỉnh.")
    text_block = next(b.text for b in response.content if b.type == "text")
    return json.loads(text_block)


# ---------------------------------------------------------------------------
# PHẦN 3 — Structured Outputs: Strict Tool Use (strict: true trên tool definition)
# ---------------------------------------------------------------------------

# BOOK_FLIGHT_TOOL: tool có strict=True — argument Claude truyền vào
# (destination, date, passengers) sẽ được validate khớp input_schema TRƯỚC KHI
# code tự viết chạy, tránh trường hợp model gửi input sai kiểu/thiếu field làm
# crash hàm xử lý.
BOOK_FLIGHT_TOOL = {
    "name": "book_flight",
    "description": "Book a flight to a destination",
    "strict": True,  # bật strict tool use — bắt buộc phải có additionalProperties: False + required
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


def request_flight_booking(user_request: str) -> dict:
    """Gửi yêu cầu đặt vé, trả về input (đã được validate) mà Claude gọi tool."""
    # user_request: str — câu yêu cầu đặt vé bằng ngôn ngữ tự nhiên
    response = client.messages.create(
        model=MODEL_DEV,
        max_tokens=300,
        messages=[{"role": "user", "content": user_request}],
        tools=[BOOK_FLIGHT_TOOL],  # chỉ khai báo 1 tool, có strict=True
    )
    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    return tool_use_block.input  # dict đã được API đảm bảo khớp input_schema


def main():
    print("=== PHẦN 1: Diagnosing Prompt Failures ===")
    print("--- Bare prompt (chưa chẩn đoán) — chạy vài lần để thấy output không nhất quán ---")
    try:
        for i in range(3):
            print(f"[bare #{i + 1}]", classify_bare(SAMPLE_TICKET))
    except anthropic.APIError as exc:
        print(f"API error (bare): {exc}")

    print("\n--- Fixed prompt (System Prompt + XML Tags + Few-shot) ---")
    try:
        for i in range(3):
            print(f"[fixed #{i + 1}]", classify_fixed(SAMPLE_TICKET))
    except anthropic.APIError as exc:
        print(f"API error (fixed): {exc}")

    print("\n=== PHẦN 2: Structured Outputs — JSON schema ===")
    try:
        contact = extract_contact_structured(
            "Jane Doe (jane@co.com) wants Enterprise, and wants a demo."
        )
        print(json.dumps(contact, indent=2))
    except (anthropic.APIError, RuntimeError, StopIteration) as exc:
        print(f"Lỗi Structured Outputs (JSON schema): {exc}")

    print("\n=== PHẦN 3: Structured Outputs — Strict Tool Use ===")
    try:
        booking_input = request_flight_booking(
            "Book a flight to Tokyo for 2 passengers on March 15, 2026."
        )
        print(json.dumps(booking_input, indent=2))
    except (anthropic.APIError, StopIteration) as exc:
        print(f"Lỗi Strict Tool Use: {exc}")


if __name__ == "__main__":
    main()
