"""
Exercise 02: Memory scope + Skills — state nào sống sau khi session kết thúc
Domain: Agents and Workflows
Objective:
    1. Encode quy tắc chọn memory scope Ở DESIGN PHASE:
       choose_memory_scope(...) -> "stateless" | "in_context" | "external_storage" | "summarized".
    2. Implement 4 memory backend cho CÙNG 1 agent tí hon (chat 1 lượt hỏi–đáp):
       - StatelessMemory      : không load, không lưu.
       - InContextMemory      : history sống trong RAM của process, mất khi process thoát.
       - ExternalStorageMemory: history ghi/đọc ra file JSON (đại diện cho DB) -> sống qua session.
       - SummarizedMemory     : nén history cũ thành 1 đoạn tóm tắt, inject đầu session sau.
    3. Đo token của "history được gửi lên" qua từng turn bằng client.messages.count_tokens ->
       minh hoạ "in-context: token cost tăng dần mỗi turn".
    4. Encode quy tắc chọn nơi đặt instruction tái sử dụng:
       choose_instruction_home(...) -> "skill" | "claude_md" | "in_context".
    5. main(): chạy 3 turn với external-storage + summarized, in bảng token, in 3 quyết định scope.

Chạy được với 1 API key thường. Không có tool call, không HITL (đây là bài về MEMORY, không phải loop).
"""
import sys                              # ép stdout UTF-8 (console Windows mặc định cp1252)
import json                             # serialize history ra file cho ExternalStorageMemory
import pathlib                          # xử lý path file state, không phụ thuộc cwd tuyệt đối
from dotenv import load_dotenv          # nạp ANTHROPIC_API_KEY từ .env, KHÔNG hardcode
import anthropic                        # SDK chính thức của Anthropic

# Console Windows mặc định cp1252 -> print tiếng Việt raise UnicodeEncodeError.
# reconfigure() ép stdout dùng UTF-8; errors="replace" để không bao giờ crash vì ký tự lạ.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()                           # đọc .env vào biến môi trường
client = anthropic.Anthropic()         # client tự lấy key từ env

# Rule 1 CLAUDE.md: haiku cho bài tập dev/test.
MODEL = "claude-haiku-4-5"

# File "database giả" cho ExternalStorageMemory — để cạnh file bài tập cho dễ xoá.
# Trong thực tế đây là 1 row trong Postgres / Redis / DynamoDB, không phải file phẳng.
STATE_FILE = pathlib.Path(__file__).with_name("02_session_state.json")

# System prompt scope hẹp: agent chỉ là trợ lý ghi nhớ sở thích của user qua nhiều phiên.
SYSTEM_PROMPT = (
    "Bạn là trợ lý cá nhân. Trả lời NGẮN GỌN (1-2 câu). "
    "Nếu người dùng đã cho biết sở thích ở phiên trước, hãy dùng lại thông tin đó."
)


# ===========================================================================
# PHẦN 1 — choose_memory_scope: quyết định Ở DESIGN PHASE, không phải lúc refactor
# ===========================================================================
def choose_memory_scope(needs_state_across_sessions: bool,
                        conversation_outgrows_context_window: bool,
                        session_short_and_disposable: bool) -> str:
    """
    Map 3 đặc điểm task -> 1 memory scope. Đây là quyết định design-time:
    quyết đúng lúc này thì rẻ; refactor lúc production (kéo state ra external storage)
    tuy mechanical nhưng đắt vì phải làm dưới deadline.

    Tham số:
        needs_state_across_sessions:
            Task có cần nhớ gì đó SAU KHI session kết thúc không?
            (agent phục vụ cùng 1 user qua nhiều ngày -> True;
             agent nhận 1 job làm xong đóng lại -> False)
        conversation_outgrows_context_window:
            Hội thoại có dài tới mức full history vượt context budget trước khi xong không?
            (long-running conversational agent -> True)
        session_short_and_disposable:
            Session có ngắn, mọi state vừa context window, và KHÔNG cần sống qua restart không?

    Trả về: "stateless" | "in_context" | "external_storage" | "summarized"
    """
    # (1) Không cần nhớ gì qua session => stateless. Không overhead, mỗi session độc lập.
    #     Đúng cho task-execution agent / pipeline mỗi bước độc lập theo thiết kế.
    if not needs_state_across_sessions and not conversation_outgrows_context_window:
        if session_short_and_disposable:
            # Session ngắn, cần nhớ trong phiên nhưng không cần sống qua restart => in-context là đủ.
            return "in_context"
        return "stateless"

    # (2) Cần nhớ qua session VÀ hội thoại sẽ phình vượt window
    #     => summarized: nén history cũ thành tóm tắt, chấp nhận rơi chi tiết summarizer bỏ.
    if conversation_outgrows_context_window:
        return "summarized"

    # (3) Cần nhớ qua session, chuyển giữa user, hoặc share giữa nhiều agent instance
    #     => external storage. Trả giá bằng retrieval latency mỗi call + read/write logic tự viết.
    return "external_storage"


# ===========================================================================
# PHẦN 2 — 4 memory backend cho cùng 1 agent
# ===========================================================================
def _ask_claude(messages: list) -> str:
    """
    Gọi 1 lượt Messages API với danh sách `messages` cho sẵn, trả text câu trả lời.
    Tách riêng để 4 backend chỉ khác nhau ở CHỖ history đến từ đâu / đi về đâu,
    không khác nhau ở cách gọi model.
    """
    resp = client.messages.create(
        model=MODEL,
        max_tokens=300,                 # câu trả lời ngắn, đủ cho bài demo
        system=SYSTEM_PROMPT,           # system là top-level param, KHÔNG nằm trong messages
        messages=messages,
    )
    # resp.content là list content block; ở đây không có tool nên chỉ có 1 block text.
    return resp.content[0].text


def _count_history_tokens(messages: list) -> int:
    """
    Đếm số token của phần history sẽ được GỬI LÊN (system + messages).
    Dùng để minh hoạ: in-context memory làm token gửi lên tăng dần mỗi turn.
    count_tokens là 1 API call riêng, KHÔNG tính phí generation.
    """
    r = client.messages.count_tokens(
        model=MODEL,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return r.input_tokens


class StatelessMemory:
    """
    Scope: no persistent memory.
    Không load gì lúc start, không lưu gì lúc end. Mỗi turn chỉ có đúng câu user vừa gõ.
    Java liên tưởng: 1 method static thuần, không field, không cache.
    """

    def turn(self, user_msg: str) -> tuple[str, int]:
        messages = [{"role": "user", "content": user_msg}]   # KHÔNG có gì trước đó
        tokens = _count_history_tokens(messages)             # ~ cố định mọi turn
        return _ask_claude(messages), tokens


class InContextMemory:
    """
    Scope: in-context memory.
    History sống trong self.messages (RAM của process). Sống qua các turn TRONG 1 lần chạy,
    mất sạch khi process thoát / tạo instance mới.
    Java liên tưởng: 1 ArrayList<Message> là field của object, không persist ra đâu.
    """

    def __init__(self):
        self.messages: list = []                             # session mới = list rỗng = quên hết

    def turn(self, user_msg: str) -> tuple[str, int]:
        self.messages.append({"role": "user", "content": user_msg})
        tokens = _count_history_tokens(self.messages)        # TĂNG DẦN mỗi turn -> bill phình
        answer = _ask_claude(self.messages)
        self.messages.append({"role": "assistant", "content": answer})
        return answer, tokens


class ExternalStorageMemory:
    """
    Scope: external storage.
    History đọc từ file JSON lúc start (đại diện DB), ghi lại sau mỗi turn -> SỐNG QUA SESSION.
    Cái giá: mỗi lần _load/_save là 1 I/O (trong thực tế là network round-trip tới DB) + bạn
    tự chịu trách nhiệm read/write logic, schema, migration...
    Java liên tưởng: 1 Repository đọc/ghi Room DB; object không giữ state, DB giữ.
    """

    def __init__(self, store: pathlib.Path):
        self.store = store

    def _load(self) -> list:
        # Đọc lại history lúc session start (hoặc on-demand). Latency nằm ở đây.
        if self.store.exists():
            return json.loads(self.store.read_text(encoding="utf-8"))
        return []

    def _save(self, messages: list) -> None:
        # Ghi lại toàn bộ history. Thực tế thường chỉ append delta, không rewrite cả blob.
        self.store.write_text(json.dumps(messages, ensure_ascii=False, indent=2),
                              encoding="utf-8")

    def turn(self, user_msg: str) -> tuple[str, int]:
        messages = self._load()                              # <- khác stateless: có history cũ
        messages.append({"role": "user", "content": user_msg})
        tokens = _count_history_tokens(messages)
        answer = _ask_claude(messages)
        messages.append({"role": "assistant", "content": answer})
        self._save(messages)                                 # <- persist để session sau đọc được
        return answer, tokens


class SummarizedMemory:
    """
    Scope: summarized memory.
    Thay vì replay full history, giữ 1 đoạn tóm tắt cô đọng (self.summary) + chỉ vài turn gần nhất.
    Token/session thấp hơn full history, nhưng MẤT bất kỳ chi tiết nào summarizer prompt không giữ.
    Chất lượng phụ thuộc hoàn toàn vào summarizer prompt được đặc tả kỹ tới đâu.
    Java liên tưởng: nén log cũ thành 1 dòng "digest" rồi xoá log gốc — không khôi phục lại được.
    """

    def __init__(self, keep_recent_turns: int = 1):
        self.summary: str = ""                               # tóm tắt tích luỹ của mọi turn cũ
        self.recent: list = []                               # vài message gần nhất giữ nguyên văn
        self.keep_recent_turns = keep_recent_turns           # số cặp user/assistant giữ raw

    def _build_messages(self, user_msg: str) -> list:
        msgs: list = []
        if self.summary:
            # Inject tóm tắt phiên trước như context ở đầu — đây là "injected at start of next session".
            msgs.append({"role": "user",
                         "content": f"[Bối cảnh các phiên trước — đã tóm tắt]\n{self.summary}"})
            msgs.append({"role": "assistant", "content": "Đã nắm bối cảnh."})
        msgs.extend(self.recent)                             # + vài turn gần nhất nguyên văn
        msgs.append({"role": "user", "content": user_msg})
        return msgs

    def _resummarize(self, user_msg: str, answer: str) -> None:
        """Nén (summary cũ + turn vừa xong) thành summary mới. Đây là bước làm rơi chi tiết."""
        material = (f"Tóm tắt hiện có:\n{self.summary or '(chưa có)'}\n\n"
                    f"Lượt mới:\nUser: {user_msg}\nAssistant: {answer}")
        # Summarizer prompt: nêu RÕ cái phải giữ, nếu không state task-critical sẽ bị bỏ.
        self.summary = _ask_claude([{
            "role": "user",
            "content": ("Cập nhật bản tóm tắt hội thoại dưới đây. BẮT BUỘC giữ lại mọi "
                        "sở thích, quyết định, và ràng buộc người dùng đã nêu. Tối đa 3 câu.\n\n"
                        + material),
        }])

    def turn(self, user_msg: str) -> tuple[str, int]:
        messages = self._build_messages(user_msg)
        tokens = _count_history_tokens(messages)             # ~ ổn định, không phình như in-context
        answer = _ask_claude(messages)

        # Cập nhật recent buffer (giữ tối đa keep_recent_turns cặp = 2*n message).
        self.recent.append({"role": "user", "content": user_msg})
        self.recent.append({"role": "assistant", "content": answer})
        overflow = len(self.recent) - 2 * self.keep_recent_turns
        if overflow > 0:
            self.recent = self.recent[overflow:]            # phần bị đẩy ra sẽ chỉ còn trong summary

        self._resummarize(user_msg, answer)
        return answer, tokens


# ===========================================================================
# PHẦN 3 — choose_instruction_home: Skill vs CLAUDE.md vs in-context
# ===========================================================================
def choose_instruction_home(applies_to_every_task_in_repo: bool,
                            reused_across_many_sessions: bool,
                            one_off_single_conversation: bool) -> str:
    """
    Quyết định đặt 1 bộ instruction tái sử dụng ở đâu.

    - "claude_md"  : chuẩn always-on, đúng với MỌI task trong codebase (coding convention,
                     format rule bắt buộc). Load vào mọi session -> overhead cố định.
    - "skill"      : expertise theo 1 LOẠI task cụ thể, không nên phình session không liên quan.
                     Chỉ name + description tốn context lúc startup; full body load khi khớp.
    - "in_context" : chỉ dùng 1 lần trong 1 conversation, không cần sống qua session.

    Lưu ý: subagent KHÔNG tự inherit Skill / history từ parent (phải khai báo explicit),
    nhưng CÓ inherit permission context.
    """
    if applies_to_every_task_in_repo:
        return "claude_md"
    if reused_across_many_sessions and not one_off_single_conversation:
        return "skill"
    return "in_context"


# ===========================================================================
# PHẦN 4 — main
# ===========================================================================
def main() -> None:
    # --- 4.1 Ba quyết định memory scope điển hình -----------------------------
    scope_scenarios = [
        # (mô tả, needs_state_across_sessions, outgrows_window, short_disposable)
        ("Trợ lý cá nhân dùng hằng ngày, nhớ sở thích qua nhiều ngày", True, False, False),
        ("Agent phân loại 1 batch ticket rồi kết thúc", False, False, False),
        ("Chatbot hỗ trợ, phiên rất dài, history sẽ vượt window", True, True, False),
    ]
    print("=== choose_memory_scope ===")
    for desc, a, b, c in scope_scenarios:
        print(f"  {desc}\n    -> {choose_memory_scope(a, b, c)}")

    # --- 4.2 choose_instruction_home ---------------------------------------
    print("\n=== choose_instruction_home ===")
    print("  Coding convention áp cho mọi file      ->",
          choose_instruction_home(True, True, False))
    print("  Checklist review bảo mật (1 loại task) ->",
          choose_instruction_home(False, True, False))
    print("  Hướng dẫn cho đúng câu hỏi lúc này     ->",
          choose_instruction_home(False, False, True))

    # --- 4.3 Chạy thật 3 turn: external storage vs summarized --------------
    turns = [
        "Tôi thích cà phê đen không đường.",
        "Sáng nay trời lạnh, gợi ý đồ uống cho tôi đi.",
        "Nhắc lại giúp tôi: tôi thích uống gì?",
    ]

    STATE_FILE.unlink(missing_ok=True)          # xoá state cũ để demo bắt đầu từ phiên trắng
    external = ExternalStorageMemory(STATE_FILE)
    summarized = SummarizedMemory(keep_recent_turns=1)

    print("\n=== 3 turn — token history GỬI LÊN qua từng turn ===")
    print(f"{'turn':<6}{'external_storage':<20}{'summarized':<14}")
    for i, msg in enumerate(turns, 1):
        ans_ext, tok_ext = external.turn(msg)
        ans_sum, tok_sum = summarized.turn(msg)
        print(f"{i:<6}{tok_ext:<20}{tok_sum:<14}")
        print(f"   user      : {msg}")
        print(f"   external  : {ans_ext.strip()}")
        print(f"   summarized: {ans_sum.strip()}")

    # Kỳ vọng: cột external_storage tăng dần (replay full history);
    #          cột summarized ổn định hơn (history cũ bị nén thành ~3 câu).
    print(f"\n(state ngoài đã ghi tại: {STATE_FILE.name} — xoá file này = 'clear' phiên)")


if __name__ == "__main__":
    main()
