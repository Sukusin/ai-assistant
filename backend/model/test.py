# # Если ты в Jupyter / Colab — можно так скачать .env:
# !wget -O .env https://storage.yandexcloud.net/ycpub/maikeys/.env

import os
from dotenv import load_dotenv
from openai import OpenAI

# Загружаем переменные из .env
load_dotenv()

# Должны быть переменные folder_id и api_key в .env
folder_id = "b1gst3c7cskk2big5fqn"
api_key = "AQVNxQ_-mwN1bNst5oDEaWiRvm5cSFOvq_MzLoIz"

# Модель из Yandex AI Studio
model = f"gpt://{folder_id}/qwen3-235b-a22b-fp8/latest"

# Клиент в режиме совместимости с OpenAI
client = OpenAI(
    api_key=api_key,
    base_url="https://rest-assistant.api.cloud.yandex.net/v1",
    project=folder_id,
)

# Запрос через Responses API
res = client.responses.create(
    model=model,
    instructions="Ты — полезный ассистент",
    input="Привет! Чем бы мне заняться?",
)

print(res.output_text)
