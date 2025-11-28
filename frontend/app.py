from flask import Flask, render_template, request, jsonify
import re
import requests
import os

app = Flask(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5001/process")
USE_BACKEND = os.getenv("USE_BACKEND", "true").lower() in ("1", "true", "yes")


def detect_classification(text: str) -> str:
    lower = text.lower()
    if "жалоб" in lower:
        return "Официальная жалоба"
    if "регулятор" in lower or "надзор" in lower:
        return "Регуляторный запрос"
    if "партнер" in lower or "партнёр" in lower:
        return "Партнёрское предложение"
    if "счет" in lower or "счёт" in lower or "оплат" in lower:
        return "Запрос по оплате/счету"
    return "Общее деловое обращение"


def extract_info(text: str):
    info = []

    contract_match = re.search(r"договор[а-я]* №?\s*([\w\/\-]+)", text, re.IGNORECASE)
    if contract_match:
        info.append({"label": "Номер договора", "value": contract_match.group(1)})

    deadline_match = re.search(
        r"(до|в срок до)\s+(\d{1,2}\.\d{1,2}\.\d{2,4}|\d{1,2}\s+[а-я]+\s+\d{4})",
        text,
        re.IGNORECASE
    )
    if deadline_match:
        info.append({"label": "Дедлайн / срок", "value": deadline_match.group(2)})

    company_match = re.search(
        r"(ООО|АО|ПАО|ЗАО)\s+[«\"']?([\wА-Яа-яёЁ0-9\s\-]+?)[»\"']?",
        text,
        re.IGNORECASE
    )
    if company_match:
        info.append({"label": "Организация отправителя", "value": company_match.group(0)})

    if text.strip():
        short_text = text.strip()
        if len(short_text) > 180:
            short_text = short_text[:180].strip() + "…"
        info.append({"label": "Краткая суть обращения", "value": short_text})

    return info


def build_answer(text: str, style: str, length: str, classification_label: str) -> str:
    style_intro_map = {
        "formal": "Уважаемый(ая) господин(жа),",
        "business": "Добрый день,",
        "client": "Здравствуйте,",
    }

    style_outro_map = {
        "formal": "С уважением,",
        "business": "С наилучшими пожеланиями,",
        "client": "Спасибо, что обратились к нам,",
    }

    intro = style_intro_map.get(style, style_intro_map["business"])
    outro = style_outro_map.get(style, style_outro_map["business"])

    if classification_label == "Официальная жалоба":
        base_body = "благодарим вас за предоставленную информацию. Мы внимательно рассмотрели изложенные замечания и уже инициировали внутреннюю проверку по описанной ситуации."
    elif classification_label == "Регуляторный запрос":
        base_body = "подтверждаем получение вашего запроса. В настоящее время мы собираем и проверяем необходимую информацию для подготовки полного ответа."
    elif classification_label == "Партнёрское предложение":
        base_body = "благодарим вас за интерес к сотрудничеству. Мы внимательно изучили ваше предложение и видим потенциал для дальнейшего взаимодействия."
    else:
        base_body = "благодарим вас за обращение. Мы внимательно ознакомились с вашим запросом и уже приступили к его обработке."

    extra_details = (
        " В ближайшее время мы предоставим вам развёрнутый ответ с необходимыми пояснениями и, при необходимости, дополнительными документами."
        if length == "full" else
        " В кратчайшие сроки мы вернёмся к вам с ответом."
    )

    return f"{intro}\n\n{base_body}{extra_details}\n\n{outro}\n[Название компании]"


def try_use_backend(text, style, length):
    if not USE_BACKEND:
        return None

    tone_map = {"formal": "формальный", "business": "деловой", "client": "дружелюбный"}
    tone = tone_map.get(style, "деловой")

    try:
        resp = requests.post(
            BACKEND_URL,
            json={"text": text, "tone": tone, "length": length},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if "classification" in data and "response" in data:
                extracted = data.get("extracted_info", data.get("extractedInfo", []))
                return {
                    "classification": data["classification"],
                    "extractedInfo": extracted,
                    "answerText": data["response"]
                }
    except:
        pass  # любая ошибка → fallback

    return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json() or {}
    incoming_text = data.get("incomingText", "").strip()
    email_style = data.get("emailStyle", "business")
    email_length = data.get("emailLength", "full")

    if not incoming_text:
        return jsonify({"error": "Пустой текст письма."}), 400

    # Пытаемся использовать бэкенд
    backend_res = try_use_backend(incoming_text, email_style, email_length)
    if backend_res:
        return jsonify(backend_res)

    # Fallback
    classification = detect_classification(incoming_text)
    info = extract_info(incoming_text)
    answer = build_answer(incoming_text, email_style, email_length, classification)

    return jsonify({
        "classification": classification,
        "extractedInfo": info,
        "answerText": answer
    })


if __name__ == "__main__":
    app.run(debug=True)