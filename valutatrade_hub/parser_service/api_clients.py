# valutatrade_hub/parser_service/api_clients.py
"""
Изоляция логики работы с внешними сервисами. Унифицированный интерфейс fetch_rates() -> dict,
скрывающий детали (разные URL, форматы ответов). Стандартизированный формат: {"BTC_USD": 59337.21, ...}.
"""
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import requests

from valutatrade_hub.core.exceptions import ApiRequestError


class BaseApiClient(ABC):
    """
    Абстрактный базовый класс для API-клиентов курсов валют.
    Единый метод fetch_rates() -> dict. Детали запроса и парсинга — в реализациях.
    """
    
    def __init__(self, config: Any):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "CurrencyParser/1.0",
            "Accept": "application/json",
        })
    
    @abstractmethod
    def fetch_rates(self) -> Dict[str, float]:
        """Получение курсов в стандартизированном формате {"PAIR": rate, ...}. Реализуется в подклассах."""
        ...
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """
        GET-запрос с повторными попытками. Перехват requests.exceptions.RequestException,
        проверка response.status_code; при ошибке — ApiRequestError с понятным сообщением.
        """
        last_error: Optional[Exception] = None
        for attempt in range(self.config.REQUEST_RETRIES):
            try:
                self.config.validate()
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.config.REQUEST_TIMEOUT,
                )
                if response.status_code != 200:
                    if response.status_code == 429:
                        raise ApiRequestError(
                            "429 Too Many Requests: превышен лимит запросов. "
                            "Подождите или уменьшите частоту обновлений."
                        )
                    raise ApiRequestError(f"HTTP {response.status_code}: {response.text[:200]}")
                return response.json()
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt == self.config.REQUEST_RETRIES - 1:
                    raise ApiRequestError(
                        f"Не удалось выполнить запрос после {self.config.REQUEST_RETRIES} попыток: {last_error}"
                    ) from e
                time.sleep(self.config.RETRY_DELAY * (attempt + 1))
        raise ApiRequestError(f"Все попытки завершились ошибкой: {last_error}")


class CoinGeckoClient(BaseApiClient):
    """
    Клиент CoinGecko API. Формирует URL с ids и vs_currencies (CRYPTO_ID_MAP),
    отправляет GET-запрос, парсит ответ и приводит к формату {"BTC_USD": 59337.21, ...}.
    Обрабатывает ошибки сети и API, выбрасывает ApiRequestError.
    """
    
    def fetch_rates(self) -> Dict[str, float]:
        try:
            params = self.config.get_coingecko_params()
            data = self._make_request(self.config.COINGECKO_URL, params)
        except ApiRequestError:
            raise
        try:
            rates: Dict[str, float] = {}
            base_lower = self.config.BASE_CURRENCY.lower()
            for crypto_code, gecko_id in self.config.CRYPTO_ID_MAP.items():
                if gecko_id in data and isinstance(data[gecko_id], dict) and base_lower in data[gecko_id]:
                    val = data[gecko_id][base_lower]
                    pair_key = f"{crypto_code}_{self.config.BASE_CURRENCY}"
                    rates[pair_key] = float(val)
            return rates
        except (KeyError, TypeError, ValueError) as e:
            raise ApiRequestError(f"Ошибка парсинга ответа CoinGecko: {e}") from e


class ExchangeRateApiClient(BaseApiClient):
    """
    Клиент ExchangeRate-API. Формирует URL с API-ключом и базовой валютой,
    парсит ответ (вложенный словарь conversion_rates), приводит к формату {"EUR_USD": 1.0786, ...}.
    Обрабатывает неверный ключ, лимит запросов, недоступность — ApiRequestError.
    """
    
    def fetch_rates(self) -> Dict[str, float]:
        try:
            url = self.config.get_exchangerate_url()
            data = self._make_request(url)
        except ApiRequestError:
            raise
        if data.get("result") != "success":
            error_type = data.get("error-type", "unknown_error")
            raise ApiRequestError(f"ExchangeRate-API: {error_type} (неверный ключ или лимит запросов)")
        try:
            conversion_rates = data.get("conversion_rates") or {}
            rates: Dict[str, float] = {}
            for currency in self.config.FIAT_CURRENCIES:
                if currency in conversion_rates:
                    pair_key = f"{currency}_{self.config.BASE_CURRENCY}"
                    rates[pair_key] = float(conversion_rates[currency])
            return rates
        except (TypeError, ValueError) as e:
            raise ApiRequestError(f"Ошибка парсинга ответа ExchangeRate-API: {e}") from e
            
            
