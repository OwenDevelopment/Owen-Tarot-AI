import random
import re
import unicodedata

def card_to_slug(name: str) -> str:
    if not name:
        return "unknown-card"

    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = text.replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text

def normalize_card_image_map(raw_tarot_data):
    image_map = {}

    if isinstance(raw_tarot_data, list):
        for item in raw_tarot_data:
            if not isinstance(item, dict):
                continue

            name = item.get("name", "") or item.get("title", "")
            image = item.get("image", "") or item.get("img", "") or item.get("image_url", "")
            slug = item.get("slug", "") or card_to_slug(name)

            if name and image:
                image_map[name.strip().lower()] = image
            if slug and image:
                image_map[slug.strip().lower()] = image

    elif isinstance(raw_tarot_data, dict):
        for key, value in raw_tarot_data.items():
            if isinstance(value, dict):
                name = value.get("name", "") or key
                image = value.get("image", "") or value.get("img", "") or value.get("image_url", "")
                slug = value.get("slug", "") or card_to_slug(name)
            else:
                name = key
                image = value
                slug = card_to_slug(name)

            if name and image:
                image_map[name.strip().lower()] = image
            if slug and image:
                image_map[slug.strip().lower()] = image

    return image_map

def attach_positions(cards):
    positions_map = {
        1: ["Lá chính"],
        3: ["Quá khứ", "Hiện tại", "Tương lai"],
        10: [
            "Hiện tại", "Thử thách", "Nền tảng", "Quá khứ gần",
            "Mục tiêu", "Tương lai gần", "Bạn", "Môi trường",
            "Hy vọng / Nỗi sợ", "Kết quả"
        ]
    }

    labels = positions_map.get(len(cards), [f"Vị trí {i+1}" for i in range(len(cards))])

    result = []
    for i, card in enumerate(cards):
        c = dict(card)
        c["position"] = labels[i] if i < len(labels) else f"Vị trí {i+1}"
        result.append(c)
    return result

def draw_cards(cards_data, count, image_map=None):
    deck = random.sample(cards_data, count)
    results = []

    for card in deck:
        name = card.get("name", "Unknown Card")
        reversed_flag = random.choice([True, False])
        slug = card_to_slug(name)

        image = ""
        if image_map:
            image = (
                image_map.get(name.strip().lower())
                or image_map.get(slug.strip().lower())
                or ""
            )

        results.append({
            "name": name,
            "slug": slug,
            "meaning_up": card.get("meaning_up", ""),
            "meaning_rev": card.get("meaning_rev", ""),
            "description": card.get("description", ""),
            "reversed": reversed_flag,
            "image": image
        })

    return results

def build_local_reading(cards):
    lines = []
    for card in cards:
        status = "ngược" if card.get("reversed") else "xuôi"
        lines.append(f"- {card.get('position', '')}: {card.get('name', '')} ({status})")
    return "\n".join(lines)