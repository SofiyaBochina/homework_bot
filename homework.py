import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import ParsingError, ResponseError, ServerError, TelegramError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename=os.path.join(os.path.dirname(__file__), 'main.log'),
    filemode='w'
)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщений."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение отправлено.')
    except TelegramError:
        raise TelegramError(
            'Сервер Телеграма недоступен.'
        )


def get_api_answer(current_timestamp):
    """Запрос ответа API от сервера."""
    params = {'from_date': current_timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except ServerError:
        raise ServerError(
            'Не удалось получить ответа от API сервера.\n'
            f'Переданный URL: {ENDPOINT}\n'
        )
    if homework_statuses.status_code != 200:
        raise ServerError(
            'Код ответа API не равен 200.\n'
            f'Переданный URL: {ENDPOINT}\n'
            f'Код ответа API: {homework_statuses.status_code}'
        )
    try:
        homework_statuses = homework_statuses.json()
    except ParsingError:
        raise ParsingError(
            'Не удалось распарсить ответ сервера API.'
        )
    logger.info('Получен ответ API от сервера.')
    return homework_statuses


def check_response(response):
    """Проверка ответа API и получение списка домашней работы."""
    if response is None:
        raise ResponseError(
            'Ответ API не был получен.'
        )
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            f'Ответ API отличается от ожидаемого: {response["homeworks"]}'
        )
    homework = response.get('homeworks')
    if homework is None:
        raise KeyError(
            'Ответ API не содержит ключ "homeworks"'
        )
    if not isinstance(homework, list):
        raise TypeError(
            f'Ответ API отличается от ожидаемого: {homework}'
        )
    if 'error' in response.keys():
        raise ResponseError(
            'Обнаружена проблема при получении ответа от API сервера:\n'
            f'{response.get("error")}'
        )
    if 'code' in response.keys():
        raise ResponseError(
            'Обнаружена проблема при получении ответа от API сервера:\n'
            f'{response.get("code")}'
        )
    logger.info('Получен список домашних работ.')
    return homework


def parse_status(homework):
    """Проверка статуса и получение текста сообщения."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError(
            'Словарь не содержит ключ "homework_name".'
        )
    homework_status = homework.get('status')
    if homework_status is None:
        raise KeyError(
            'Словарь не содержит ключ "status".'
        )
    if homework_status not in HOMEWORK_STATUSES.keys():
        raise KeyError(
            f'Статус проверки {homework_status} неизвестен.'
        )
    verdict = HOMEWORK_STATUSES[homework_status]
    logger.info('Получен текст сообщения.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия токенов."""
    secret_list = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    for secret_name, secret in secret_list.items():
        if secret is None:
            logger.critical(
                f'Отсутствует переменная окружения: {secret_name}'
            )
            return False
    logger.info('Токены проверены.')
    return True


def get_current_date(response):
    """Получение времени запроса ответа API."""
    current_date = response.get('current_date')
    if current_date is None:
        raise KeyError(
            'Ответ API не содержит ключ "current_date".'
        )
    return current_date


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_error = None
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework != []:
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                logger.info('Изменений в статусе домашней работы нет')
            current_timestamp = get_current_date(response)
            time.sleep(RETRY_TIME)
        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            if error_message != last_error:
                logger.error(error_message)
                send_message(bot, error_message)
            last_error = error_message
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
