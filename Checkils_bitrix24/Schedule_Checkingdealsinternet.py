# Версия 0.1
# Каждый час и полчаса
# Запускает проверку стадии успешной в Битрикс 24 на наличие сделок без накладной и возвращает сделку на стадию "получена оплата"

import requests
from datetime import datetime, timedelta
import creds # Импорт файла с конфигурацией
import schedule
import time
from loguru import logger # Импортируем loguru для логирования
import os

# Создаем папку для логов, если она не существует
log_folder = "logs"
if not os.path.exists(log_folder):
    os.makedirs(log_folder)

# Настройка логирования
log_file = os.path.join(log_folder, "Schedule_Checkingdealsinternet.log")
logger.add(log_file, rotation="10 MB", retention="10 days", level="INFO")

# Конфигурация API Bitrix24 (из файла creds)
BITRIX24_WEBHOOK_URL = creds.b24_webhook2

# Константы для фильтрации
FUNNEL_ID = 0 # ID воронки
STAGE_ID = "WON" # Стадия сделки
FIELD_TO_CHECK = "UF_CRM_1744885954501" # Поле для проверки наличия файла
NEW_STAGE_ID = "UC_6DPHP4" # Новая стадия для перемещения сделок


def get_deals(webhook_url):
    """
    Получает сделки за последние 7 дней в указанной воронке и стадии.
    """
    # Дата 7 дней назад
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")

    # Параметры фильтрации
    params = {
        "filter": {
            "CATEGORY_ID": FUNNEL_ID, # Воронка
            "STAGE_ID": STAGE_ID, # Стадия
            ">=DATE_MODIFY": seven_days_ago # Сделки за последние 7 дней
        },
        "select": ["ID", "TITLE", FIELD_TO_CHECK], # Поля для выборки
        "start": 0 # Начальная позиция для постраничного вывода
    }

    deals_without_files = [] # Список сделок без файлов

    while True:
        try:
            # Запрос к API Битрикс24
            response = requests.post(f"{webhook_url}/crm.deal.list", json=params) # Добавлен "/" перед методом
            response.raise_for_status() # Проверка на HTTP ошибки
            result = response.json()

            if "error" in result:
                logger.error(f"Ошибка: {result['error_description']}")
                break

            # Обработка сделок
            for deal in result.get("result", []):
                # Проверяем поле на наличие файла
                if not deal.get(FIELD_TO_CHECK): # Если поле пустое
                    deals_without_files.append(
                        {"ID": deal["ID"], "TITLE": deal["TITLE"]}) # Добавляем ID и название сделки

            # Проверяем, есть ли еще страницы
            if result.get("next"):
                params["start"] = result["next"]
            else:
                break

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при выполнении запроса: {e}")
            break

    return deals_without_files


def move_deals_to_new_stage(webhook_url, deals):
    """
    Перемещает сделки на новую стадию.
    """
    for deal in deals:
        deal_id = deal["ID"]
        try:
            # Запрос на обновление стадии сделки
            response = requests.post(
                f"{webhook_url}/crm.deal.update", # Добавлен "/" перед методом
                json={
                    "id": deal_id,
                    "fields": {
                        "STAGE_ID": NEW_STAGE_ID # Устанавливаем новую стадию
                    }
                }
            )
            result = response.json()

            if "error" in result:
                logger.error(f"Ошибка при обновлении сделки {deal['TITLE']} (ID: {deal_id}): {result['error_description']}")
            else:
                logger.info(f"Сделка {deal['TITLE']} (ID: {deal_id}) успешно перемещена на стадию {NEW_STAGE_ID}.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при выполнении запроса для сделки {deal['TITLE']} (ID: {deal_id}): {e}")


def process_deals():
    """
    Основная функция для обработки сделок.
    """
    # Используем вебхук из файла creds
    webhook_url = BITRIX24_WEBHOOK_URL
    if not webhook_url:
        logger.error("Ошибка: Вебхук не загружен.")
        return

    # Получаем список сделок без файлов
    deals = get_deals(webhook_url)

    if deals:
        logger.info("Сделки без файлов в поле UF_CRM_1744885954501:")
        for deal in deals:
            logger.info(f"- {deal['TITLE']} (ID: {deal['ID']})")

        # Перемещаем сделки на новую стадию
        move_deals_to_new_stage(webhook_url, deals)
    else:
        logger.info("Все сделки содержат файлы или нет сделок за последние 7 дней.")


def main():
    # Планировщик: запускать каждый 1 и 30 минут
    schedule.every().hour.at(":01").do(process_deals) # Запускать на 1-й минуте каждого часа
    schedule.every().hour.at(":30").do(process_deals) # Запускать на 30-й минуте каждого часа

    print("Планировщик запущен. Скрипт будет выполняться на 1-й и 30-й минуте каждого часа.")
    logger.info("Планировщик запущен. Скрипт будет выполняться на 1-й и 30-й минуте каждого часа.")

    # Бесконечный цикл для выполнения задач по расписанию
    while True:
        schedule.run_pending()
        time.sleep(1) # Небольшая задержка, чтобы не нагружать процессор


if __name__ == "__main__":
    main()
