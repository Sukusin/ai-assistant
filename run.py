# ai-assistant/run.py
import subprocess
import sys
import time

def run():
    # Запускаем бэкенд в фоне
    backend = subprocess.Popen([
        sys.executable, "-u", "backend/api.py"
    ], cwd=".", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    print("Бэкенд запущен (порт 5001)")

    try:
        # Ждём немного, чтобы бэкенд стартовал
        time.sleep(2)

        # Читаем логи бэкенда
        def log_backend():
            for line in iter(backend.stdout.readline, ''):
                if line:
                    print(f"[BACKEND] {line.rstrip()}")
        import threading
        threading.Thread(target=log_backend, daemon=True).start()

        # Запускаем фронтенд в основном процессе
        print("Запускаем фронтенд (порт 5000)...")
        subprocess.run([sys.executable, "-u", "frontend/app.py"])

    except KeyboardInterrupt:
        print("\nОстановка...")
    finally:
        backend.terminate()
        backend.wait()
        print("Оба сервиса остановлены.")

if __name__ == "__main__":
    run()