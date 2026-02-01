# valutatrade_hub/infra/settings.py
"""
Singleton: единая точка конфигурации приложения.

Ключи конфигурации (минимум):
- data_directory: путь к каталогу с JSON (users.json, portfolios.json, rates.json).
- rates_ttl_seconds: политика свежести курсов (секунды), например 300.
- currency_info_ttl_seconds: TTL данных о валютах (секунды).
- default_base_currency: базовая валюта по умолчанию (USD).
- log_file: путь к файлу логов; log_level: уровень (INFO, DEBUG и т.д.).
- supported_currencies: список кодов валют; api_timeout: таймаут API (секунды).

Публичные методы: get(key, default=None) -> Any; reload() — перезагрузка конфигурации.
"""
import os
from typing import Any, Callable, Dict, Optional


def _to_int(value: Any) -> Optional[int]:
    """Преобразует значение в int. Возвращает None при ошибке."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _to_str(value: Any) -> Optional[str]:
    """Возвращает строку или None для пустых значений."""
    return str(value) if value else None


# Маппинг ключей pyproject → парсер значения
_PYPROJECT_KEYS: Dict[str, Callable[[Any], Optional[Any]]] = {
    'rates_ttl_seconds': _to_int,
    'currency_info_ttl_seconds': _to_int,
    'data_directory': _to_str,
    'default_base_currency': _to_str,
    'log_level': _to_str,
    'log_file': _to_str,
}

# Маппинг переменных окружения → ключи settings
_ENV_TO_SETTING: Dict[str, str] = {
    'VALUTATRADE_DATA_DIR': 'data_directory',
    'VALUTATRADE_RATES_TTL': 'rates_ttl_seconds',
    'VALUTATRADE_LOG_LEVEL': 'log_level',
}


def _parse_env_value(setting_key: str, value: str) -> Any:
    """Преобразует значение из окружения в нужный тип для ключа."""
    if setting_key == 'rates_ttl_seconds':
        try:
            return int(value)
        except ValueError:
            return None
    return value


def _read_pyproject_section() -> Optional[Dict[str, Any]]:
    """Читает секцию [tool.valutatrade] из pyproject.toml. Возвращает None при ошибке."""
    try:
        import tomllib
    except ImportError:
        return None
    if not os.path.exists('pyproject.toml'):
        return None
    try:
        with open('pyproject.toml', 'rb') as f:
            data = tomllib.load(f)
        tool = data.get('tool', {}).get('valutatrade')
        return tool if isinstance(tool, dict) else None
    except Exception:
        return None


class SettingsLoader:
    '''
    Singleton: загрузка и кеширование конфигурации (pyproject.toml [tool.valutatrade], env, дефолты).
    Гарантия: в приложении ровно один экземпляр.
    Реализация через __new__: простота и читабельность, одна точка инициализации в _load_settings;
    при любом вызове SettingsLoader() возвращается один и тот же _instance — дополнительные экземпляры не создаются.
    '''
    _instance = None
    _settings: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsLoader, cls).__new__(cls)
            cls._instance._load_settings()
        return cls._instance

    def _load_settings(self):
        '''Загрузка настроек: дефолты → pyproject.toml [tool.valutatrade] → env.'''
        default_settings = {
            'data_directory': 'data',
            'rates_ttl_seconds': 300,
            'currency_info_ttl_seconds': 3600,
            'default_base_currency': 'USD',
            'log_level': 'INFO',
            'log_file': 'logs/valutatrade.log',
            'supported_currencies': ['USD', 'EUR', 'GBP', 'RUB', 'BTC', 'ETH', 'SOL'],
            'api_timeout': 10,
        }
        self._settings.update(default_settings)
        self._load_pyproject()
        self._load_env()

    def _load_pyproject(self) -> None:
        """Чтение секции [tool.valutatrade] из pyproject.toml при наличии."""
        tool = _read_pyproject_section()
        if not tool:
            return
        for key, parser in _PYPROJECT_KEYS.items():
            if key not in tool:
                continue
            parsed = parser(tool[key])
            if parsed is not None:
                self._settings[key] = parsed

    def _load_env(self) -> None:
        """Переменные окружения переопределяют значения."""
        for env_var, setting_key in _ENV_TO_SETTING.items():
            value = os.getenv(env_var)
            if value:
                parsed = _parse_env_value(setting_key, value)
                if parsed is not None:
                    self._settings[setting_key] = parsed
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Возвращает значение настройки по ключу.

        Args:
            key: Ключ (data_directory, rates_ttl_seconds, log_level и т.д.).
            default: Значение по умолчанию, если ключ отсутствует.

        Returns:
            Значение настройки или default.
        """
        return self._settings.get(key, default)

    def reload(self) -> None:
        """Перезагружает конфигурацию: очищает кеш и повторно загружает из pyproject.toml и окружения."""
        self._settings.clear()
        self._load_settings()

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __setitem__(self, key: str, value: Any):
        self._settings[key] = value


# Глобальный экземпляр — единственная точка доступа; при импортах создаётся один раз.
settings = SettingsLoader()
