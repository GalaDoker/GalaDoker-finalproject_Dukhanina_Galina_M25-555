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
from typing import Any, Dict


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

    def _load_pyproject(self):
        '''Чтение секции [tool.valutatrade] из pyproject.toml при наличии.'''
        try:
            import tomllib
        except ImportError:
            return
        if not os.path.exists('pyproject.toml'):
            return
        try:
            with open('pyproject.toml', 'rb') as f:
                data = tomllib.load(f)
            tool = data.get('tool', {}).get('valutatrade')
            if isinstance(tool, dict):
                for key, value in tool.items():
                    if key == 'rates_ttl_seconds' and isinstance(value, int):
                        self._settings['rates_ttl_seconds'] = value
                    elif key == 'currency_info_ttl_seconds' and isinstance(value, int):
                        self._settings['currency_info_ttl_seconds'] = value
                    elif key in ('data_directory', 'default_base_currency', 'log_level', 'log_file'):
                        self._settings[key] = value
        except Exception:
            pass

    def _load_env(self):
        '''Переменные окружения переопределяют значения.'''
        env_mapping = {
            'VALUTATRADE_DATA_DIR': 'data_directory',
            'VALUTATRADE_RATES_TTL': 'rates_ttl_seconds',
            'VALUTATRADE_LOG_LEVEL': 'log_level',
        }
        for env_var, setting_key in env_mapping.items():
            value = os.getenv(env_var)
            if value:
                if setting_key == 'rates_ttl_seconds':
                    try:
                        self._settings[setting_key] = int(value)
                    except ValueError:
                        pass
                else:
                    self._settings[setting_key] = value
    
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
