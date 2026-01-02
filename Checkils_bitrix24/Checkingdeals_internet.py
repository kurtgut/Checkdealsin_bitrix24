# Версия 0.1
# Программа ручной проверки Интернет сделок которые ушли в Успешные
# Проверяет наличие файла 1С Накладная и если файла нет возвращает сделку на стадию получена оплата

import os
from datetime import datetime, timedelta

import requests
from loguru import logger

import creds  # Импорт файла с конфигурацией

# Создаем папку для логов, если она не существует
log_folder = "logs"
if not os.path.exists(log_folder):
    os.makedirs(log_folder)

# Настройка логирования
log_file = os.path.join(log_folder, "Checkdeals.log")
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
    logger.info("Начало получения сделок за последние 7 дней.")
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
            response = requests.post(f"{webhook_url}crm.deal.list", json=params)
            response.raise_for_status() # Проверка на HTTP ошибки
            result = response.json()

            if "error" in result:
                logger.error(f"Ошибка API при получении сделок: {result['error_description']}")
                break

            # Обработка сделок
            for deal in result.get("result", []):
                # Проверяем поле на наличие файла
                if not deal.get(FIELD_TO_CHECK): # Если поле пустое
                    deals_without_files.append({"ID": deal["ID"], "TITLE": deal["TITLE"]}) # Добавляем ID и название сделки
                    logger.info(f"Сделка без файла найдена: {deal['TITLE']} (ID: {deal['ID']})")

            # Проверяем, есть ли еще страницы
            if "next" in result:
                params["start"] = result["next"]
            else:
                break

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при выполнении запроса: {e}")
            break

    logger.info(f"Получено {len(deals_without_files)} сделок без файлов.")
    return deals_without_files


def move_deals_to_new_stage(webhook_url, deals):
    """
    Перемещает сделки на новую стадию.
    """
    logger.info(f"Начало перемещения {len(deals)} сделок на стадию получена оплата.")
    for deal in deals:
        deal_id = deal["ID"]
        try:
            # Запрос на обновление стадии сделки
            response = requests.post(
                f"{webhook_url}crm.deal.update",
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
                logger.info(f"Сделка {deal['TITLE']} (ID: {deal_id}) успешно перемещена на стадию получена оплата {NEW_STAGE_ID}.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при выполнении запроса для сделки {deal['TITLE']} (ID: {deal_id}): {e}")


def main():
    logger.info("Запуск программы проверки сделок.")
    # Используем вебхук из файла creds
    webhook_url = BITRIX24_WEBHOOK_URL
    if not webhook_url:
        logger.error("Ошибка: Вебхук не загружен.")
        return

    # Получаем список сделок без файлов
    deals = get_deals(webhook_url)

    if deals:
        logger.info("Список сделок без файлов:")
        for deal in deals:
            logger.info(f"- {deal['TITLE']} (ID: {deal['ID']})")

        # Перемещаем сделки на новую стадию
        move_deals_to_new_stage(webhook_url, deals)
    else:
        logger.info("Все сделки содержат файлы или нет сделок за последние 7 дней.")

    logger.info("Программа завершена.")


if __name__ == "__main__":
    main()
