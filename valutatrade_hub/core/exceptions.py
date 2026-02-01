# valutatrade_hub/core/exceptions.py


# Классы для обработки исключений
class ValutaTradeError(Exception):
    '''
    Базовое исключение для приложения
    '''
    pass


class InsufficientFundsError(ValutaTradeError):
    '''
    Недостаточно средств (Wallet.withdraw, usecases buy/sell).
    Сообщение: "Недостаточно средств: доступно {available} {code}, требуется {required} {code}"
    '''
    def __init__(self, available: float, required: float, code: str):
        self.available = available
        self.required = required
        self.code = code
        super().__init__(f'Недостаточно средств: доступно {available} {code}, требуется {required} {code}')


class CurrencyNotFoundError(ValutaTradeError):
    '''
    Неизвестная валюта (currencies.get_currency, get-rate валидация).
    Сообщение: "Неизвестная валюта '{code}'"
    '''
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Неизвестная валюта '{code}'")


class ApiRequestError(ValutaTradeError):
    '''
    Сбой внешнего API (слой получения курсов: заглушка/Parser Service).
    Сообщение: "Ошибка при обращении к внешнему API: {reason}"
    '''
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f'Ошибка при обращении к внешнему API: {reason}')


class UserNotFoundError(ValutaTradeError):
    '''
    Обрабатывает вход пользователя, если не найден возвращает ошибку
    '''
    def __init__(self, username: str):
        super().__init__(f"Пользователь '{username}' не найден")


class AuthenticationError(ValutaTradeError):
    '''
    Обрабатывает вход пользователя — неверный пароль
    '''
    def __init__(self):
        super().__init__('Неверный пароль')


class UsernameTakenError(ValutaTradeError):
    '''
    Обрабатывает регистрацию (если пользователь с таким именем уже существует - вернет ошибку)
    '''
    def __init__(self, username: str):
        super().__init__(f"Имя пользователя '{username}' уже занято")


class UsernamePasswordError(ValutaTradeError):
    '''
    Ошибка: пароль слишком короткий (длина < 4).
    '''
    def __init__(self):
        super().__init__('Пароль должен быть не короче 4 символов')
        
        
