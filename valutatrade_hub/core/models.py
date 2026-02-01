# valutatrade_hub/core/models.py
import hashlib
import secrets
from datetime import datetime
from typing import Callable, Dict, Optional

from .currencies import get_currency
from .exceptions import InsufficientFundsError


class User:
    def __init__(self, user_id: int, username: str, password: str, 
                 salt: Optional[str] = None, 
                 registration_date: Optional[datetime] = None):
        self._user_id = user_id
        self.username = username
        self._salt = salt or secrets.token_hex(8)
        self._hashed_password = self._hash_password(password)
        self._registration_date = registration_date or datetime.now()
    
    def _hash_password(self, password: str) -> str:
        '''
        Хеширование пароля с солью
        '''
        return hashlib.sha256((password + self._salt).encode()).hexdigest()
    
    def verify_password(self, password: str) -> bool:
        '''
        Проверка пароля
        '''
        return self._hashed_password == self._hash_password(password)
    
    def change_password(self, new_password: str) -> None:
        '''
        Изменение пароля
        '''
        if len(new_password) < 4:
            raise ValueError('Ошибка: Минимальная длина пароля - 4 символа')
        self._hashed_password = self._hash_password(new_password)
    
    def get_user_info(self) -> str:
        '''
        Информация о пользователе
        '''
        return (f'User ID: {self._user_id}, '
                f'Username: {self._username}, '
                f'Registered: {self._registration_date.strftime('%Y-%m-%d %H:%M')}')
    
    # Геттеры - необходимы для безопасного доступа к атрибутам, нельзя изменить напрямую данные
    @property
    def user_id(self) -> int:
        return self._user_id
    
    @property
    def username(self) -> str:
        return self._username
    
    @username.setter
    def username(self, value: str) -> None:
        if not value or not value.strip():
            raise ValueError('Ошибка: Имя пользователя не может быть пустым')
        self._username = value
    
    @property
    def registration_date(self) -> datetime:
        return self._registration_date

class Wallet:
    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = currency_code.upper()
        self._balance = balance
    
    def deposit(self, amount: float) -> None:
        '''
        Пополнение баланса
        '''
        if amount <= 0:
            raise ValueError('Ошибка: Сумма пополнения должна быть положительной')
        self.balance += amount
    
    def withdraw(self, amount: float) -> None:
        '''
        Снятие средств/Удаление
        '''
        if amount <= 0:
            raise ValueError('Ошибка: Сумма снятия должна быть положительной')
        if amount > self._balance:
            raise InsufficientFundsError(self._balance, amount, self.currency_code)
        self.balance -= amount
    
    def get_balance_info(self) -> str:
        '''
        Информация о балансе
        '''
        return f'{self.currency_code}: {self._balance:.2f}'
    
    @property
    def balance(self) -> float:
        return self._balance
    
    @balance.setter
    def balance(self, value: float) -> None:
        if value < 0:
            raise ValueError('Ошибка: Баланс не может быть отрицательным')
        self._balance = value
        

# Фиктивные курсы для get_total_value при отсутствии get_rate (1 единица валюты = X USD)
_STUB_RATES_TO_USD: Dict[str, float] = {
    'USD': 1.0,
    'EUR': 1.05,
    'GBP': 1.27,
    'RUB': 0.012,
    'JPY': 0.0067,
    'CNY': 0.14,
    'BTC': 97000.0,
    'ETH': 3500.0,
    'SOL': 220.0,
    'ADA': 0.6,
    'DOT': 7.0,
}


class Portfolio:
    def __init__(
        self,
        user_id: int,
        wallets: Optional[Dict[str, Wallet]] = None,
        user: Optional['User'] = None,
    ):
        self._user_id = user_id
        self._wallets = wallets or {}
        self._user = user

    def add_currency(self, currency_code: str) -> None:
        '''
        Добавление новой валюты в портфель (если её ещё нет).
        '''
        currency_code = currency_code.upper()
        if currency_code in self._wallets:
            return
        get_currency(currency_code)
        self._wallets[currency_code] = Wallet(currency_code)

    def get_wallet(self, currency_code: str) -> Wallet:
        '''
        Возвращает кошелёк по коду валюты (создаёт новый, если не существует).
        '''
        currency_code = currency_code.upper()
        if currency_code not in self._wallets:
            self._wallets[currency_code] = Wallet(currency_code, 0.0)
        return self._wallets[currency_code]

    def get_total_value(
        self,
        base_currency: str = 'USD',
        get_rate: Optional[Callable[[str, str], float]] = None,
    ) -> float:
        '''
        Общая стоимость всех валют в базовой валюте (по курсам или фиктивным данным).
        '''
        base_currency = base_currency.upper()
        total = 0.0
        for code, wallet in self._wallets.items():
            if code == base_currency:
                total += wallet.balance
            elif get_rate:
                try:
                    rate = get_rate(code, base_currency)
                    total += wallet.balance * rate
                except Exception:
                    pass
            else:
                # Фиктивные курсы: конвертируем в USD, затем в base_currency
                to_usd = _STUB_RATES_TO_USD.get(code, 0.0)
                usd_value = wallet.balance * to_usd
                if base_currency == 'USD':
                    total += usd_value
                else:
                    usd_per_base = _STUB_RATES_TO_USD.get(base_currency)
                    if usd_per_base and usd_per_base > 0:
                        total += usd_value / usd_per_base
        return total

    @property
    def user(self) -> Optional['User']:
        '''Геттер: объект пользователя (без возможности перезаписи).'''
        return self._user

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def wallets(self) -> Dict[str, Wallet]:
        '''Геттер: копия словаря кошельков.'''
        return self._wallets.copy()
