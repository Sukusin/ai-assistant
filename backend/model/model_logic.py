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


COMPANY_PRIORITY_TABLE: dict[str, dict] = {
    'ооо "ромашка"': {
        "base_priority": 7,
        "segment": "VIP-клиент",
        "risk_level": "low",
    },
    "банк россии": {
        "base_priority": 9,
        "segment": "Регулятор",
        "risk_level": "high",
    },
    # если компании нет - base=5
}



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
        return "Иное обращение"

    lowered = text.lower()

    if any(kw in lowered for kw in [
        "банк россии",           
        "банка россии",          
        "цб рф",
        "центральный банк российской федерации",
        "центрального банка российской федерации",
        "указание банка россии",
        "указания банка россии",
        "указание цб",
        "указания цб",
        "формы №",             
    ]):
        return "Регуляторный запрос"

    if any(kw in lowered for kw in [
        "жалоба",
        "претензия",
        "претензионное письмо",
        "грубое нарушен",       
        "нарушение условий договора",
        "ненадлежащ",          
        "требуем немедленного",
        "требуем возврата",
        "требуем возместить",
    ]):
        return "Официальная жалоба или претензия"

    if any(kw in lowered for kw in [
        "партнерство",
        "партнёрство",
        "стратегического партнёрства",
        "стратегического партнерства",
        "предлагаем сотрудничество",
        "предлагаем установить партнёрство",
        "предлагаем установить партнерство",
        "коммерческое предложение",
        "готовы обсудить детали",
        "совместного запуска цифровой платформы",
        "партнёрский проект",
    ]):
        return "Партнёрское предложение"

    if any(kw in lowered for kw in [
        "на согласование",
        "просим согласовать",
        "прошу согласовать",
        "согласование проведения мероприятия",
        "направляем на согласование",
    ]):
        return "Запрос на согласование"

    if any(kw in lowered for kw in [
        "просим предоставить",
        "прошу предоставить",
        "просим представить",
        "прошу представить",
        "просим направить",
        "прошу направить",
        "просим выслать",
        "прошу выслать",
        "запрос информации",
        "просим предоставить информацию",
        "просим предоставить документы",
        "просим представить информацию",
        "просим представить документы",
    ]):
        return "Запрос информации/документов"
    
    if any(kw in lowered for kw in [
        "сообщаем",
        "настоящим сообщаем",
        "уведомляем",
        "настоящим уведомляем",
        "информируем",
        "доводим до вашего сведения",
    ]):
        return "Уведомление или информирование"

    return "Иное обращение"

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

    # очень простое извлечение суммы (например, 100 000 руб.)
    amount_match = re.search(r"(\d[\d\s]{2,})\s*(?:руб\.?|₽)", text.lower())
    if amount_match:
        info["amount"] = amount_match.group(1).strip().replace(" ", "")

    # попытка вытащить компанию-отправителя: ООО/АО/ПАО «...» или "..."
    company_match = re.search(r"(ООО|АО|ПАО)\s+\"?«?([^»\"]+)\"?»?", text)
    if company_match:
        sender_company = f'{company_match.group(1)} "{company_match.group(2).strip()}"'
        info["sender_company"] = sender_company

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
        "крайний срок",
        "срок исполнения",
        "просим ответить в течение",
        "до ",
    ]

    if any(m in lowered for m in high_markers):
        return "Высокая срочность"

    if any(m in lowered for m in medium_markers):
        return "Средняя срочность"

    return "Низкая срочность"

def get_company_profile(sender_company: str | None) -> dict | None:
    if not sender_company:
        return None
    key = sender_company.lower()
    return COMPANY_PRIORITY_TABLE.get(key)


def calculate_priority(
    category: str,
    urgency: str,
    info: dict,
    sender_company: str | None = None,
) -> dict:
    adjustments: list[str] = []
    company_profile = get_company_profile(sender_company)

    # базовый приоритет
    if company_profile and "base_priority" in company_profile:
        base_priority = int(company_profile["base_priority"])
        adjustments.append(
            f"Базовый приоритет по компании ({company_profile.get('segment', 'без сегмента')}) = {base_priority}"
        )
    else:
        base_priority = 5  # дефолт
        adjustments.append("Компания не найдена в таблице, базовый приоритет = 5")

    priority = base_priority

    # корректировка по категории
    if category == "Жалоба":
        priority += 2
        adjustments.append("Категория 'Жалоба' → +2 к приоритету")
    elif category == "Регуляторный запрос":
        priority = max(priority, 8)
        adjustments.append("Категория 'Регуляторный запрос' → приоритет не ниже 8")
    elif category == "Партнёрское предложение":
        priority += 1
        adjustments.append("Категория 'Партнёрское предложение' → +1 к приоритету")

    # корректировка по срочности
    if urgency == "Высокая срочность":
        priority += 2
        adjustments.append("Высокая срочность → +2 к приоритету")
    elif urgency == "Средняя срочность":
        priority += 1
        adjustments.append("Средняя срочность → +1 к приоритету")

    # корректировка по сумме
    amount_str = info.get("amount")
    if amount_str:
        try:
            amount = int(amount_str)
            if amount >= 10_000_000:
                priority += 2
                adjustments.append("Сумма ≥ 10 000 000 → +2 к приоритету")
            elif amount >= 1_000_000:
                priority += 1
                adjustments.append("Сумма ≥ 1 000 000 → +1 к приоритету")
        except ValueError:
            pass

    # ограничиваем диапазон 0-9
    priority = max(0, min(9, priority))

    return {
        "base_priority": base_priority,
        "final_priority": priority,
        "adjustments": adjustments,
        "sender_company": sender_company,
        "company_profile": company_profile,
    }

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


ANSWER_LENGTH_PRESETS = {
    "short":  "Ответ не более 3–4 предложений.",
    "medium": "Ответ не более 6–8 предложений.",
    "long":   "Ответ не более 12–15 предложений.",
}

def build_prompt(
    original_text: str,
    category: str | None,
    info: dict | None,
    tone: str | None = None,
    answer_length: str | None = None,
) -> str:
    info_lines = []
    if info:
        for k, v in info.items():
            info_lines.append(f"- {k}: {v}")
    info_block = "\n".join(info_lines) if info_lines else "нет дополнительных данных"

    # Тон
    if tone == "Официальный строгий":
        tone_instruction = (
            "Используй максимально официальный и строгий тон: "
            "деловой стиль, опора на нормы и формулировки документов, "
            "минимум эмоций и разговорных оборотов."
        )
    elif tone == "Корпоративный-деловой":
        tone_instruction = (
            "Пиши в корпоративном деловом стиле: вежливо, профессионально, "
            "структурированно и по делу, без излишней эмоциональности."
        )
    elif tone == "Клиентоориентированный":
        tone_instruction = (
            "Сохраняй вежливый и клиентоориентированный тон: подчёркивай внимание к "
            "клиенту, проявляй эмпатию, предлагай помощь и варианты решения, "
            "избегай резких формулировок."
        )

    # Длина ответа
    if answer_length is None:
        answer_length = "medium"  # значение по умолчанию

    length_instruction = ANSWER_LENGTH_PRESETS.get(
        answer_length,
        ANSWER_LENGTH_PRESETS["medium"],
    )

    return f"""
        Ты - ассистент деловой переписки крупного банка. Пиши строго на «Вы», официально-деловым стилем.

        Входящее письмо клиента:
        \"\"\"{original_text}\"\"\"

        Категория письма: {category or "не определено"}.
        Извлечённые ключевые факты:
        {info_block}

        {tone_instruction}
        {length_instruction}

        Сформируй вежливый, профессиональный ответ от лица банка. 
        Структура:
        - Обращение (если нет имени, используй «Уважаемый клиент»)
        - 1–2 абзаца по сути
        - При необходимости: сроки и дальнейшие шаги
        - Завершение с фразой «С уважением, ПСБ Банк».
        """.strip()



def generate_response(
    text: str,
    category: str | None = None,
    info: dict | None = None,
    answer_length: str | None = None,
) -> str:
    # дефолтный тон, но передаём длину
    return generate_response_with_tone(
        text=text,
        category=category,
        info=info,
        tone=None,
        answer_length=answer_length,
    )


def generate_response_with_tone(
    text: str,
    category: str | None = None,
    info: dict | None = None,
    tone: str | None = None,
    answer_length: str | None = None,
) -> str:
    prompt = build_prompt(
        original_text=text,
        category=category,
        info=info,
        tone=tone,
        answer_length=answer_length,
    )

    try:
        res = client.responses.create(
            model=model,
            instructions="Ты - ассистент деловой переписки банка.",
            input=prompt,
        )
        return res.output_text.strip()
    except Exception as e:
        return f"Не удалось сгенерировать ответ: {e}"


def process_letter(
    text: str,
    tone: str | None = None,
    sender_company: str | None = None,
    answer_length: str | None = None,
) -> dict:
    """
    Главный хелпер: принимает текст письма (и, опционально, компанию-отправителя и длину ответа).
    Возвращает всё, что нужно фронту.
    """
    cleaned = preprocess_text(text)
    category = classify_letter(cleaned)
    info = extract_info(cleaned)

    # если компанию явно передали в аргументе — считаем, что она приоритетнее парсинга из текста
    if sender_company:
        info["sender_company"] = sender_company

    urgency = estimate_urgency(cleaned)
    summary = summarize_letter(cleaned)

    priority_info = calculate_priority(
        category=category,
        urgency=urgency,
        info=info,
        sender_company=info.get("sender_company"),
    )

    response = generate_response_with_tone(
        cleaned,
        category,
        info,
        tone=tone,
        answer_length=answer_length,
    )

    return {
        "category": category,
        "info": info,
        "urgency": urgency,
        "summary": summary,
        "response": response,
        "priority": priority_info,
    }
