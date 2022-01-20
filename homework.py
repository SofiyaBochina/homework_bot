import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import ResponseError, ServerError

load_dotenv()


PRACTICUM_TOKEN = secret_token = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = secret_token = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = 1593821440

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
    level=logging.INFO)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщений."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.info('Сообщение отправлено.')


def get_api_answer(current_timestamp):
    """Запрос ответа API от сервера."""
    params = {'from_date': current_timestamp}
    homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if homework_statuses is None:
        raise ServerError(
            'Сервер API недоступен.'
        )
    if homework_statuses.status_code != 200:
        raise ServerError(
            f'Код ответа API не равен 200: {homework_statuses.status_code}'
        )
    logger.info('Получен ответ API от сервера.')
    return homework_statuses.json()


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
    if PRACTICUM_TOKEN is None:
        logger.critical(
            'Отсутствует переменная окружения: PRACTICUM_TOKEN'
        )
        return False
    if TELEGRAM_TOKEN is None:
        logger.critical(
            'Отсутствует переменная окружения: TELEGRAM_TOKEN'
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
    first_response_made = False
    while True:
        try:
            if first_response_made is False:
                response = get_api_answer(current_timestamp)
                homework = check_response(response)
                first_response_made = True
            else:
                new_timestamp = get_current_date(response)
                response = get_api_answer(new_timestamp)
                homework = check_response(response)
            if homework != []:
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                logger.info('Изменений в статусе домашней работы нет')
            time.sleep(RETRY_TIME)
        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            if error_message != last_error:
                logger.error(error_message)
                send_message(bot, error_message)
                time.sleep(RETRY_TIME)
            last_error = error_message


if __name__ == '__main__':
    main()
