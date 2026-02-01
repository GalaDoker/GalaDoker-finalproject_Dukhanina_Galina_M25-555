# valutatrade_hub/cli/interface.py
import os
import sys

from ..core.currencies import get_currency
from ..core.exceptions import (
    ApiRequestError,
    AuthenticationError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    UsernamePasswordError,
    UsernameTakenError,
    UserNotFoundError,
)
from ..infra.database import db


class InteractiveCLI:
    def __init__(self):
        from ..core.currencies import CurrencyRegistry, initialize_currencies
        from ..core.usecases import PortfolioManager, RateManager, UserManager
        from ..logging_config import setup_logging
        from ..parser_service.config import ParserConfig
        from ..parser_service.scheduler import Scheduler
        from ..parser_service.updater import RatesUpdater
        
        self.parser_config = ParserConfig.from_env()
        self.rates_updater = RatesUpdater(self.parser_config)
        self.scheduler = Scheduler(self.parser_config)

        setup_logging()
        initialize_currencies()
        
        self.user_manager = UserManager()
        self.portfolio_manager = PortfolioManager()
        self.rate_manager = RateManager()
        self.currency_registry = CurrencyRegistry
        
        self.menu_options = {
            'register': ('Register', self.register),
            'login': ('Login', self.login),
            'portfolio': ('Show-portfolio', self.show_portfolio),
            'buy': ('Buy currency', self.buy_currency),
            'sell': ('Sell currency', self.sell_currency),
            'get-rate': ('Get-rate', self.get_single_rate),
            'show-rates': ('Show-rates', self.show_rates_command),
            'update': ('Update-rates', self.update_rates),
            'update-rates': ('Update-rates', self.update_rates),
            'parser': ('Status-parser', self.parser_status),
            'autoupdate': ('Run autoupdate', self.start_auto_update),
            'stop': ('Stop autoupdate', self.stop_auto_update),
            'exit': ('Exit', self.exit_app),
            'quit': ('Exit', self.exit_app)
        }
        
        self.digit_mapping = {
            '1': 'register',
            '2': 'login', 
            '3': 'portfolio',
            '4': 'buy',
            '5': 'sell',
            '6': 'get-rate',
            '7': 'show-rates',
            '8': 'update',
            '9': 'parser',
            '10': 'autoupdate',
            '11': 'stop',
            '12': 'exit'
        }
        
        self.menu_options_desc = {
            'register': 'Зарегистрировать новый аккаунт',
            'login': 'Войти в существующий аккаунт',
            'portfolio': 'Просмотреть свое портфолио',
            'buy': 'Купить валюту',
            'sell': 'Продать валюту',
            'get-rate': 'Получить курс одной валюты к другой',
            'show-rates': 'Показать текущие выгруженные курсы',
            'update': 'Обновить текущие курсы',
            'update-rates': 'Обновить текущие курсы (CLI update-rates)',
            'parser': 'Запустить парсер',
            'autoupdate': 'Запустить автообновление',
            'stop': 'Выключить автообновление',
            'exit': 'Выйти из программы',
            'quit': 'Так же выйти из программы'
        }

    def _currency_not_found_hint(self) -> str:
        '''Подсказка при CurrencyNotFoundError: get-rate или список кодов.'''
        codes = ', '.join(sorted(self.currency_registry.get_all_currencies().keys()))
        return f'Используйте get-rate для списка курсов. Поддерживаемые коды: {codes}'

    def _api_error_hint(self) -> str:
        '''Подсказка при ApiRequestError.'''
        return 'Повторите позже или проверьте подключение к сети.'

    def update_rates(self):
        """
        Команда update-rates: немедленное обновление курсов.
        Опционально --source: обновить только из указанного источника (coingecko или exchangerate).
        Инициализирует RatesUpdater, вызывает run_update(), перехватывает ApiRequestError,
        сообщает об успехе (кол-во курсов, last_refresh) или о завершении с ошибками.
        """
        self.clear_screen()
        self.print_header('Процедура: Обновление курсов валют (update-rates)')
        print('Источник (опционально):')
        print('  1. Все источники (по умолчанию)')
        print('  2. Только CoinGecko (coingecko)')
        print('  3. Только ExchangeRate-API (exchangerate)')
        print()
        choice = input('Ваш выбор (1-3, Enter = все): ').strip() or '1'
        source_map = {'1': None, '2': 'coingecko', '3': 'exchangerate'}
        source = source_map.get(choice)
        if source is None and choice != '1':
            print('Ошибка: Неверный выбор. Используется все источники.')
            source = None

        try:
            print()
            print('INFO: Starting rates update...')
            rates, failed_sources = self.rates_updater.run_update(source)
            status = self.rates_updater.get_update_status()
            last_refresh = status.get('last_refresh') or '—'

            if failed_sources:
                print('Update completed with errors. Check logs/valutatrade.log for details.')
            if rates:
                print(f'INFO: Writing {len(rates)} rates to data/rates.json...')
                print(f'Update successful. Total rates updated: {len(rates)}. Last refresh: {last_refresh}')
            else:
                if failed_sources:
                    print('Ни один источник не вернул данные. Проверьте сеть и ключ ExchangeRate-API.')
                else:
                    print('Нет данных для сохранения.')
        except ApiRequestError as e:
            print(f'ERROR: {e}')
            print(self._api_error_hint())
        except Exception as e:
            print(f'ERROR: Ошибка при обновлении: {e}')

        self.wait_for_enter()
    
    def parser_status(self):
        '''
        Статус парсера
        '''
        self.clear_screen()
        self.print_header('Процедура: Статус парсера')
        
        try:
            status = self.rates_updater.get_update_status()
            
            print('Статус обновления курсов:')
            print(f'Последнее обновление: {status['last_refresh'] or 'Никогда'}')
            print(f'Количество пар: {status['total_pairs']}')
            print(f'Источник: {status['source']}')
            
            rates_data = db.load_data('rates') or {}
            pairs = rates_data.get('pairs', {})
            if not pairs and rates_data.get('rates'):
                pairs = {k: {'rate': v} for k, v in rates_data['rates'].items()}
            pair_list = list(pairs.keys())[:5]
            print('\nПримеры текущих курсов:')
            for pair in pair_list:
                rate_val = pairs[pair].get('rate', pairs[pair]) if isinstance(pairs[pair], dict) else pairs[pair]
                print(f'   {pair}: {float(rate_val):.6f}')
            
        except Exception as e:
            print(f'Ошибка: Произошла ошибка: {e}')
        
        self.wait_for_enter()
    
    def start_auto_update(self):
        '''
        Запуск автоматического обновления
        '''
        self.clear_screen()
        self.print_header('Процедура: Автообновление курсов')
        
        try:
            self.scheduler.start()
            print('Автообновление запущено!')
            print(f'Интервал: {self.parser_config.UPDATE_INTERVAL_MINUTES} минут')
            print('Приложение продолжит работу в обычном режиме')
            
        except Exception as e:
            print(f'Ошибка: Произошла ошибка: {e}')
        
        self.wait_for_enter()
    
    def stop_auto_update(self):
        '''
        Остановка автоматического обновления
        '''
        self.clear_screen()
        self.print_header('Процедура: Остановка автообновления...')
        
        try:
            self.scheduler.stop()
            print('Автообновление успешно остановлено!')
            
        except Exception as e:
            print(f'Ошибка: Произошла ошибка: {e}')
        
        self.wait_for_enter()
    
    def clear_screen(self):
        '''
        Очистка экрана
        '''
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self, title: str):
        '''
        Печать заголовка
        '''
        print('-' * 50)
        print(f'ValutaTrade Hub - {title}')
        print('-' * 50)
        if self.user_manager.current_user:
            print(f'Пользователь: {self.user_manager.current_user.username}')
            reg = self.user_manager.current_user.registration_date
            print(f'Дата регистрации: {reg.strftime("%Y-%m-%d %H:%M")}')
        print()
    
    def wait_for_enter(self):
        '''
        Ожидание нажатия Enter
        '''
        input('\nНажмите Enter для продолжения...')
    
    def get_user_input(self, prompt: str, required: bool = True) -> str:
        '''
        Получение ввода от пользователя
        '''
        while True:
            value = input(prompt).strip()
            if not value and required:
                print('Ошибка: Это поле обязательно для заполнения!')
                continue
            return value
    
    def get_float_input(self, prompt: str) -> float:
        '''
        Получение числового ввода
        '''
        while True:
            try:
                value = float(input(prompt))
                if value <= 0:
                    print('Ошибка: Значение должно быть положительным!')
                    continue
                return value
            except ValueError:
                print('Ошибка: Пожалуйста, введите число!')
    
    def show_main_menu(self):
        '''
        Отображение главного меню с поддержкой цифр и слов
        '''
        print('\n' + '-'*50)
        print('          VALUTATRADE HUB - главное меню')
        print('-'*50)
        
        for digit, command in self.digit_mapping.items():
            print(f'{digit:2} -> {command} - {self.menu_options_desc[command]}')
        
        print('-'*50)
        
    
    def register(self):
        '''
        Регистрация пользователя
        '''
        self.clear_screen()
        self.print_header('Процедура: Регистрация')
        
        username = self.get_user_input('Введите имя пользователя: ')
        password = self.get_user_input('Введите пароль: ')
        
        try:
            user = self.user_manager.register_user(username, password)
            print(
                f"\nПользователь '{user.username}' зарегистрирован (id={user.user_id}). "
                "Стартовый счёт: 10 000 USD. Выберите команду login для входа."
            )
        except UsernameTakenError as e:
            print(f'\n{e}')
        except UsernamePasswordError as e:
            print(f'\n{e}')
        except Exception as e:
            print(f'\nОшибка: Произошла ошибка: {e}')
        
        self.wait_for_enter()
    
    def login(self):
        '''
        Вход пользователя
        '''
        self.clear_screen()
        self.print_header('Процедура: Вход в систему')
        
        username = self.get_user_input('Имя пользователя: ')
        password = self.get_user_input('Пароль: ')
        
        try:
            user = self.user_manager.login(username, password)
            print(f"\nВы вошли как '{user.username}'")
        except UserNotFoundError as e:
            print(f'\n{e}')
        except AuthenticationError as e:
            print(f'\n{e}')
        except Exception as e:
            print(f'\nОшибка: Произошла ошибка: {e}')
        
        self.wait_for_enter()
    
    def show_portfolio(self):
        '''
        Показать портфель: все кошельки и итоговая стоимость в базовой валюте (по умолчанию USD).
        '''
        if not self.user_manager.current_user:
            print('\nОшибка: Сначала выполните вход (команда login).')
            self.wait_for_enter()
            return

        self.clear_screen()
        self.print_header('Процедура: Ваш портфель')

        base_input = input('Базовая валюта (Enter = USD): ').strip()
        base_currency = (base_input or 'USD').upper()

        try:
            get_currency(base_currency)
        except CurrencyNotFoundError as e:
            print(f'\n{e}')
            print(self._currency_not_found_hint())
            self.wait_for_enter()
            return

        try:
            portfolio = self.portfolio_manager.get_user_portfolio(
                self.user_manager.current_user.user_id
            )

            if not portfolio.wallets:
                print('\nПортфель пуст. Используйте buy для покупки валюты.')
                self.wait_for_enter()
                return

            total_value = portfolio.get_total_value(
                base_currency,
                get_rate=lambda c, b: self.rate_manager.get_rate(c, b)[0],
            )

            username = self.user_manager.current_user.username
            print(f"\nПортфель пользователя '{username}' (база: {base_currency}):")

            for currency_code, wallet in portfolio.wallets.items():
                if currency_code == base_currency:
                    value = wallet.balance
                else:
                    try:
                        rate = self.rate_manager.get_rate(currency_code, base_currency)[0]
                        value = wallet.balance * rate
                    except Exception:
                        value = 0.0

                balance_fmt = f'{wallet.balance:.4f}' if currency_code in ('BTC', 'ETH') else f'{wallet.balance:.2f}'
                value_fmt = f'{value:,.2f}' if value >= 1000 else f'{value:.2f}'
                print(f"- {currency_code}: {balance_fmt}  → {value_fmt} {base_currency}")

            print("---------------------------------")
            total_fmt = f'{total_value:,.2f}' if total_value >= 1000 else f'{total_value:.2f}'
            print(f"ИТОГО: {total_fmt} {base_currency}")

        except Exception as e:
            print(f'\nОшибка: Произошла ошибка: {e}')

        self.wait_for_enter()
    
    def buy_currency(self):
        '''
        Покупка валюты
        '''
        if not self.user_manager.current_user:
            print('\nОшибка: Сначала выполните вход!')
            self.wait_for_enter()
            return
        
        self.clear_screen()
        self.print_header('Процедура: Покупка валюты')
        
        try:
            currency_code = self.get_user_input('Код валюты (например, BTC, EUR): ').upper()
            amount = self.get_float_input('Количество для покупки: ')
            
            if currency_code == 'USD':
                print('Ошибка: Нельзя покупать USD, так как это базовая валюта!')
                self.wait_for_enter()
                return
            
            portfolio = self.portfolio_manager.get_user_portfolio(
                self.user_manager.current_user.user_id
            )
            
            if 'USD' not in portfolio.wallets or portfolio.wallets['USD'].balance <= 0:
                print('Ошибка: У вас нет средств в USD для покупки!')
                self.wait_for_enter()
                return
            
            try:
                if not self.rate_manager.is_rates_data_fresh():
                    age = self.rate_manager.get_rates_age()
                    print(f'\n⚠ Данные курсов могут быть устаревшими ({age}).')
                    print('  Для актуальных курсов выполните команду update-rates.\n')
                rate = self.rate_manager.get_rate(currency_code, 'USD')[0]
            except CurrencyNotFoundError as e:
                print(f'\n{e}')
                print(self._currency_not_found_hint())
                self.wait_for_enter()
                return
            except Exception:
                print(f'\nНе удалось получить курс для {currency_code}→USD')
                self.wait_for_enter()
                return

            cost = amount * rate
            usd_balance = portfolio.wallets['USD'].balance
            
            print('\n Детали покупки:')
            print(f'   Валюта: {currency_code}')
            print(f'   Количество: {amount}')
            print(f'   Текущий курс: 1 {currency_code} = {rate:.6f} USD')
            print(f'   Общая стоимость: {cost:,.2f} USD')
            print(f'   Ваш текущий баланс USD: {usd_balance:,.2f}')
            print(f'   Баланс после покупки: {usd_balance - cost:,.2f} USD')
            
            if cost > usd_balance:
                print('\n Ошибка: Недостаточно средств!')
                print(f'   Требуется: {cost:,.2f} USD')
                print(f'   Доступно: {usd_balance:,.2f} USD')
                self.wait_for_enter()
                return
            
            confirm = input('\nПодтвердить покупку? (y/n): ').lower()
            if confirm == 'y':
                try:
                    result = self.portfolio_manager.buy_currency(
                        self.user_manager.current_user.user_id,
                        currency_code,
                        amount,
                        'USD'
                    )
                    rate = result['rate']
                    cost = result['cost']
                    old_bal = result['old_balance']
                    new_bal = result['new_balance']
                    amount_fmt = f'{amount:.4f}' if currency_code in ('BTC', 'ETH') else f'{amount:.2f}'
                    rate_fmt = f'{rate:,.2f}' if rate >= 1000 else f'{rate:.2f}'
                    cost_fmt = f'{cost:,.2f}' if cost >= 1000 else f'{cost:.2f}'
                    old_fmt = f'{old_bal:.4f}' if currency_code in ('BTC', 'ETH') else f'{old_bal:.2f}'
                    new_fmt = f'{new_bal:.4f}' if currency_code in ('BTC', 'ETH') else f'{new_bal:.2f}'
                    print(f'\nПокупка выполнена: {amount_fmt} {currency_code} по курсу {rate_fmt} USD/{currency_code}')
                    print('Изменения в портфеле:')
                    print(f'- {currency_code}: было {old_fmt} → стало {new_fmt}')
                    print(f'Оценочная стоимость покупки: {cost_fmt} USD')
                except ValueError as e:
                    print(f'\n{e}')
                except CurrencyNotFoundError as e:
                    print(f'\n{e}')
                    print(self._currency_not_found_hint())
                except InsufficientFundsError as e:
                    print(f'\n{e}')
                except Exception as e:
                    print(f'\nОшибка: Ошибка при выполнении операции: {repr(e)}')
                    import traceback
                    traceback.print_exc()
            else:
                print('\nПокупка отменена.')
        
        except Exception as e:
            print(f'\nОшибка: Общая ошибка: {repr(e)}')
            import traceback
            traceback.print_exc()
        
        self.wait_for_enter()
    
    def sell_currency(self):
        '''
        Продажа валюты
        '''
        if not self.user_manager.current_user:
            print('\nОшибка: Сначала выполните вход!')
            self.wait_for_enter()
            return
        
        self.clear_screen()
        self.print_header('Процедура: Продажа валюты')
        
        try:
            portfolio = self.portfolio_manager.get_user_portfolio(
                self.user_manager.current_user.user_id
            )
            
            if not portfolio.wallets:
                print('Ошибка: Ваш портфель пуст.')
                self.wait_for_enter()
                return
            
            available_currencies = []
            print('Доступные валюты для продажи:')
            for currency_code, wallet in portfolio.wallets.items():
                if wallet.balance > 0 and currency_code != 'USD':
                    available_currencies.append(currency_code)
                    balance_str = f'{wallet.balance:.8f}' if currency_code in ['BTC', 'ETH'] else f'{wallet.balance:.4f}'
                    print(f'  {currency_code}: {balance_str}')
            
            if not available_currencies:
                print('Ошибка: У вас нет валют для продажи!')
                self.wait_for_enter()
                return
            
            print()
            currency_code = self.get_user_input('Код валюты для продажи: ').upper()
            
            if currency_code not in available_currencies:
                print(f'\nОшибка: У вас нет валюты {currency_code} для продажи или валюта недоступна!')
                self.wait_for_enter()
                return
            
            wallet = portfolio.wallets[currency_code]
            max_amount = wallet.balance
            
            print(f'\nДоступно для продажи: {max_amount} {currency_code}')
            amount = self.get_float_input('Количество для продажи: ')
            
            if amount > max_amount:
                print(f'\n Ошибка: Недостаточно средств! Доступно: {max_amount} {currency_code}')
                self.wait_for_enter()
                return
            
            try:
                if not self.rate_manager.is_rates_data_fresh():
                    age = self.rate_manager.get_rates_age()
                    print(f'\n⚠ Данные курсов могут быть устаревшими ({age}).')
                    print('  Для актуальных курсов выполните команду update-rates.\n')
                rate = self.rate_manager.get_rate(currency_code, 'USD')[0]
                revenue = amount * rate
                current_usd_balance = portfolio.wallets['USD'].balance if 'USD' in portfolio.wallets else 0
                print('\nДетали продажи:')
                print(f'   Валюта: {currency_code}')
                print(f'   Количество: {amount}')
                print(f'   Текущий курс: 1 {currency_code} = {rate:.6f} USD')
                print(f'   Общая выручка: {revenue:,.2f} USD')
                print(f'   Текущий баланс USD: {current_usd_balance:,.2f}')
                print(f'   Баланс USD после продажи: {current_usd_balance + revenue:,.2f}')
            except CurrencyNotFoundError as e:
                print(f'\n{e}')
                print(self._currency_not_found_hint())
                self.wait_for_enter()
                return
            except Exception:
                print(f'\nНе удалось получить курс для {currency_code}→USD')
                self.wait_for_enter()
                return

            confirm = input('\nПодтвердить продажу? (y/n): ').lower()
            if confirm == 'y':
                try:
                    result = self.portfolio_manager.sell_currency(
                        self.user_manager.current_user.user_id,
                        currency_code,
                        amount,
                        'USD'
                    )
                    
                    print('\nПродажа выполнена успешно!')
                    print(f'   Продано: {amount} {currency_code}')
                    print(f'   Выручка: {revenue:,.2f} USD')
                    print(f'   Новый баланс {currency_code}: {result["new_balance"]}')
                    print(f'   Новый баланс USD: {result["base_currency_new_balance"]:,.2f}')
                except ValueError as e:
                    print(f'\n{e}')
                except CurrencyNotFoundError as e:
                    print(f'\n{e}')
                    print(self._currency_not_found_hint())
                except InsufficientFundsError as e:
                    print(f'\n{e}')
                except Exception as e:
                    print(f'\nОшибка: Ошибка при выполнении операции: {repr(e)}')
                    import traceback
                    traceback.print_exc()
            else:
                print('\nПродажа отменена.')
        
        except Exception as e:
            print(f'\n Ошибка: Общая ошибка: {repr(e)}')
            import traceback
            traceback.print_exc()
        
        self.wait_for_enter()

    def get_single_rate(self):
        '''
        Получить текущий курс одной валюты к другой (--from, --to).
        Валидация кодов, кеш rates.json: если свежий — показать;
        иначе обновить кеш (Parser), затем показать курс и метку времени.
        '''
        self.clear_screen()
        self.print_header('Процедура: Курс валюты (get-rate)')

        from_currency = self.get_user_input('Исходная валюта (from, напр. USD): ').strip().upper()
        to_currency = self.get_user_input('Целевая валюта (to, напр. BTC): ').strip().upper()

        if not from_currency or not to_currency:
            print('\nКоды валют не могут быть пустыми.')
            self.wait_for_enter()
            return

        if from_currency == to_currency:
            print('\nИсходная и целевая валюта совпадают. Курс: 1.0000')
            self.wait_for_enter()
            return

        try:
            get_currency(from_currency)
            get_currency(to_currency)
        except CurrencyNotFoundError as e:
            print(f'\n{e}')
            print(self._currency_not_found_hint())
            self.wait_for_enter()
            return

        try:
            if not self.rate_manager.is_rates_data_fresh():
                try:
                    self.rates_updater.run_update()  # (rates, failed_sources) — результат не используется
                except ApiRequestError as e:
                    print(f'\n{e}')
                    print(self._api_error_hint())
                    self.wait_for_enter()
                    return
                except Exception:
                    pass

            rate, updated_at = self.rate_manager.get_rate(from_currency, to_currency)
            age_str = self.rate_manager.get_rates_age()

            rate_fmt = f'{rate:,.4f}' if rate >= 1000 else f'{rate:.4f}'
            print(f'\nКурс {from_currency}→{to_currency}: {rate_fmt}')
            print(f'Метка времени: {updated_at or "—"} ({age_str})')
        except CurrencyNotFoundError as e:
            print(f'\n{e}')
            print(self._currency_not_found_hint())
        except ApiRequestError as e:
            print(f'\n{e}')
            print(self._api_error_hint())
        except Exception as e:
            print(f'\nОшибка: {e}')
        self.wait_for_enter()

    def show_rates_command(self):
        """
        Команда show-rates: список актуальных курсов из локального кеша (data/rates.json).
        Аргументы (интерактивно): --currency, --top, --base.
        """
        self.clear_screen()
        self.print_header('Процедура: Показать курсы валют (show-rates)')
        print('Фильтры (опционально):')
        print('  --currency <код> — только указанная валюта (например, BTC)')
        print('  --top <N>       — N самых дорогих по курсу')
        print('  --base <код>    — курсы относительно базы (например, EUR); по умолчанию USD')
        print()
        currency = input('Валюта (Enter = все): ').strip() or None
        top_input = input('Топ N (Enter = все): ').strip()
        base_input = input('База (Enter = USD): ').strip().upper() or 'USD'
        top = None
        if top_input:
            try:
                top = int(top_input)
                if top <= 0:
                    print('Ошибка: Число должно быть положительным.')
                    self.wait_for_enter()
                    return
            except ValueError:
                print('Ошибка: Неверный формат числа.')
                self.wait_for_enter()
                return
        self.show_rates(currency=currency, top=top, base=base_input)

    def show_rates(self, currency: str = None, top: int = None, base: str = None):
        """
        Показать курсы из data/rates.json с фильтрами --currency, --top, --base.
        Читает кеш, применяет фильтры, сортирует, выводит таблицу и время обновления.
        Ошибки: пустой/не найден кеш → сообщение про update-rates; валюта не найдена → курс не найден в кеше.
        """
        base_currency = (base or 'USD').upper()
        try:
            rates_data = db.load_data('rates') or {}
            pairs = rates_data.get('pairs', {})
            if not pairs and rates_data.get('rates') is not None:
                pairs = {
                    p: {'rate': v, 'updated_at': rates_data.get('timestamp'), 'source': ''}
                    for p, v in rates_data.get('rates', {}).items()
                }
            timestamp = rates_data.get('last_refresh') or rates_data.get('timestamp') or '—'

            if not pairs:
                print("Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные.")
                self.wait_for_enter()
                return

            # Строим список курсов относительно базы (в т.ч. база != USD через пересчёт)
            rows = []
            base_rate_to_usd = None
            for pair, info in pairs.items():
                if '_' not in pair:
                    continue
                rate_val = float(info.get('rate') if isinstance(info, dict) else info or 0)
                from_c, to_c = pair.split('_', 1)
                updated_at = info.get('updated_at') if isinstance(info, dict) else timestamp
                source = info.get('source', '') if isinstance(info, dict) else ''
                if from_c == base_currency and to_c == 'USD':
                    base_rate_to_usd = rate_val
                elif to_c == base_currency and from_c == 'USD':
                    base_rate_to_usd = 1.0 / rate_val if rate_val else None
                rows.append({
                    'pair': pair,
                    'from_currency': from_c,
                    'to_currency': to_c,
                    'rate_to_usd': rate_val if to_c == 'USD' else (1.0 / rate_val if rate_val else 0),
                    'updated_at': updated_at,
                    'source': source,
                })

            if base_currency != 'USD' and base_rate_to_usd is None:
                for r in rows:
                    if r['from_currency'] == base_currency and r['to_currency'] == 'USD':
                        base_rate_to_usd = r['rate_to_usd']
                        break
                    if r['from_currency'] == 'USD' and r['to_currency'] == base_currency:
                        base_rate_to_usd = 1.0 / r['rate_to_usd'] if r['rate_to_usd'] else None
                        break
                if base_rate_to_usd is None:
                    base_rate_to_usd = 1.0

            display_list = []
            for r in rows:
                to_usd = r['rate_to_usd']
                curr = r['from_currency'] if r['to_currency'] == 'USD' else r['to_currency']
                if base_currency == 'USD':
                    rate_in_base = to_usd if r['to_currency'] == 'USD' else (1.0 / to_usd if to_usd else 0)
                    pair_display = f"{curr}_USD"
                else:
                    rate_in_base = to_usd / base_rate_to_usd if base_rate_to_usd else 0
                    pair_display = f"{curr}_{base_currency}"
                display_list.append({
                    'pair': pair_display,
                    'rate': rate_in_base,
                    'updated_at': r['updated_at'],
                    'source': r['source'],
                    'currency': curr,
                })

            if currency:
                display_list = [x for x in display_list if x['currency'].upper() == currency.upper()]
                if not display_list:
                    print(f"Курс для '{currency}' не найден в кеше.")
                    self.wait_for_enter()
                    return

            if top:
                display_list.sort(key=lambda x: x['rate'], reverse=True)
                display_list = display_list[:top]
            else:
                display_list.sort(key=lambda x: x['pair'])

            print(f"Rates from cache (updated at {timestamp}):")
            for x in display_list:
                rate_fmt = f"{x['rate']:,.2f}" if x['rate'] >= 1 else f"{x['rate']:.6f}"
                print(f"- {x['pair']}: {rate_fmt}")
            if not self.rate_manager.is_rates_data_fresh():
                print("Предупреждение: данные могут быть устаревшими. Выполните 'update-rates'.")
        except Exception as e:
            print(f"Ошибка при получении курсов: {e}")
        self.wait_for_enter()

    def _display_rates_table(self, rates, base_currency, timestamp):
        """Отображение таблицы с курсами (Валюта, Курс, Обновлено, Источник)."""
        from datetime import datetime

        from prettytable import PrettyTable
        if not rates:
            print('Нет данных для отображения.')
            return
        table = PrettyTable()
        table.field_names = ['Валюта', f'Курс ({base_currency})', 'Обновлено', 'Источник']
        table.align['Валюта'] = 'l'
        table.align[f'Курс ({base_currency})'] = 'r'
        for rate_info in rates:
            currency = rate_info.get('currency', '')
            rate = rate_info.get('rate', 0)
            row_ts = rate_info.get('updated_at') or timestamp
            source = rate_info.get('source', '') or '—'
            formatted_rate = f'{rate:,.2f}' if rate >= 1 else f'{rate:.6f}'
            update_time = '—'
            if row_ts:
                try:
                    update_dt = datetime.fromisoformat(str(row_ts).replace('Z', '+00:00'))
                    update_time = update_dt.strftime('%H:%M:%S')
                except (ValueError, AttributeError):
                    update_time = str(row_ts)[:19] if row_ts else '—'
            table.add_row([currency, formatted_rate, update_time, source])
        print('\n' + '-' * 50)
        print('КУРСЫ ВАЛЮТ')
        print('-' * 50)
        print(table)
        print(f'\nВсего: {len(rates)}')
    
    def show_currency_info(self):
        '''
        Показать информацию о валютах с проверкой актуальности
        '''
        self.clear_screen()
        self.print_header('Процедура: Информация о валютах')
        
        try:
            
            currencies = self.currency_registry.get_all_currencies()
            
            print('Информация о валютах:')
            print('-' * 80)
            
            for code, currency in currencies.items():
                print(currency.get_display_info())
                print('-' * 80)
                
        except Exception as e:
            print(f'\n Ошибка: Произошла ошибка: {e}')
        
        self.wait_for_enter()
    
    def exit_app(self):
        '''
        Выход из приложения
        '''
        print('\nВыход из программы ValutaTrade Hub!')
        sys.exit(0)


    def get_command(self, user_input):
        '''
        Определяет команду по вводу пользователя
        '''
        if not user_input:
            return None
            
        user_input = user_input.strip().lower()
        
        if user_input in self.digit_mapping:
            return self.digit_mapping[user_input]
        
        if user_input in self.menu_options:
            return user_input
        
        matches = [cmd for cmd in self.menu_options.keys() 
                   if cmd.startswith(user_input) and len(user_input) >= 2]
        
        if len(matches) == 1:
            return matches[0]
        
        return None
    
    def run(self):
        '''
        Запуск интерактивного интерфейса
        '''
        while True:
            try:
                self.show_main_menu()
                
                choice = input('Список доступных команд (введите текстовую команду или число 1-12): ').strip()
                
                command = self.get_command(choice)
                
                if command:
                    _, handler = self.menu_options[command]
                    handler()
                else:
                    print(f'\n Ошибка: Неверный выбор: "{choice}"! Пожалуйста, выберите от 1 до 12 или используйте команды из меню.')
                    self.wait_for_enter()
            
            except KeyboardInterrupt:
                print('\n\nОшибка: Прервано пользователем.')
                self.exit_app()
            except Exception as e:
                print(f'\nОшибка: Неожиданная ошибка: {e}')
                self.wait_for_enter()
                
                
