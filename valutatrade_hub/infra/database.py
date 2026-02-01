# valutatrade_hub/infra/database.py
import json
import os
from threading import Lock
from typing import Any

from .settings import settings


class DatabaseManager:
    '''
    Singleton: единая точка доступа к JSON-данным (users, portfolios, rates).
    Реализация через __new__: один экземпляр, инициализация в _init_db при первом создании.
    '''
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._init_db()
        return cls._instance
    
    def _init_db(self):
        '''
        Инициализация базы данных
        '''
        self.data_dir = settings.get('data_directory', 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        self._ensure_file_exists('users.json', [])
        self._ensure_file_exists('portfolios.json', [])
        self._ensure_file_exists('rates.json', {'pairs': {}, 'last_refresh': None})
        self._ensure_file_exists('exchange_rates.json', [])
    
    def _ensure_file_exists(self, filename: str, default_data: Any):
        '''
        Создание файла с данными по умолчанию если он не существует
        '''
        filepath = os.path.join(self.data_dir, filename)
        if not os.path.exists(filepath):
            self._write_file(filepath, default_data)
    
    def _read_file(self, filepath: str) -> Any:
        '''
        Чтение JSON файла
        '''
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return None
    
    def _write_file(self, filepath: str, data: Any):
        '''
        Запись в JSON файл
        '''
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            raise IOError(f'Ошибка: Ошибка записи в файл {filepath}: {e}')
    
    def load_data(self, entity: str) -> Any:
        '''
        Загрузка данных по имени сущности
        '''

        filepath = os.path.join(self.data_dir, f'{entity}.json')
        result = self._read_file(filepath)
        return result
    
    def save_data(self, entity: str, data: Any):
        '''
        Сохранение данных по имени сущности
        '''

        filepath = os.path.join(self.data_dir, f'{entity}.json')
        self._write_file(filepath, data)
        
    def update_data(self, entity: str, update_fn: callable) -> Any:
        '''
        Атомарное обновление данных
        '''       
        with self._lock:            
            try:
                data = self.load_data(entity)
                updated_data = update_fn(data)
                self.save_data(entity, updated_data)
                return updated_data                
            except Exception:
                import traceback
                traceback.print_exc()
                raise

# Глобальный экземпляр — единственная точка доступа к хранилищу; при импортах создаётся один раз.
db = DatabaseManager()
