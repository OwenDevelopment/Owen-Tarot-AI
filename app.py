import json
import math
import sqlite3
import traceback
from datetime import datetime
from html import escape

from flask import Flask, redirect, render_template, request, session, jsonify, Response
from config import Config
from services.tarot_service import draw_cards, attach_positions, build_local_reading, card_to_slug, normalize_card_image_map
from services.db_service import init_db, save_reading, save_chat_message, get_recent_context
from services.ai_service import AIService

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = app.config["SECRET_KEY"]

with open("tarot_data.json", "r", encoding="utf-8") as f:
    CARDS_DATA = json.load(f)

with open("card_data.json", "r", encoding="utf-8") as f:
    raw_tarot_data = json.load(f)

if isinstance(raw_tarot_data, dict):
    tarot_data = raw_tarot_data.get("cards", [])
else:
    tarot_data = raw_tarot_data

image_map = normalize_card_image_map(raw_tarot_data)

init_db(app.config["DATABASE_PATH"])

ai_service = AIService(
    api_key=app.config["OPENAI_API_KEY"],
    model=app.config["OPENAI_MODEL"]
)


def get_session_id() -> str:
    if "session_id" not in session:
        session["session_id"] = datetime.now().strftime("%Y%m%d%H%M%S%f")
    return session["session_id"]


def is_json_request() -> bool:
    return request.is_json or "application/json" in (request.headers.get("Content-Type", ""))


def get_current_cards():
    last_result = session.get("last_result")
    if isinstance(last_result, dict):
        return last_result.get("cards", [])
    return []


def get_current_spread():
    last_result = session.get("last_result")
    if isinstance(last_result, dict):
        return last_result.get("spread", "1")
    return "1"


def get_current_question():
    last_result = session.get("last_result")
    if isinstance(last_result, dict):
        return last_result.get("question", "")
    return ""


def get_image_by_name(name: str):
    target = name.strip().lower()

    aliases = {
        "strength": "fortitude",
        "judgement": "the last judgment",
        "wheel of fortune": "wheel of fortune",
    }

    target = aliases.get(target, target)

    for card in tarot_data:
        if not isinstance(card, dict):
            continue

        card_name = str(card.get("name", "")).strip().lower()
        if card_name == target:
            short_name = str(card.get("name_short", "")).strip().lower()
            if short_name:
                return f"https://sacred-texts.com/tarot/pkt/img/{short_name}.jpg"

    return None


def enrich_cards(cards):
    for c in cards:
        if "slug" not in c or not c["slug"]:
            c["slug"] = card_to_slug(c["name"])

        c["image"] = get_image_by_name(c.get("name", ""))
    return cards


def build_followup_suggestions(result):
    if not result:
        return [
            "Mình nên hỏi điều gì về chuyện tình cảm hiện tại?",
            "Điều mình cần tập trung nhất lúc này là gì?",
            "Nếu rút 3 lá thì mình nên hỏi theo hướng nào?",
        ]

    cards = result.get("cards", []) or []
    question = result.get("question", "")
    suggestions = []

    if cards:
        first_card = cards[0].get("name", "lá đầu tiên")
        suggestions.append(f"Giải thích kỹ hơn lá {first_card} giúp mình")
        suggestions.append("Trải bài này đang muốn nhắn mình điều gì quan trọng nhất?")

        if len(cards) >= 3:
            suggestions.append("Ba lá này liên kết với nhau như thế nào?")
            suggestions.append("Lá nào trong trải bài là lời khuyên mạnh nhất cho mình?")
        else:
            suggestions.append("Lá này ảnh hưởng thế nào đến thời gian tới của mình?")

    if question:
        suggestions.append("Nếu nhìn sâu hơn vào câu hỏi này thì điều mình chưa thấy là gì?")

    seen = set()
    cleaned = []
    for item in suggestions:
        if item not in seen:
            cleaned.append(item)
            seen.add(item)
    return cleaned[:4]


@app.route("/", methods=["GET", "POST"])
def index():
    error_message = None
    session_id = get_session_id()

    if request.method == "POST":
        question = (request.form.get("question") or "").strip()
        spread = (request.form.get("spread") or "1").strip()

        if not question:
            error_message = "Bạn cần nhập câu hỏi trước khi rút bài."
        else:
            try:
                if spread == "10":
                    card_count = 10
                elif spread == "3":
                    card_count = 3
                else:
                    card_count = 1

                cards = draw_cards(CARDS_DATA, card_count, image_map=image_map)
                cards = attach_positions(cards)
                cards = enrich_cards(cards)

                reading = ai_service.generate_reading(
                    question=question,
                    spread=spread,
                    cards=cards
                )

                used_ai = bool(ai_service.enabled)

                result = {
                    "question": question,
                    "spread": spread,
                    "cards": cards,
                    "reading": reading,
                    "used_ai": used_ai,
                }

                save_reading(
                    app.config["DATABASE_PATH"],
                    session_id=session_id,
                    question=question,
                    spread=spread,
                    cards_json=json.dumps(cards, ensure_ascii=False),
                    reading_text=reading,
                    used_ai=1 if used_ai else 0,
                )

                session["last_result"] = result
                return redirect("/")

            except Exception as e:
                print("DRAW ERROR:", e)
                traceback.print_exc()
                error_message = f"Có lỗi xảy ra khi rút bài: {e}"

    result = session.get("last_result")
    history = get_recent_context(app.config["DATABASE_PATH"], session_id, limit=10)
    chat_history = [item for item in history if item.get("type") == "chat"]
    suggestions = build_followup_suggestions(result)
    selected_spread = get_current_spread()

    return render_template(
        "index.html",
        result=result,
        error_message=error_message,
        ai_enabled=ai_service.enabled,
        history=chat_history,
        suggestions=suggestions,
        selected_spread=selected_spread,
    )


@app.route("/chat", methods=["POST"])
def chat():
    session_id = get_session_id()

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or request.form.get("message") or "").strip()

    if not message:
        return jsonify({"reply": "Bạn chưa nhập gì để mình trả lời."}), 400

    save_chat_message(app.config["DATABASE_PATH"], session_id, role="user", content=message)

    if not ai_service.enabled:
        reply = "Hiện chat AI chưa bật. Bạn vẫn có thể rút bài và xem local reading."
        save_chat_message(app.config["DATABASE_PATH"], session_id, role="assistant", content=reply)
        return jsonify({"reply": reply})

    try:
        context = get_recent_context(app.config["DATABASE_PATH"], session_id, limit=12)
        current_cards = get_current_cards()
        latest_result = session.get("last_result") or {}

        reply = ai_service.generate_chat_reply(
            message=message,
            context=context,
            cards=current_cards,
            question=get_current_question(),
            spread=get_current_spread(),
            latest_reading=latest_result.get("reading", ""),
        )

        if not reply or not str(reply).strip():
            raise ValueError("Empty AI reply")

        save_chat_message(app.config["DATABASE_PATH"], session_id, role="assistant", content=reply)
        return jsonify({"reply": reply})

    except Exception as e:
        print("CHAT AI ERROR:", e)

        current_cards = get_current_cards()
        latest_result = session.get("last_result") or {}
        latest_reading = latest_result.get("reading", "")

        if current_cards:
            card_names = ", ".join(card.get("name", "lá bài") for card in current_cards[:3])
            reply = (
                f"Mình vẫn đang bám theo trải bài hiện tại của bạn. "
                f"Lúc này nổi bật nhất là: {card_names}. "
                f"Bạn vừa hỏi: “{message}”.\n\n"
                f"{latest_reading[:500] if latest_reading else 'Bạn thử hỏi sâu hơn về một lá cụ thể hoặc mối liên hệ giữa các lá nhé.'}"
            )
        else:
            reply = (
                "Mình đã nhận được câu hỏi của bạn, nhưng hiện Owen chưa kết nối ổn định với phần phân tích sâu. "
                "Bạn vẫn có thể rút bài trước, rồi mình sẽ bám theo trải bài để phân tích kỹ hơn."
            )

        save_chat_message(app.config["DATABASE_PATH"], session_id, role="assistant", content=reply)
        return jsonify({"reply": reply})


@app.route("/clear-history", methods=["POST"])
def clear_history():
    session_id = get_session_id()

    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    cur = conn.cursor()
    cur.execute("DELETE FROM readings WHERE session_id = ?", (session_id,))
    cur.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

    session.pop("last_result", None)

    if is_json_request():
        return jsonify({"ok": True})

    return redirect("/")


@app.route("/clear-chat", methods=["POST"])
def clear_chat():
    session_id = get_session_id()

    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    cur = conn.cursor()
    cur.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

    if is_json_request():
        return jsonify({"ok": True})

    return redirect("/")


@app.route("/card-image/<slug>")
def card_image(slug: str):
    title = slug.replace("-", " ").title()
    safe_title = escape(title)
    safe_slug = escape(slug.upper())

    major_icons = {
        "the-fool": "✦",
        "the-magician": "✧",
        "the-high-priestess": "☾",
        "the-empress": "❀",
        "the-emperor": "▲",
        "the-hierophant": "✠",
        "the-lovers": "♥",
        "the-chariot": "▣",
        "strength": "♌",
        "the-hermit": "☼",
        "wheel-of-fortune": "◌",
        "justice": "⚖",
        "the-hanged-man": "☥",
        "death": "☠",
        "temperance": "⚗",
        "the-devil": "♄",
        "the-tower": "🜂",
        "the-star": "★",
        "the-moon": "☽",
        "the-sun": "☀",
        "judgement": "♫",
        "the-world": "◎",
    }

    def parse_card_info(slug_value: str):
        parts = slug_value.split("-of-")
        if len(parts) == 2:
            rank_slug = parts[0]
            suit_slug = parts[1]

            rank_map = {
                "ace": 1,
                "two": 2,
                "three": 3,
                "four": 4,
                "five": 5,
                "six": 6,
                "seven": 7,
                "eight": 8,
                "nine": 9,
                "ten": 10,
                "page": 11,
                "knight": 12,
                "queen": 13,
                "king": 14,
            }

            return {
                "is_minor": True,
                "rank_slug": rank_slug,
                "suit_slug": suit_slug,
                "rank_value": rank_map.get(rank_slug, 0),
            }

        return {
            "is_minor": False,
            "rank_slug": "",
            "suit_slug": "",
            "rank_value": 0,
        }

    card_info = parse_card_info(slug)

    if card_info["is_minor"]:
        suit_slug = card_info["suit_slug"]
        rank_slug = card_info["rank_slug"]
        rank_value = card_info["rank_value"]

        suit_label_map = {
            "cups": "CUPS",
            "swords": "SWORDS",
            "wands": "WANDS",
            "pentacles": "PENTACLES",
        }

        suit_symbol_map = {
            "cups": "C",
            "swords": "S",
            "wands": "W",
            "pentacles": "P",
        }

        suit_label = suit_label_map.get(suit_slug, "TAROT")

        suit_colors = {
            "cups": ("#6ecbff", "#2c7be5"),
            "swords": ("#d7def7", "#8fa4e8"),
            "wands": ("#ffb36b", "#ff7b39"),
            "pentacles": ("#f4db7d", "#caa85c"),
        }

        c1, c2 = suit_colors.get(suit_slug, ("#d7c793", "#8a5cff"))

        rank_text_map = {
            "ace": "ACE",
            "two": "II",
            "three": "III",
            "four": "IV",
            "five": "V",
            "six": "VI",
            "seven": "VII",
            "eight": "VIII",
            "nine": "IX",
            "ten": "X",
            "page": "PAGE",
            "knight": "KNIGHT",
            "queen": "QUEEN",
            "king": "KING",
        }

        rank_text = rank_text_map.get(rank_slug, "")
        center_symbol = suit_symbol_map.get(suit_slug, "T")

        symbols_svg = ""

        if 1 <= rank_value <= 10:
            cols = 2 if rank_value <= 4 else 3 if rank_value <= 6 else 4
            rows = math.ceil(rank_value / cols)
            start_x = 160 - ((cols - 1) * 46) / 2
            start_y = 192
            index = 0

            for r in range(rows):
                for c in range(cols):
                    if index >= rank_value:
                        break
                    x = start_x + c * 46
                    y = start_y + r * 48
                    symbols_svg += f'''
  <circle cx="{x}" cy="{y}" r="18" fill="rgba(255,255,255,0.04)" stroke="{c1}" stroke-opacity="0.55"/>
  <text x="{x}" y="{y + 7}" text-anchor="middle" fill="{c1}" font-size="20" font-family="Georgia, serif" font-weight="700">{center_symbol}</text>
'''
                    index += 1
        else:
            figure_map = {
                11: ("PAGE", 160, 210, 34),
                12: ("KNIGHT", 160, 210, 32),
                13: ("QUEEN", 160, 210, 32),
                14: ("KING", 160, 210, 34),
            }
            figure_text, fx, fy, fs = figure_map.get(rank_value, ("COURT", 160, 210, 30))
            symbols_svg = f'''
  <circle cx="160" cy="200" r="56" fill="rgba(255,255,255,0.03)" stroke="{c1}" stroke-width="2"/>
  <circle cx="160" cy="200" r="22" fill="url(#minorAccent)"/>
  <text x="{fx}" y="{fy + 70}" text-anchor="middle" fill="{c1}" font-size="{fs}" font-family="Georgia, serif" font-weight="700">{figure_text}</text>
  <text x="160" y="178" text-anchor="middle" fill="#fff4cf" font-size="28" font-family="Georgia, serif" font-weight="700">{center_symbol}</text>
'''

        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="320" height="520" viewBox="0 0 320 520">
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#130b25"/>
      <stop offset="45%" stop-color="#26134a"/>
      <stop offset="100%" stop-color="#120a22"/>
    </linearGradient>
    <linearGradient id="gold" x1="0" x2="1">
      <stop offset="0%" stop-color="#caa85c"/>
      <stop offset="50%" stop-color="#f5e1a4"/>
      <stop offset="100%" stop-color="#b88b3f"/>
    </linearGradient>
    <linearGradient id="minorAccent" x1="0" x2="1">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="100%" stop-color="{c2}"/>
    </linearGradient>
    <filter id="shadow">
      <feDropShadow dx="0" dy="10" stdDeviation="10" flood-color="#000000" flood-opacity="0.35"/>
    </filter>
  </defs>

  <rect x="10" y="10" width="300" height="500" rx="24" fill="url(#bg)" stroke="url(#gold)" stroke-width="5" filter="url(#shadow)"/>
  <rect x="26" y="26" width="268" height="468" rx="18" fill="none" stroke="#e7d39b" stroke-opacity="0.75" stroke-width="2"/>

  <circle cx="160" cy="78" r="26" fill="none" stroke="url(#minorAccent)" stroke-width="3"/>
  <circle cx="160" cy="78" r="10" fill="url(#minorAccent)"/>

  <text x="160" y="124" text-anchor="middle" fill="#fff4cf" font-size="24" font-family="Georgia, serif" font-weight="700">{safe_title}</text>
  <text x="160" y="148" text-anchor="middle" fill="{c1}" font-size="12" font-family="Arial, sans-serif" font-weight="700">{suit_label}</text>
  <text x="160" y="166" text-anchor="middle" fill="#d7c793" font-size="11" font-family="Arial, sans-serif">{rank_text}</text>

  {symbols_svg}

  <path d="M78 390 C110 348, 210 348, 242 390" fill="none" stroke="url(#gold)" stroke-width="2" opacity="0.85"/>
  <path d="M105 414 C130 382, 190 382, 215 414" fill="none" stroke="url(#gold)" stroke-width="2" opacity="0.55"/>

  <text x="160" y="452" text-anchor="middle" fill="#fff4cf" font-size="20" font-family="Georgia, serif" font-weight="700">{safe_title}</text>
  <text x="160" y="476" text-anchor="middle" fill="{c1}" font-size="11" font-family="Arial, sans-serif">{safe_slug}</text>
</svg>"""
        return Response(svg, content_type="image/svg+xml; charset=utf-8")

    icon = major_icons.get(slug, "✦")

    major_color_map = {
        "the-fool": ("#ffe38a", "#ffb347"),
        "the-magician": ("#ff9ac6", "#d66bff"),
        "the-high-priestess": ("#9ec5ff", "#7c8cff"),
        "the-empress": ("#ffb3d1", "#ff86b7"),
        "the-emperor": ("#ffb37a", "#ff7f50"),
        "the-hierophant": ("#e5d1ff", "#b28cff"),
        "the-lovers": ("#ff98b2", "#ff6f91"),
        "the-chariot": ("#9ee7ff", "#4db8ff"),
        "strength": ("#ffd36a", "#ff9f43"),
        "the-hermit": ("#fff2b3", "#ffd166"),
        "wheel-of-fortune": ("#ffe28a", "#f4a261"),
        "justice": ("#d9e4ff", "#98a8ff"),
        "the-hanged-man": ("#b8f2e6", "#70d6c2"),
        "death": ("#d9d9d9", "#9b9b9b"),
        "temperance": ("#ffe8b3", "#ffbf69"),
        "the-devil": ("#ff9f9f", "#ff5d73"),
        "the-tower": ("#ffb4a2", "#ff7f50"),
        "the-star": ("#a0e7ff", "#7b9cff"),
        "the-moon": ("#b5c7ff", "#8f9fff"),
        "the-sun": ("#ffe66d", "#ffb703"),
        "judgement": ("#d7f9ff", "#8ecae6"),
        "the-world": ("#d6ffd6", "#8bd17c"),
    }

    c1, c2 = major_color_map.get(slug, ("#d7c793", "#8a5cff"))

    number_map = {
        "the-fool": "0",
        "the-magician": "I",
        "the-high-priestess": "II",
        "the-empress": "III",
        "the-emperor": "IV",
        "the-hierophant": "V",
        "the-lovers": "VI",
        "the-chariot": "VII",
        "strength": "VIII",
        "the-hermit": "IX",
        "wheel-of-fortune": "X",
        "justice": "XI",
        "the-hanged-man": "XII",
        "death": "XIII",
        "temperance": "XIV",
        "the-devil": "XV",
        "the-tower": "XVI",
        "the-star": "XVII",
        "the-moon": "XVIII",
        "the-sun": "XIX",
        "judgement": "XX",
        "the-world": "XXI",
    }

    major_number = number_map.get(slug, "")

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="320" height="520" viewBox="0 0 320 520">
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#140b24"/>
      <stop offset="50%" stop-color="#2a164f"/>
      <stop offset="100%" stop-color="#120a22"/>
    </linearGradient>
    <linearGradient id="gold" x1="0" x2="1">
      <stop offset="0%" stop-color="#caa85c"/>
      <stop offset="50%" stop-color="#f5e1a4"/>
      <stop offset="100%" stop-color="#b88b3f"/>
    </linearGradient>
    <linearGradient id="majorAccent" x1="0" x2="1">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="100%" stop-color="{c2}"/>
    </linearGradient>
    <filter id="shadow">
      <feDropShadow dx="0" dy="10" stdDeviation="10" flood-color="#000000" flood-opacity="0.35"/>
    </filter>
  </defs>

  <rect x="10" y="10" width="300" height="500" rx="24" fill="url(#bg)" stroke="url(#gold)" stroke-width="5" filter="url(#shadow)"/>
  <rect x="26" y="26" width="268" height="468" rx="18" fill="none" stroke="#e7d39b" stroke-opacity="0.75" stroke-width="2"/>

  <circle cx="160" cy="86" r="34" fill="none" stroke="url(#majorAccent)" stroke-width="3"/>
  <circle cx="160" cy="86" r="13" fill="url(#majorAccent)"/>
  <text x="160" y="92" text-anchor="middle" fill="#1b102f" font-size="14" font-family="Arial, sans-serif" font-weight="700">{major_number}</text>

  <circle cx="160" cy="228" r="76" fill="rgba(255,255,255,0.03)" stroke="url(#majorAccent)" stroke-width="2.5"/>
  <circle cx="160" cy="228" r="48" fill="none" stroke="url(#majorAccent)" stroke-opacity="0.45" stroke-width="1.5"/>
  <text x="160" y="246" text-anchor="middle" fill="url(#majorAccent)" font-size="64" font-family="Georgia, serif" font-weight="700">{icon}</text>

  <text x="160" y="342" text-anchor="middle" fill="#fff4cf" font-size="24" font-family="Georgia, serif" font-weight="700">{safe_title}</text>
  <text x="160" y="368" text-anchor="middle" fill="{c1}" font-size="12" font-family="Arial, sans-serif" font-weight="700">MAJOR ARCANA</text>

  <path d="M78 398 C112 352, 208 352, 242 398" fill="none" stroke="url(#gold)" stroke-width="2" opacity="0.85"/>
  <path d="M105 422 C130 388, 190 388, 215 422" fill="none" stroke="url(#gold)" stroke-width="2" opacity="0.55"/>

  <text x="160" y="452" text-anchor="middle" fill="#fff4cf" font-size="20" font-family="Georgia, serif" font-weight="700">{safe_title}</text>
  <text x="160" y="476" text-anchor="middle" fill="{c1}" font-size="11" font-family="Arial, sans-serif">{safe_slug}</text>
</svg>"""
    return Response(svg, content_type="image/svg+xml; charset=utf-8")


@app.route("/card-back")
def card_back():
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="320" height="520" viewBox="0 0 320 520">
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#160d2a"/>
      <stop offset="50%" stop-color="#2e1955"/>
      <stop offset="100%" stop-color="#0f091d"/>
    </linearGradient>
    <linearGradient id="gold" x1="0" x2="1">
      <stop offset="0%" stop-color="#caa85c"/>
      <stop offset="50%" stop-color="#f5e1a4"/>
      <stop offset="100%" stop-color="#b88b3f"/>
    </linearGradient>
    <filter id="shadow">
      <feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="#000000" flood-opacity="0.35"/>
    </filter>
  </defs>

  <rect x="10" y="10" width="300" height="500" rx="24" fill="url(#bg)" stroke="url(#gold)" stroke-width="5" filter="url(#shadow)"/>
  <rect x="26" y="26" width="268" height="468" rx="18" fill="none" stroke="#e7d39b" stroke-opacity="0.7" stroke-width="2"/>

  <circle cx="160" cy="110" r="34" fill="none" stroke="url(#gold)" stroke-width="3"/>
  <circle cx="160" cy="110" r="12" fill="url(#gold)" opacity="0.95"/>

  <path d="M160 60 L172 92 L206 92 L178 112 L189 145 L160 126 L131 145 L142 112 L114 92 L148 92 Z"
        fill="none" stroke="url(#gold)" stroke-width="2"/>

  <rect x="72" y="170" width="176" height="176" rx="20" fill="none" stroke="#e7d39b" stroke-opacity="0.42" stroke-width="2"/>
  <circle cx="160" cy="258" r="54" fill="none" stroke="url(#gold)" stroke-width="2"/>
  <circle cx="160" cy="258" r="20" fill="url(#gold)" opacity="0.92"/>

  <path d="M106 258 Q160 204 214 258 Q160 312 106 258 Z" fill="none" stroke="url(#gold)" stroke-width="2"/>
  <path d="M160 204 Q214 258 160 312 Q106 258 160 204 Z" fill="none" stroke="url(#gold)" stroke-width="2"/>

  <text x="160" y="408" text-anchor="middle" fill="#fff4cf" font-size="22" font-family="Georgia, serif" font-weight="700">OWEN TAROT</text>
  <text x="160" y="438" text-anchor="middle" fill="#d7c793" font-size="12" font-family="Arial, sans-serif">THE CARD AWAITS YOU</text>
</svg>"""
    return Response(svg, content_type="image/svg+xml; charset=utf-8")


if __name__ == "__main__":
    app.run(debug=True)