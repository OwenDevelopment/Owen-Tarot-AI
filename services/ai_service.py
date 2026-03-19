import os

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class AIService:
    def __init__(self, api_key: str = "", model: str = "gpt-4o-mini"):
        self.api_key = (api_key or "").strip()
        self.model = (model or "gpt-4o-mini").strip()
        self.enabled = bool(self.api_key and OpenAI is not None)
        self.client = OpenAI(api_key=self.api_key) if self.enabled else None

    def _build_cards_text(self, cards):
        if not cards:
            return "Chưa có lá bài nào."

        lines = []
        for card in cards:
            orientation = "ngược" if card.get("reversed") else "xuôi"
            lines.append(
                f"- {card.get('position', 'Không rõ vị trí')}: "
                f"{card.get('name', 'Unknown')} ({orientation})\n"
                f"  Nghĩa xuôi: {card.get('meaning_up', '')}\n"
                f"  Nghĩa ngược: {card.get('meaning_rev', '')}\n"
                f"  Mô tả: {card.get('description', '')}"
            )
        return "\n".join(lines)

    def generate_reading(self, question: str, spread: str, cards: list):
        question = (question or "").strip()
        cards_text = self._build_cards_text(cards)

        if not self.enabled:
            return self._build_local_fallback(cards)

        prompt = f"""
Bạn là Owen, một reader tarot nói tiếng Việt, giọng ấm áp, rõ ràng, không mê tín quá đà.
Hãy diễn giải trải bài cho người dùng.

Câu hỏi: {question}
Số lá: {spread}

Các lá bài:
{cards_text}

Yêu cầu:
- Viết bằng tiếng Việt tự nhiên.
- Có cấu trúc rõ ràng.
- Giải thích lần lượt từng lá theo vị trí.
- Sau đó nối ý nghĩa các lá với nhau.
- Cuối cùng đưa ra 1 đoạn lời khuyên thực tế.
- Không dùng markdown quá rối, chỉ xuống dòng dễ đọc.
- Độ dài vừa phải, khoảng 220-450 từ.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Bạn là Owen, một người diễn giải tarot tinh tế, ấm áp, sâu sắc và thực tế."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.8,
            )

            text = response.choices[0].message.content.strip()
            return text if text else self._build_local_fallback(cards)

        except Exception:
            return self._build_local_fallback(cards)

    def generate_chat_reply(self, message: str, context: list, cards: list, question: str, spread: str, latest_reading: str):
        message = (message or "").strip()
        if not message:
            return "Bạn cứ nhắn điều bạn đang muốn hỏi, mình sẽ cùng bạn nhìn sâu hơn vào trải bài."

        if not self.enabled:
            return self._fallback_chat(message, cards, latest_reading)

        cards_text = self._build_cards_text(cards)

        context_lines = []
        for item in context[-10:]:
            if item.get("type") == "chat":
                role = "Người dùng" if item.get("role") == "user" else "Owen"
                context_lines.append(f"{role}: {item.get('content', '')}")
            elif item.get("type") == "reading":
                context_lines.append(
                    f"Trải bài trước | câu hỏi: {item.get('question', '')} | spread: {item.get('spread', '')} | reading: {item.get('reading', '')}"
                )

        context_text = "\n".join(context_lines).strip() or "Không có ngữ cảnh trước đó."

        prompt = f"""
Bạn là Owen AI, đang tiếp tục trò chuyện về một trải bài tarot với người dùng.

Câu hỏi gốc của người dùng:
{question}

Trải bài hiện tại:
{spread} lá

Các lá hiện tại:
{cards_text}

Diễn giải gần nhất:
{latest_reading or "Chưa có."}

Ngữ cảnh cuộc trò chuyện:
{context_text}

Tin nhắn mới của người dùng:
{message}

Yêu cầu:
- Trả lời bằng tiếng Việt.
- Bám sát trải bài hiện tại.
- Nếu người dùng hỏi sâu về 1 lá, hãy giải thích lá đó trong bối cảnh câu hỏi gốc.
- Nếu người dùng hỏi chung, hãy nối các lá với nhau.
- Giọng tự nhiên, tinh tế, dễ hiểu.
- Không nói lan man.
- Kết thúc bằng 1 câu gợi mở nhẹ nếu phù hợp.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Bạn là Owen AI, chuyên trò chuyện tiếp nối sau khi người dùng rút bài tarot."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.85,
            )

            text = response.choices[0].message.content.strip()
            if text:
                return text

            return self._fallback_chat(message, cards, latest_reading)

        except Exception:
            return self._fallback_chat(message, cards, latest_reading)

    def _build_local_fallback(self, cards: list):
        if not cards:
            return "Hiện chưa có trải bài để diễn giải."

        parts = []
        for card in cards:
            position = card.get("position", "Vị trí")
            name = card.get("name", "Lá bài")
            reversed_flag = card.get("reversed", False)
            meaning = card.get("meaning_rev", "") if reversed_flag else card.get("meaning_up", "")
            orientation = "ngược" if reversed_flag else "xuôi"

            parts.append(f"{position} – {name} ({orientation}): {meaning}")

        return (
            "Mình đang nhìn thấy năng lượng chính của trải bài như sau:\n\n"
            + "\n".join(parts)
            + "\n\nTổng thể, đây là một trải bài cho thấy bạn nên nhìn rõ điều đang diễn ra ở hiện tại, "
              "đừng chỉ phản ứng theo cảm xúc nhất thời. Khi hiểu đúng tín hiệu của từng lá, hướng đi tiếp theo sẽ sáng hơn."
        )

    def _fallback_chat(self, message: str, cards: list, latest_reading: str):
        if cards:
            card_names = ", ".join(card.get("name", "lá bài") for card in cards[:3])
            return (
                f"Mình vẫn đang bám theo trải bài hiện tại của bạn. Nổi bật nhất lúc này là: {card_names}.\n\n"
                f"Bạn vừa hỏi: “{message}”.\n\n"
                f"{latest_reading or 'Bạn thử hỏi sâu hơn về một lá cụ thể hoặc mối liên hệ giữa các lá nhé.'}"
            )

        return (
            f"Mình đã nhận được điều bạn hỏi: “{message}”. "
            "Hãy rút bài trước, rồi mình sẽ bám sát trải bài để phân tích sâu hơn cho bạn."
        )