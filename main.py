from core.dialog_manager import handle

# память пользователя и текущий шаг
context = {}
step = "INIT"
user_id = 1  # для примера, CLI-сессия

print("CNC Assistant запущен")

while True:
    try:
        user_input = input(">> ")
        response, context, step = handle(user_input, context, step, user_id)
        print(response)
    except KeyboardInterrupt:
        print("\nВыход из бота.")
        break
