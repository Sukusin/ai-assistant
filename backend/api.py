# ai-assistant/backend/api.py
from flask import Flask, request, jsonify
from model.model_logic import process_letter
import traceback

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # чтобы русский текст не экранировался


@app.route("/process", methods=["POST"])
def process():
    try:
        data = request.get_json()
        text = data.get("text", "").strip()
        tone = data.get("tone", "деловой")  # "формальный", "деловой", "дружелюбный"
        #length = data.get("length", "full")

        if not text:
            return jsonify({"error": "Поле 'text' обязательно"}), 400

        result = process_letter(text, tone=tone)

        # Переводим ключи в camelCase для удобства фронта
        return jsonify({
            "classification": result["category"],
            "extractedInfo": result["info"],
            "response": result["response"],
            "urgency": result.get("urgency"),
            "summary": result.get("summary")
        })

    except Exception as e:
        app.logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Запуск: python api.py → http://localhost:5001/process
    app.run(host="0.0.0.0", port=5001, debug=True)