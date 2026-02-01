# valutatrade_hub/parser_service/scheduler.py
import threading
import time
from typing import Optional

from ..logging_config import get_logger
from .config import ParserConfig
from .updater import RatesUpdater


class Scheduler:
    '''
    Планировщик периодического обновления курсов
    '''
    
    def __init__(self, config: ParserConfig = None):
        self.config = config or ParserConfig.from_env()
        self.updater = RatesUpdater(config)
        self.logger = get_logger('scheduler')
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_running = False
    
    def start(self):
        '''
        Запуск планировщика в отдельном потоке
        '''
        if self._is_running:
            self.logger.warning('Scheduler is already running')
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._is_running = True
        self.logger.info('Scheduler started')
    
    def stop(self):
        '''
        Остановка планировщика
        '''
        if not self._is_running:
            return
            
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._is_running = False
        self.logger.info('Scheduler stopped')
    
    def _run_loop(self):
        '''
        Основной цикл планировщика
        '''
        while not self._stop_event.is_set():
            try:
                self.logger.debug('Running scheduled update...')
                self.updater.run_update()
                
                wait_time = self.config.UPDATE_INTERVAL_MINUTES * 60
                for _ in range(wait_time * 2):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f'Scheduler error: {e}')
                for _ in range(60):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.5)
    
    def run_once(self):
        '''
        Однократный запуск обновления
        '''
        return self.updater.run_update()
    
    @property
    def is_running(self) -> bool:
        '''
        Проверка запущен ли планировщик
        '''
        return self._is_running and self._thread and self._thread.is_alive()
