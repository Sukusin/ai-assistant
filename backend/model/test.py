import os
import urllib.request
from dotenv import load_dotenv
from openai import OpenAI

ENV_URL = "https://storage.yandexcloud.net/ycpub/maikeys/.env"

if not os.path.exists(".env"):
    print("Скачиваю .env...")
    urllib.request.urlretrieve(ENV_URL, ".env")

load_dotenv(".env")

folder_id = os.getenv("folder_id")
api_key = os.getenv("api_key")

if folder_id is None or api_key is None:
    raise RuntimeError("Не нашёл folder_id или api_key в .env")

model = f"gpt://{folder_id}/qwen3-235b-a22b-fp8/latest"

client = OpenAI(
    api_key=api_key,
    base_url="https://rest-assistant.api.cloud.yandex.net/v1",
    project=folder_id,
)

res = client.responses.create(
    model=model,
    instructions="Ты — полезный ассистент деловой переписки.",
    input="Привет! Напиши короткий деловой ответ клиенту, который благодарит нас за хорошую работу.",
)

print(res.output_text)
