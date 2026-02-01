# valutatrade_hub/decorators.py
"""
Декоратор @log_action — логирование доменных операций (BUY/SELL/REGISTER/LOGIN).

Поля логов: timestamp (ISO), action, username или user_id, currency_code, amount,
rate и base (если применимо), result (OK/ERROR), при ошибке — error_type, error_message.
Формат сообщения: одна строка, человекочитаемый, например:
  BUY user_id=1 currency='BTC' amount=0.0500 rate=59300.00 base='USD' result=OK
При verbose=True добавляется контекст: состояние кошелька «было→стало».
Исключения не глотаются — после записи в лог пробрасываются дальше.
"""
import functools
from datetime import datetime
from typing import Any, Callable

from .logging_config import get_logger


def log_action(user_action: str, verbose: bool = False):
    '''
    Декоратор для прозрачной трассировки ключевых операций (buy/sell/register/login).
    user_action: BUY | SELL | register | login.
    verbose: при True добавляет контекст (например, баланс кошелька было→стало).
    '''
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = get_logger('actions')
            ts = datetime.now().isoformat()

            user_info = 'unknown'
            if user_action in ('register', 'login') and len(args) >= 2 and isinstance(args[1], str):
                user_info = f"user='{args[1]}'"
            else:
                for arg in args:
                    if hasattr(arg, 'user_id'):
                        user_info = f"user_id={arg.user_id}"
                        break
                    if hasattr(arg, '_user_id'):
                        user_info = f"user_id={getattr(arg, '_user_id')}"
                        break
                    if isinstance(arg, int) and arg > 0:
                        user_info = f"user_id={arg}"
                        break

            currency_code = kwargs.get('currency_code', '')
            amount = kwargs.get('amount', 0)
            base_currency = kwargs.get('base_currency', '')

            try:
                result = func(*args, **kwargs)
                parts = [f"{user_action} {user_info}"]
                if currency_code:
                    parts.append(f"currency='{currency_code}'")
                if amount is not None and amount != '':
                    amount_fmt = f'{amount:.4f}' if isinstance(amount, float) else amount
                    parts.append(f"amount={amount_fmt}")
                if isinstance(result, dict):
                    rate = result.get('rate')
                    if rate is not None:
                        parts.append(f"rate={rate:.2f}" if isinstance(rate, (int, float)) else f"rate={rate}")
                    if base_currency:
                        parts.append(f"base='{base_currency}'")
                elif base_currency:
                    parts.append(f"base='{base_currency}'")
                parts.append("result=OK")
                if verbose and isinstance(result, dict):
                    curr = result.get('currency', '')
                    ob = result.get('old_balance')
                    nb = result.get('new_balance')
                    obase = result.get('base_currency_old_balance')
                    nbase = result.get('base_currency_new_balance')
                    if curr is not None and ob is not None and nb is not None:
                        parts.append(f"| wallet {curr} {ob}→{nb}")
                    if obase is not None and nbase is not None:
                        parts.append(f"base {obase}→{nbase}")
                msg = ' '.join(str(p) for p in parts)
                logger.info(msg, extra={'timestamp': ts})
                return result

            except Exception as e:
                parts = [f"{user_action} {user_info}"]
                if currency_code:
                    parts.append(f"currency='{currency_code}'")
                if amount is not None and amount != '':
                    parts.append(f"amount={amount}")
                if base_currency:
                    parts.append(f"base='{base_currency}'")
                parts.append("result=ERROR")
                parts.append(f"error_type={type(e).__name__}")
                parts.append(f"error_message={str(e)!r}")
                msg = ' '.join(str(p) for p in parts)
                logger.error(msg, extra={'timestamp': ts, 'error_type': type(e).__name__, 'error_message': str(e)})
                raise
        return wrapper
    return decorator
