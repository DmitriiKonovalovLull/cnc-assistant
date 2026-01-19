# ===============================
# main.py — CLI с долгой памятью
# ===============================
from memory.session import get_session, update_session
from router import route_message  # сюда подключи твой process_flow
import os

os.makedirs("storage", exist_ok=True)

print("✅ CNC Assistant запущен")

user_id = 1  # для CLI теста

while True:
    user_input = input(">> ")
    if user_input.lower() in ["выход", "exit"]:
        break
    response = route_message(user_id, user_input)
    print(response)
