# Импортирование библиотек и модулей
import functools
import telebot
import requests
import json
import os
import logging
import threading
from flask import Flask
from telebot import types
from datetime import datetime
from schedule_data import Schedule

# Получение токена из переменных окружения
BOT_API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
weather_API =  os.environ.get('weather_API')
bot = telebot.TeleBot(BOT_API_TOKEN)
USER_DATA_FILE = "user_data.json"

# Проверка на загрузку токена
if not BOT_API_TOKEN:
    raise ValueError("Переменная не найдена")
session = requests.Session()

session.request = functools.partial(session.request, timeout=30)

weather_descriptions = {
    "clear sky": "ясно",
    "few clouds": "слегка облачно",
    "scattered clouds": "рассеянные облака",
    "broken clouds": "разорванные облака",
    "overcast clouds": "пасмурно",
    "light intensity shower rain": "легкий дождь",
    "moderate rain": "умеренный дождь",
    "heavy rain": " сильный дождь",
    "thunderstorm": "гроза",
    "smoke": "туман",
    "haze": "лёгкий туман"
}

classes = ['10/1', '10/2', '10/3', '10/4']

today_num = datetime.now().weekday()


def load_user_data():  # Загрузка данных о выбранных классах пользователя
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_user_data(data):  # Сохранение словаря с классом в файл
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


user_class = load_user_data()


def main_keyboard():  # Создание клавиатуры с главными кнопками
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_schedule = types.KeyboardButton("📅 Расписание")
    btn_change_class = types.KeyboardButton("🏫 Сменить класс")
    btn_weather = types.KeyboardButton("🌤 Погода")
    markup.add(btn_schedule, btn_change_class, btn_weather)
    return markup


def get_class_keyboard():  # Создание клавиатуры для выбора класса
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    buttons = [types.KeyboardButton(cls) for cls in classes]
    markup.add(*buttons)
    return markup


def days_inline_keyboard():  # Создание клавиатуры для выбора дня недели для расписания
    markup = types.InlineKeyboardMarkup(row_width=2)
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]
    buttons = [types.InlineKeyboardButton(day, callback_data=f"day_{day}") for day in days]
    markup.add(*buttons)
    return markup


def get_schedule_for_class_and_day(class_name, day_name):  # Формирование и вывод расписания на заданный день
    class_schedule = Schedule.get(class_name)
    if class_schedule is None:
        return f"Класс {class_name} не найден."
    day_schedule = class_schedule.get(day_name)
    if day_schedule is None:
        return f"Расписание на {day_name} для класса {class_name} отсутствует."

    schedule_hat = f'📚 *Расписание для {class_name} на {day_name}:*\n'
    for i, lesson in enumerate(day_schedule, 1):
        if lesson is None or lesson.get('lesson') is None:
            schedule_hat += f"{i}. *Нет урока* (можно прийти позже)\n"
        else:
            schedule_hat += f"{i}. {lesson['lesson']} {lesson['time']} (каб. {lesson['room']})\n"
    return schedule_hat


@bot.message_handler(commands=['start'])
def send_welcome(message):  # Первое сообщение бота при новом чате
    user_id = str(message.from_user.id)
    if user_id in user_class:
        bot.send_message(message.chat.id, f'С возвращением, {message.from_user.first_name}! Вы закреплены за классом {user_class[user_id]}.', reply_markup=main_keyboard())
    else:
        bot.send_message(message.chat.id, f'Здравствуй, {message.from_user.first_name}! Выбери свой класс:', reply_markup=get_class_keyboard())


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):  # Обработка всех нажатий на кнопки, обработка выбора дня и возврата в главное меню
    user_id = str(call.from_user.id)
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    if call.data.startswith("day_"):
        day = call.data[4:]  # Получение названия дня
        if user_id not in user_class:
            bot.send_message(chat_id, 'Сначала выберите класс с помощью кнопки "Сменить класс".')
            bot.answer_callback_query(call.id)
            return
        class_name = user_class[user_id]
        schedule_text = get_schedule_for_class_and_day(class_name, day)
        bot.send_message(chat_id, schedule_text, parse_mode="Markdown")
        bot.delete_message(chat_id, message_id)
    elif call.data == "back_to_menu":
        bot.delete_message(chat_id, message_id)
        bot.send_message(chat_id, "Главное меню:", reply_markup=main_keyboard())
    bot.answer_callback_query(call.id)


@bot.message_handler(commands=['schedule'])
def schedule(message):  # Отправка расписания на текущий день
    user_id = str(message.from_user.id)
    if user_id not in user_class:
        bot.send_message(message.chat.id,
                         'Сначала выберите ваш класс с помощью кнопки "Сменить класс"', reply_markup=get_class_keyboard())
        return
    class_name = user_class[user_id]
    # Определение текущего дня недели
    from datetime import datetime
    days_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    today = days_ru[datetime.now().weekday()]
    # Получение расписания
    schedule_text = get_schedule_for_class_and_day(class_name, today)
    bot.reply_to(message, schedule_text, parse_mode="Markdown")


@bot.message_handler(func=lambda message: message.text == "📅 Расписание")
def handle_schedule_button(message):  # Отправка сообщения с расписанием
    user_id = str(message.from_user.id)
    if user_id not in user_class:
        bot.send_message(message.chat.id, 'Сначала выберите ваш класс с помощью кнопки "Сменить класс".', reply_markup=main_keyboard())
        return
    bot.send_message(message.chat.id, "📅 Выберите день недели:", reply_markup=days_inline_keyboard())


@bot.message_handler(func=lambda message: message.text == "🏫 Сменить класс")
def handle_change_class_button(message):  # Отправка сообщения со сменой класса
    set_class_command(message)


@bot.message_handler(func=lambda message: message.text == "🌤 Погода")
def handle_weather_button(message):  # Отправка сообщения с запросом погоды
        try:
            res = requests.get(f'https://api.openweathermap.org/data/2.5/weather?q=omsk&appid={weather_API}')
            if res.status_code == 200:
                data = json.loads(res.text)
                temp = round((data['main']['temp'] - 273.15))
                description_en = data['weather'][0]['description']
                description_ru = weather_descriptions.get(description_en, description_en)
                bot.send_message(message.chat.id, f'🌤 Погода в Омске сейчас: {temp}°C, {description_ru}.')
            else:
                bot.send_message(message.chat.id, 'Не удалось получить погоду. Попробуйте позже.')
        except Exception as e:
            bot.send_message(message.chat.id, f'Произошла ошибка: {e}')


@bot.message_handler(func=lambda message: message.text in classes)
def set_class(message):  # Сохранение выбранныого класса для пользователя
    user_id = str(message.from_user.id)
    selected_class = message.text
    user_class[user_id] = selected_class
    save_user_data(user_class)
    bot.send_message(message.chat.id, f'Вы выбрали класс {selected_class}. Теперь вы можете использовать команду /schedule или кнопку "Расписание" для получения расписания.',
                     reply_markup=main_keyboard())  # Скрытие временной клавиатуры и возвращение главной клавиатуры


@bot.message_handler(commands=['setclass'])
def set_class_command(message):  # Вывод клавиатуры для выбора класса
    bot.send_message(message.chat.id, "Выберите ваш класс:", reply_markup=get_class_keyboard())

def run_bot(): # Запуск бота в режиме long polling
    bot.delete_webhook() # Удаление вебхука, если он был установлен
    print("Бот запущен")
    bot.polling(none_stop=True)

# Создание Flask-приложения
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "OK", 200

if __name__ == '__main__':
    # Запуск бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()

    # Запуск Flask-сервера на порту, который даёт платформа Render
    port = int(os.environ.get('PORT', 5000))
    flask_app.run(host='0.0.0.0', port=port)
