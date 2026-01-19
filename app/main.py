from router import route_message

print("CNC Assistant запущен")

user_id = 1  # для теста CLI

while True:
    user_input = input(">> ")
    if user_input.lower() in ["выход", "exit"]:
        break
    response = route_message(user_id, user_input)
    print(response)
