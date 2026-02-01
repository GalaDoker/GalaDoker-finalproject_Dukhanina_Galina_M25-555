# valutatrade_hub/core/currencies.py
from abc import ABC, abstractmethod
from typing import Dict

from .exceptions import CurrencyNotFoundError
from .utils import normalize_currency_code, validate_currency_code


class Currency(ABC):
    '''
    Абстрактный базовый класс валюты.
    Инварианты: code — верхний регистр, 2–5 символов, без пробелов; name — не пустая строка.
    '''
    def __init__(self, name: str, code: str):
        self._code = validate_currency_code(code)
        if not name or not name.strip():
            raise ValueError('Ошибка: Название валюты не может быть пустым')
        self._name = name.strip()
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def code(self) -> str:
        return self._code
    
    @abstractmethod
    def get_display_info(self) -> str:
        pass

class FiatCurrency(Currency):
    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code)
        self._issuing_country = issuing_country
    
    def get_display_info(self) -> str:
        return f'[FIAT] {self._code} — {self._name} (Issuing: {self._issuing_country})'
    

class CryptoCurrency(Currency):
    def __init__(self, name: str, code: str, algorithm: str, market_cap: float = 0.0):
        super().__init__(name, code)
        self._algorithm = algorithm
        self._market_cap = market_cap
    
    def get_display_info(self) -> str:
        mcap_str = f'{self._market_cap:.2e}' if self._market_cap > 1e6 else f'{self._market_cap:,.2f}'
        return f'[CRYPTO] {self._code} — {self._name} (Algo: {self._algorithm}, MCAP: {mcap_str})'

# Реестр валют
class CurrencyRegistry:
    _currencies: Dict[str, Currency] = {}
    
    @classmethod
    def register_currency(cls, currency: Currency) -> None:
        """Регистрирует валюту в реестре по её коду."""
        cls._currencies[currency.code] = currency

    @classmethod
    def get_currency(cls, code: str) -> Currency:
        """Возвращает валюту по коду. Вызывает CurrencyNotFoundError, если не найдена."""
        code = normalize_currency_code(code)
        if code not in cls._currencies:
            raise CurrencyNotFoundError(code)
        return cls._currencies[code]

    @classmethod
    def get_all_currencies(cls) -> Dict[str, Currency]:
        """Возвращает копию словаря всех зарегистрированных валют."""
        return cls._currencies.copy()


def initialize_currencies() -> None:
    """Инициализирует базовый набор валют (фиат и криптовалюты) в реестре."""
    CurrencyRegistry.register_currency(FiatCurrency('US Dollar', 'USD', 'United States'))
    CurrencyRegistry.register_currency(FiatCurrency('Euro', 'EUR', 'Eurozone'))
    CurrencyRegistry.register_currency(FiatCurrency('British Pound', 'GBP', 'United Kingdom'))
    CurrencyRegistry.register_currency(FiatCurrency('Russian Ruble', 'RUB', 'Russia'))
    CurrencyRegistry.register_currency(FiatCurrency('Japanese Yen', 'JPY', 'Japan'))
    CurrencyRegistry.register_currency(FiatCurrency('Chinese Yuan', 'CNY', 'China'))
    
    CurrencyRegistry.register_currency(CryptoCurrency('Bitcoin', 'BTC', 'SHA-256', 1.12e12))
    CurrencyRegistry.register_currency(CryptoCurrency('Ethereum', 'ETH', 'Ethash', 4.5e11))
    CurrencyRegistry.register_currency(CryptoCurrency('Solana', 'SOL', 'Proof of History', 6.8e10))
    CurrencyRegistry.register_currency(CryptoCurrency('Cardano', 'ADA', 'Ouroboros', 2.3e10))
    CurrencyRegistry.register_currency(CryptoCurrency('Polkadot', 'DOT', 'Nominated Proof-of-Stake', 1.2e10))

def get_currency(code: str) -> Currency:
    """Возвращает объект валюты по коду. Вызывает CurrencyNotFoundError, если валюта не зарегистрирована."""
    return CurrencyRegistry.get_currency(code)
    
    
