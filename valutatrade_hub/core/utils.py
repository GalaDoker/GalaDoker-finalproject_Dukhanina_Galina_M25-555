# valutatrade_hub/core/utils.py
"""
Утилиты для валидации валютных кодов и конвертации сумм.
"""
from typing import Optional


def validate_currency_code(code: str) -> str:
    """
    Валидирует код валюты.
    
    Требования: 2–5 латинских букв, без пробелов. Регистр нормализуется в верхний.
    
    Args:
        code: Сырой код валюты (например, 'usd', 'BTC').
        
    Returns:
        Нормализованный код в верхнем регистре.
        
    Raises:
        ValueError: Если код пустой, не соответствует формату или содержит недопустимые символы.
    """
    if code is None:
        raise ValueError('Ошибка: Код валюты не может быть None')
    
    raw = (code or '').strip()
    if not raw:
        raise ValueError('Ошибка: Код валюты не может быть пустым')
    
    normalized = raw.upper()
    
    if len(normalized) < 2 or len(normalized) > 5:
        raise ValueError('Ошибка: Код валюты должен быть от 2 до 5 символов')
    
    if not normalized.isalpha():
        raise ValueError('Ошибка: Код валюты должен содержать только латинские буквы')
    
    if ' ' in normalized:
        raise ValueError('Ошибка: Код валюты не должен содержать пробелы')
    
    return normalized


def convert_amount(
    amount: float,
    rate: float,
    *,
    round_digits: Optional[int] = 8,
) -> float:
    """
    Конвертирует сумму по заданному курсу.
    
    Курс rate интерпретируется как: 1 единица исходной валюты = rate единиц целевой.
    Итог: amount * rate.
    
    Args:
        amount: Сумма в исходной валюте.
        rate: Курс обмена (из валюты A в валюту B).
        round_digits: Количество знаков после запятой для округления (None — без округления).
        
    Returns:
        Сумма в целевой валюте.
        
    Raises:
        ValueError: Если amount или rate отрицательные.
    """
    if amount < 0:
        raise ValueError('Ошибка: Сумма не может быть отрицательной')
    if rate < 0:
        raise ValueError('Ошибка: Курс не может быть отрицательным')
    
    result = amount * rate
    
    if round_digits is not None:
        result = round(result, round_digits)
    
    return result


def normalize_currency_code(code: str) -> str:
    """
    Нормализует код валюты (приводит к верхнему регистру, убирает пробелы).
    Не выполняет полную валидацию — используйте validate_currency_code при вводе от пользователя.
    
    Args:
        code: Сырой код валюты.
        
    Returns:
        Код в верхнем регистре без лишних пробелов.
    """
    if code is None:
        return ''
    return (code or '').strip().upper()
