"""Shared Anthropic client for study exercises.

Import `client`, `MODEL_DEV`, `MODEL_MAIN` from this module in exercise scripts
instead of re-initializing the SDK each time.
"""

import os  # đọc biến môi trường ANTHROPIC_API_KEY
import sys  # in lỗi ra stderr và set exit code khi health check thất bại

from anthropic import Anthropic  # SDK chính thức để gọi Claude API
from dotenv import load_dotenv  # load biến môi trường từ file .env

load_dotenv()  # đọc .env vào os.environ (phải gọi trước khi os.getenv bên dưới)

# Use MODEL_DEV for fast/cheap iteration, MODEL_MAIN for final/quality runs.
MODEL_DEV = "claude-haiku-4-5"  # model rẻ, tốc độ nhanh, dùng khi code/test
MODEL_MAIN = "claude-sonnet-4-6"  # model mạnh hơn, dùng khi cần chất lượng output tốt nhất

api_key = os.getenv("ANTHROPIC_API_KEY")  # lấy API key từ env, None nếu chưa set
if not api_key:
    # fail sớm và rõ ràng thay vì để lỗi khó hiểu khi gọi API sau này
    raise RuntimeError(
        "ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key."
    )

client = Anthropic(api_key=api_key)  # client dùng chung, import lại ở các exercise khác


def health_check() -> None:
    """Send a minimal request to confirm the API key and connection work."""
    try:
        response = client.messages.create(
            model=MODEL_DEV,  # dùng model rẻ vì chỉ cần test kết nối, không cần chất lượng cao
            max_tokens=64,  # response ngắn, chỉ cần xác nhận key hoạt động
            messages=[{"role": "user", "content": "Say 'ok' if you can hear me."}],
        )
        print("API key is valid. Response from Claude:")
        print(response.content[0].text)
    except Exception as exc:
        # bắt mọi lỗi (network, auth, ...) để in rõ ràng ra stderr rồi thoát với exit code 1
        print(f"Health check failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    health_check()
