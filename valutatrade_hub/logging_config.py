# valutatrade_hub/logging_config.py
"""
Настройка логов приложения.

Формат: человекочитаемый (строковый), одна строка на запись.
Пример: INFO 2025-10-09T12:05:22 BUY user_id=1 currency='BTC' amount=0.0500 rate=59300.00 base='USD' result=OK

Политика ротации:
- logs/actions.log — лог доменных операций (BUY/SELL/register/login): RotatingFileHandler,
  maxBytes=5MB, backupCount=3 (по размеру).
- logs/valutatrade.log — общий лог: maxBytes=10MB, backupCount=5.

Уровень по умолчанию: INFO. Для отладки установить VALUTATRADE_LOG_LEVEL=DEBUG в окружении
или в [tool.valutatrade] в pyproject.toml (log_level = "DEBUG").
"""
import logging as lg
import logging.handlers as hd
import os

# Формат: уровень + timestamp (ISO) + сообщение
ACTIONS_LOG_FORMAT = '%(levelname)s %(asctime)s %(message)s'
ACTIONS_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'

DEFAULT_LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def setup_logging():
    '''
    Настройка системы логирования: формат, ротация файлов, уровень (INFO по умолчанию).
    '''
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)

    formatter = lg.Formatter(DEFAULT_LOG_FORMAT, datefmt=DEFAULT_DATE_FORMAT)
    actions_formatter = lg.Formatter(ACTIONS_LOG_FORMAT, datefmt=ACTIONS_DATE_FORMAT)

    file_handler = hd.RotatingFileHandler(
        filename=os.path.join(log_dir, 'valutatrade.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8',
    )
    file_handler.setFormatter(formatter)

    console_handler = lg.StreamHandler()
    console_handler.setFormatter(formatter)

    log_level = _get_log_level()
    root_logger = lg.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    actions_logger = lg.getLogger('actions')
    actions_handler = hd.RotatingFileHandler(
        filename=os.path.join(log_dir, 'actions.log'),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8',
    )
    actions_handler.setFormatter(actions_formatter)
    actions_logger.addHandler(actions_handler)
    actions_logger.setLevel(log_level)
    actions_logger.propagate = False


def _get_log_level():
    '''Уровень из окружения или настроек (INFO по умолчанию, DEBUG для отладки).'''
    level_name = os.getenv('VALUTATRADE_LOG_LEVEL', 'INFO')
    try:
        return getattr(lg, level_name.upper(), lg.INFO)
    except (TypeError, AttributeError):
        return lg.INFO


def get_logger(name: str) -> lg.Logger:
    '''Возвращает логгер по имени (например, 'actions').'''
    return lg.getLogger(name)
