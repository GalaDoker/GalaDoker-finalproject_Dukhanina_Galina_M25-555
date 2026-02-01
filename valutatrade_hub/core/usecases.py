# valutatrade_hub/core/usecases.py
"""
Бизнес-логика приложения.

Валидация валют через currencies.py: get_currency(code) перед операциями; при неизвестном коде — CurrencyNotFoundError.
Исключения: InsufficientFundsError (buy/sell при нехватке средств), CurrencyNotFoundError (get_currency, get_rate).
DatabaseManager/JSON: все записи через db.update_data(entity, update_fn) — безопасная операция read→modify→write под блокировкой.

Использование синглтонов:
- db (DatabaseManager): load_data(), update_data().
- settings (SettingsLoader): get('rates_ttl_seconds'), get('currency_info_ttl_seconds').

Применение @log_action: register_user, login, buy_currency (verbose=True), sell_currency (verbose=True).
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from valutatrade_hub.decorators import log_action

from ..infra.database import db
from ..infra.settings import settings
from .currencies import get_currency
from .exceptions import (
    AuthenticationError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    UsernamePasswordError,
    UsernameTakenError,
    UserNotFoundError,
)
from .models import Portfolio, User, Wallet
from .utils import convert_amount


class UserManager:
    def __init__(self):
        self.current_user: Optional[User] = None

    @log_action('register')
    def register_user(self, username: str, password: str) -> User:
        '''
        Регистрация нового пользователя
        '''
        if len(password) < 4:
            raise UsernamePasswordError()
        
        users_data = db.load_data('users') or []
        
        if any(user['username'] == username for user in users_data):
            raise UsernameTakenError(username)
        
        try:
            if users_data:
                user_id = max([user['user_id'] for user in users_data]) + 1
            else:
                user_id = 1
            

            user = User(user_id, username, password)
            
            user_data = {
                'user_id': user.user_id,
                'username': user.username,
                'hashed_password': user._hashed_password,
                'salt': user._salt,
                'registration_date': user.registration_date.isoformat()
            }
            
            def update_users(users):
                users.append(user_data)
                return users
            
            db.update_data('users', update_users)
            self._create_portfolio(user_id)
            return user
            
        except Exception:
            import traceback
            traceback.print_exc()
            raise
        
    @log_action('login')
    def login(self, username: str, password: str) -> User:
        '''
        Вход пользователя
        '''
        users_data = db.load_data('users') or []
        
        user_data = next((u for u in users_data if u['username'] == username), None)
        if not user_data:
            raise UserNotFoundError(username)
        
        temp_user = User(
            user_data['user_id'],
            user_data['username'],
            'temp',
            user_data['salt']
        )
        temp_user._hashed_password = user_data['hashed_password']
        
        if not temp_user.verify_password(password):
            raise AuthenticationError()
        
        self.current_user = User(
            user_data['user_id'],
            user_data['username'],
            password,
            user_data['salt']
        )
        
        return self.current_user
    
    def logout(self):
        '''
        Выход пользователя
        '''
        self.current_user = None
    
    def _create_portfolio(self, user_id: int):
        '''
        Создание пустого портфеля для пользователя (user_id + пустой словарь кошельков).
        '''
        new_portfolio = {
            'user_id': user_id,
            'wallets': {}
        }

        def update_portfolios(portfolios_list):
            portfolios_list.append(new_portfolio)
            return portfolios_list

        db.update_data('portfolios', update_portfolios)

class PortfolioManager:
    @log_action('BUY', verbose=True)
    def buy_currency(self, user_id: int, currency_code: str, amount: float, base_currency: str = 'USD') -> Dict[str, Any]:
        '''
        Покупка валюты с списанием базовой валюты
        '''
        if amount <= 0:
            raise ValueError('Количество должно быть положительным')
        
        get_currency(currency_code)
        get_currency(base_currency)

        portfolio = self.get_user_portfolio(user_id)
        rate_manager = RateManager()
        rate, _ = rate_manager.get_rate(currency_code, base_currency)
        cost_in_base_currency = convert_amount(amount, rate)

        base_wallet = portfolio.get_wallet(base_currency)
        if base_wallet.balance < cost_in_base_currency:
            raise InsufficientFundsError(
                base_wallet.balance, cost_in_base_currency, base_currency
            )
        old_base_balance = base_wallet.balance
        base_wallet.withdraw(cost_in_base_currency)
        
        target_wallet = portfolio.get_wallet(currency_code)
        old_target_balance = target_wallet.balance
        old_base_balance = base_wallet.balance
        target_wallet.deposit(amount)
        
        self.save_portfolio(portfolio)
        
        return {
            'currency': currency_code,
            'amount': amount,
            'cost': cost_in_base_currency,
            'rate': rate,
            'old_balance': old_target_balance,
            'new_balance': target_wallet.balance,
            'base_currency_old_balance': old_base_balance,
            'base_currency_new_balance': base_wallet.balance
        }

    @log_action('SELL', verbose=True)
    def sell_currency(self, user_id: int, currency_code: str, amount: float, base_currency: str = 'USD') -> Dict[str, Any]:
        '''
        Продажа валюты с зачислением базовой валюты
        '''
        if amount <= 0:
            raise ValueError('Ошибка: Количество должно быть положительным')
        
        if currency_code == base_currency:
            raise ValueError(f'Ошибка: Базовую валюту {base_currency} нельзя продать')
        get_currency(currency_code)
        get_currency(base_currency)

        portfolio = self.get_user_portfolio(user_id)
        if currency_code not in portfolio.wallets:
            raise ValueError(f'Ошибка: Не существует кошелька "{currency_code}"')
        
        wallet = portfolio.wallets[currency_code]
        old_balance = wallet.balance
        if amount > wallet.balance:
            raise InsufficientFundsError(wallet.balance, amount, currency_code)
        rate_manager = RateManager()
        rate, _ = rate_manager.get_rate(currency_code, base_currency)
        revenue_in_base_currency = convert_amount(amount, rate)
        
        wallet.withdraw(amount)
        
        base_wallet = portfolio.get_wallet(base_currency)
        old_base_balance = base_wallet.balance
        base_wallet.deposit(revenue_in_base_currency)
        
        self.save_portfolio(portfolio)
        
        return {
            'currency': currency_code,
            'amount': amount,
            'revenue': revenue_in_base_currency,
            'rate': rate,
            'old_balance': old_balance,
            'new_balance': wallet.balance,
            'base_currency_old_balance': old_base_balance,
            'base_currency_new_balance': base_wallet.balance
        }
    
    def get_user_portfolio(self, user_id: int) -> Portfolio:
        '''
        Получение портфеля пользователя
        '''
        portfolios_data = db.load_data('portfolios') or []
        
        portfolio_data = next((p for p in portfolios_data if p['user_id'] == user_id), None)
        if not portfolio_data:
            raise ValueError(f'Портфель для пользователя {user_id} не найден')
        
        wallets = {}
        for currency_code, wallet_data in portfolio_data['wallets'].items():
            wallets[currency_code] = Wallet(currency_code, wallet_data['balance'])
        
        return Portfolio(user_id, wallets)
    
    def save_portfolio(self, portfolio: Portfolio):
        '''
        Сохранение портфеля
        '''
        def update_portfolios(portfolios_data):
            for i, portfolio_data in enumerate(portfolios_data):
                if portfolio_data['user_id'] == portfolio.user_id:
                    wallets_data = {}
                    for currency_code, wallet in portfolio.wallets.items():
                        wallets_data[currency_code] = {
                            'balance': wallet.balance
                        }
                    portfolios_data[i]['wallets'] = wallets_data
                    break
            else:
                wallets_data = {}
                for currency_code, wallet in portfolio.wallets.items():
                    wallets_data[currency_code] = {
                        'balance': wallet.balance
                    }
                portfolios_data.append({
                    'user_id': portfolio.user_id,
                    'wallets': wallets_data
                })
            
            return portfolios_data
        
        db.update_data('portfolios', update_portfolios)


class RateManager:
    def __init__(self):
        self.rates_ttl = settings.get('rates_ttl_seconds', 300)
        self.currency_info_ttl = settings.get('currency_info_ttl_seconds', 3600)
    
    def is_rates_data_fresh(self) -> bool:
        '''
        Проверяет, актуальны ли данные о курсах. TTL из SettingsLoader.
        '''
        rates_data = db.load_data('rates') or {}
        ts = rates_data.get('last_refresh') or rates_data.get('timestamp')
        if not ts:
            return False
        try:
            last_update = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            time_diff = datetime.now(timezone.utc) - last_update
            return time_diff.total_seconds() < self.rates_ttl
        except (ValueError, TypeError):
            return False
    
    def is_currency_info_fresh(self) -> bool:
        '''
        Проверяет, актуальны ли данные о валютах
        '''
        currency_info_data = db.load_data('currency_info') or {}
        
        if not currency_info_data.get('timestamp'):
            return False
        
        try:
            last_update = datetime.fromisoformat(currency_info_data['timestamp'])
            time_diff = datetime.now() - last_update
            return time_diff.total_seconds() < self.currency_info_ttl
        except (ValueError, TypeError):
            return False
    
    def get_rate(self, from_currency: str, to_currency: str) -> Tuple[float, Optional[str]]:
        '''
        Получение курса из кеша rates.json (снимок: pairs с rate, updated_at, source). TTL из SettingsLoader.
        Валидация кодов через get_currency() — иначе CurrencyNotFoundError.
        Возврат: (значение курса, updated_at из кеша или None).
        '''
        if from_currency == to_currency:
            raise ValueError('Исходная и целевая валюта совпадают')
        get_currency(from_currency)
        get_currency(to_currency)

        rates_data = db.load_data('rates') or {}
        pairs = rates_data.get('pairs', {})
        if not pairs and rates_data.get('rates') is not None:
            # Legacy: rates + timestamp
            pairs = {
                pair: {'rate': v, 'updated_at': rates_data.get('timestamp')}
                for pair, v in rates_data.get('rates', {}).items()
            }
        updated_at = rates_data.get('last_refresh') or rates_data.get('timestamp')

        direct_pair = f'{from_currency}_{to_currency}'
        if direct_pair in pairs:
            info = pairs[direct_pair]
            return (float(info['rate']), info.get('updated_at') or updated_at)
        reverse_pair = f'{to_currency}_{from_currency}'
        if reverse_pair in pairs:
            info = pairs[reverse_pair]
            rev = float(info['rate'])
            return (1.0 / rev if rev else 0.0, info.get('updated_at') or updated_at)
        raise CurrencyNotFoundError(f'{from_currency}→{to_currency}')
      
    def get_rates_age(self) -> str:
        '''
        Возвращает возраст данных о курсах в читаемом формате (по last_refresh).
        '''
        rates_data = db.load_data('rates') or {}
        ts = rates_data.get('last_refresh') or rates_data.get('timestamp')
        if not ts:
            return 'данные отсутствуют'
        try:
            last_update = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            time_diff = datetime.now(timezone.utc) - last_update
            minutes = int(time_diff.total_seconds() // 60)
            if minutes < 1:
                return 'только что'
            elif minutes < 60:
                return f'{minutes} минут назад'
            else:
                hours = minutes // 60
                return f'{hours} часов назад'
        except (ValueError, TypeError):
            return 'неизвестно'
    
    def _get_simple_stub_rate(self, from_currency: str, to_currency: str) -> float:
        '''
        Простая заглушка без рекурсии
        '''
        stub_rates = {
            'BTC_USD': 111701.0,
            'ETH_USD': 3950.39,
            'SOL_USD': 194.12,
            'ADA_USD': 0.655614,
            'DOT_USD': 3.1,
            'EUR_USD': 0.8602,
            'GBP_USD': 0.7512,
            'RUB_USD': 81.0309,
            'JPY_USD': 152.8245,
            'CNY_USD': 7.1274,
            'USD_BTC': 1/111701.0,
            'USD_ETH': 1/3950.39,
            'USD_SOL': 1/194.12,
            'USD_ADA': 1/0.655614,
            'USD_DOT': 1/3.1,
            'USD_EUR': 1/0.8602,
            'USD_GBP': 1/0.7512,
            'USD_RUB': 1/81.0309,
            'USD_JPY': 1/152.8245,
            'USD_CNY': 1/7.1274,
        }
        
        pair_key = f'{from_currency}_{to_currency}'
        if pair_key in stub_rates:
            return stub_rates[pair_key]
        
        return 1.0
