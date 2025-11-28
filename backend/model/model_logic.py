# backend/model/model_logic.py
import os
import re
import urllib.request
from datetime import datetime, timedelta

from dotenv import load_dotenv
from openai import OpenAI

ENV_URL = "https://storage.yandexcloud.net/ycpub/maikeys/.env"

if not os.path.exists(".env"):
    print("Скачиваю .env...")
    urllib.request.urlretrieve(ENV_URL, ".env")

load_dotenv(".env")

folder_id = os.getenv("folder_id")
api_key = os.getenv("api_key")

if not folder_id or not api_key:
    raise RuntimeError(
        "Не найдены переменные окружения 'folder_id' или 'api_key'. "
    )

model = f"gpt://{folder_id}/qwen3-235b-a22b-fp8/latest"

client = OpenAI(
    api_key=api_key,
    base_url="https://rest-assistant.api.cloud.yandex.net/v1",
    project=folder_id,
)

def preprocess_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.strip()
    text = text.replace("\r", " ")
    text = " ".join(text.split())
    return text

def classify_letter(text: str) -> str:
    text = preprocess_text(text)

    if not text:
        return "Не определено"

    lowered = text.lower()

    if any(w in lowered for w in ["претензия", "жалоба", "недовольн", "нарушение"]):
        return "Жалоба"

    if any(w in lowered for w in ["банк россии", "центральный банк", "указание банка россии"]):
        return "Регуляторный запрос"

    if any(w in lowered for w in [
        "предлагаем сотрудничество",
        "предлагаем партнёрство",
        "предлагаем партнерство",
        "партнерство",
        "партнёрство",
        "коммерческое предложение",
    ]):
        return "Партнёрское предложение"

    if any(w in lowered for w in [
        "просим предоставить",
        "просим направить",
        "запрос информации",
        "просим выслать",
        "прошу предоставить",
    ]):
        return "Запрос информации"

    if any(w in lowered for w in ["благодарим", "спасибо", "благодарность"]):
        return "Благодарность"

    return "Общий запрос"

def extract_info(text: str) -> dict:
    info: dict = {}

    # поиск даты в формате 12.03.2025
    date_match = re.search(r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b", text)
    if date_match:
        info["deadline_date"] = date_match.group(1)

    # примитив: "в течение N дней"
    days_match = re.search(r"в течение\s+(\d+)\s+дн", text.lower())
    if days_match:
        days = int(days_match.group(1))
        info["deadline_relative"] = f"{days} дней"
        info["deadline_date_estimated"] = (
            datetime.now() + timedelta(days=days)
        ).strftime("%d.%m.%Y")

    # номер договора/закона вида №123-ХХ или № 123
    contract_match = re.search(r"№\s*([\w\-\/]+)", text)
    if contract_match:
        info["document_number"] = contract_match.group(1)

    # очень простое извлечение суммы
    amount_match = re.search(r"(\d[\d\s]{2,})\s*(?:руб\.?|₽)", text.lower())
    if amount_match:
        info["amount"] = amount_match.group(1).strip().replace(" ", "")

    return info

def estimate_urgency(text: str) -> str:
    lowered = text.lower()

    high_markers = [
        "срочно",
        "в кратчайшие сроки",
        "немедленно",
        "в ближайшее время",
        "незамедлительно",
        "до конца дня",
    ]
    medium_markers = [
        "до ",
        "крайний срок",
        "срок исполнения",
        "просим ответить в течение",
    ]

    if any(m in lowered for m in high_markers):
        return "Высокая срочность"

    if any(m in lowered for m in medium_markers):
        return "Средняя срочность"

    return "Низкая срочность"

def summarize_letter(text: str, max_sentences: int = 2) -> str:
    text = preprocess_text(text)
    if not text:
        return ""

    prompt = f"""
Тебе дан текст входящего письма.

Задача: кратко пересказать суть письма {max_sentences} предложениями на русском языке, 
нейтральным деловым стилем, без приветствий и лишних деталей.

Письмо:
\"\"\"{text}\"\"\"
""".strip()

    try:
        res = client.responses.create(
            model=model,
            instructions="Ты кратко пересказываешь содержание деловых писем.",
            input=prompt,
        )
        return res.output_text.strip()
    except Exception as e:
        return f"Не удалось сформировать краткое резюме письма ({e})."

def build_prompt(
    original_text: str,
    category: str | None,
    info: dict | None,
    tone: str | None = None,
) -> str:
    info_lines = []
    if info:
        for k, v in info.items():
            info_lines.append(f"- {k}: {v}")
    info_block = "\n".join(info_lines) if info_lines else "нет дополнительных данных"

    if tone == "мягкий":
        tone_instruction = "Сохраняй вежливый, но более мягкий и дружелюбный тон."
    elif tone == "строгий":
        tone_instruction = "Тон более формальный и строгий, без лишних эмоций."
    else:
        tone_instruction = "Используй стандартный официальный деловой тон."

    return f"""
Ты - ассистент деловой переписки крупного банка. Пиши строго на «Вы», официально-деловым стилем.

Входящее письмо клиента:
\"\"\"{original_text}\"\"\"

Категория письма: {category or "не определено"}.
Извлечённые ключевые факты:
{info_block}

{tone_instruction}

Сформируй вежливый, профессиональный ответ от лица банка. 
Структура:
- Обращение (если нет имени, используй «Уважаемый клиент»)
- 1–2 абзаца по сути
- При необходимости: сроки и дальнейшие шаги
- Завершение с фразой «С уважением, [название банка]».

Не используй неформальных обращений. Ответ не более 8–10 предложений.
""".strip()


def generate_response(
    text: str,
    category: str | None = None,
    info: dict | None = None,
) -> str:
    return generate_response_with_tone(text, category, info, tone=None)


def generate_response_with_tone(
    text: str,
    category: str | None = None,
    info: dict | None = None,
    tone: str | None = None,
) -> str:
    prompt = build_prompt(text, category, info, tone=tone)

    try:
        res = client.responses.create(
            model=model,
            instructions="Ты - ассистент деловой переписки банка.",
            input=prompt,
        )
        return res.output_text.strip()
    except Exception as e:
        return f"Не удалось сгенерировать ответ: {e}"


def process_letter(text: str, tone: str | None = None) -> dict:
    cleaned = preprocess_text(text)
    category = classify_letter(cleaned)
    info = extract_info(cleaned)
    urgency = estimate_urgency(cleaned)
    summary = summarize_letter(cleaned)
    response = generate_response_with_tone(cleaned, category, info, tone=tone)


    return {
        "category": category,
        "info": info,
        "urgency": urgency,
        "summary": summary,
        "response": response,
    }
