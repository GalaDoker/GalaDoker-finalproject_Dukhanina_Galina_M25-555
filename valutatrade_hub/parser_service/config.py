# valutatrade_hub/parser_service/config.py
"""
Единый файл конфигурации парсера: все изменяемые параметры здесь, без hardcoding в логике.
API-ключ: только из переменной окружения EXCHANGERATE_API_KEY или из локального файла
(не отслеживаемого git), не хранить ключ в коде.
"""
import os
from dataclasses import dataclass, field
from typing import Dict, Tuple


def _read_key_from_file(filepath: str, key_name: str) -> str:
    """
    Читает значение ключа из файла в формате KEY=value.
    Возвращает пустую строку, если ключ не найден или ошибка чтения.
    """
    if not os.path.isfile(filepath):
        return ""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key_name}="):
                    return line.split("=", 1)[1].strip().strip('"\'')
    except OSError:
        pass
    return ""


def _load_api_key_from_env_or_file() -> str:
    """
    Загрузка API-ключа: сначала переменная окружения, затем опционально файл
    .env.parser или parser_secrets.env в корне проекта (файлы в .gitignore).
    """
    key = os.getenv("EXCHANGERATE_API_KEY")
    if key:
        return key
    for name in (".env.parser", "parser_secrets.env"):
        path = os.path.join(os.getcwd(), name)
        value = _read_key_from_file(path, "EXCHANGERATE_API_KEY")
        if value:
            return value
    return ""


@dataclass
class ParserConfig:
    """
    Структурированное хранение настроек парсера (dataclass).
    Чувствительные данные (API-ключ) загружаются из окружения или локального файла.
    """
    # API-ключ: не хранить в коде; из переменной окружения или не отслеживаемого git файла
    EXCHANGERATE_API_KEY: str = field(default_factory=_load_api_key_from_env_or_file)

    # Эндпоинты (полные URL)
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # Базовая валюта для запросов (рекомендуется USD)
    BASE_CURRENCY: str = "USD"

    # Списки валют для отслеживания
    FIAT_CURRENCIES: Tuple[str, ...] = ("EUR", "GBP", "RUB", "JPY", "CNY")
    CRYPTO_CURRENCIES: Tuple[str, ...] = ("BTC", "ETH", "SOL", "ADA", "DOT")

    # Сопоставление кодов и ID для CoinGecko
    CRYPTO_ID_MAP: Dict[str, str] = field(default_factory=lambda: {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "ADA": "cardano",
        "DOT": "polkadot",
    })

    # Сетевые параметры запросов
    REQUEST_TIMEOUT: int = 10
    REQUEST_RETRIES: int = 3
    RETRY_DELAY: float = 1.0

    # Пути к файлам
    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"

    # Параметры обновления (опционально из окружения)
    UPDATE_INTERVAL_MINUTES: int = 5
    RATES_TTL_SECONDS: int = 300

    def __post_init__(self):
        """Создание директории для данных при необходимости."""
        dir_path = os.path.dirname(self.RATES_FILE_PATH)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

    @classmethod
    def from_env(cls) -> "ParserConfig":
        """Создание конфигурации с загрузкой чувствительных данных из переменных окружения."""
        return cls(
            EXCHANGERATE_API_KEY=_load_api_key_from_env_or_file(),
            REQUEST_TIMEOUT=int(os.getenv("PARSER_REQUEST_TIMEOUT", "10")),
            UPDATE_INTERVAL_MINUTES=int(os.getenv("PARSER_UPDATE_INTERVAL", "5")),
            RATES_TTL_SECONDS=int(os.getenv("RATES_TTL_SECONDS", "300")),
        )
    
    def _warn_if_demo_api_key(self) -> None:
        """Выводит предупреждение, если используется демо-ключ ExchangeRate-API."""
        if not self.EXCHANGERATE_API_KEY or self.EXCHANGERATE_API_KEY == 'demo_key':
            print('   ВНИМАНИЕ: Используется демо-ключ ExchangeRate-API!')
            print('   Для работы с фиатными валютами зарегистрируйтесь на:')
            print('   https://app.exchangerate-api.com/sign-up')
            print('   и установите переменную окружения EXCHANGERATE_API_KEY')

    def _validate_currency_codes(self) -> None:
        """Проверяет, что все коды валют в верхнем регистре и содержат только буквы."""
        all_currencies = list(self.FIAT_CURRENCIES) + list(self.CRYPTO_CURRENCIES)
        if not all(
            currency.isalpha() and currency.isupper() for currency in all_currencies
        ):
            raise ValueError(
                'Ошибка: Коды валют должны быть в верхнем регистре и содержать только буквы'
            )

    def _ensure_data_directory(self) -> None:
        """Создаёт директорию для данных, если её нет."""
        data_dir = os.path.dirname(self.RATES_FILE_PATH)
        if not data_dir:
            return
        if not os.path.exists(data_dir):
            try:
                os.makedirs(data_dir, exist_ok=True)
                print(f'Создана директория: {data_dir}')
            except OSError as e:
                raise ValueError(
                    f'Ошибка: Не удалось создать директорию {data_dir}: {e}'
                ) from e

    def validate(self) -> bool:
        """Валидация конфигурации: предупреждение о ключе, проверка валют, создание директории."""
        self._warn_if_demo_api_key()
        self._validate_currency_codes()
        self._ensure_data_directory()
        return True
    
    def get_coingecko_params(self) -> Dict[str, str]:
        '''
        Получение параметров для запроса к CoinGecko (без ключа)
        '''
        crypto_ids = ','.join(
            self.CRYPTO_ID_MAP[currency] 
            for currency in self.CRYPTO_CURRENCIES 
            if currency in self.CRYPTO_ID_MAP
        )
        
        return {
            'ids': crypto_ids,
            'vs_currencies': self.BASE_CURRENCY.lower()
        }
    
    def get_exchangerate_url(self) -> str:
        '''
        Получение URL для запроса к ExchangeRate-API (требует ключ)
        '''
        return f'{self.EXCHANGERATE_API_URL}/{self.EXCHANGERATE_API_KEY}/latest/{self.BASE_CURRENCY}'
