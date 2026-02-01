# valutatrade_hub/parser_service/updater.py
"""
Координация процесса обновления: получение данных от всех клиентов, объединение и сохранение.
RatesUpdater — точка входа для логики парсинга; принимает экземпляры API-клиентов и хранилища.
Итоговый JSON в формате Core Service: data/rates.json (pairs + last_refresh).
"""
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from valutatrade_hub.core.exceptions import ApiRequestError

from ..logging_config import get_logger
from .storage import ParserStorage, build_exchange_rate_record

SOURCE_DISPLAY_NAMES = {"coingecko": "CoinGecko", "exchangerate": "ExchangeRate-API"}


def _validate_pair_and_rate(pair_key: str, rate: Any) -> bool:
    """Коды валют — верхний регистр, 2–5 символов; rate — число. Пишем только после валидации."""
    if "_" not in pair_key or pair_key.count("_") != 1:
        return False
    from_c, to_c = pair_key.split("_", 1)
    if not (2 <= len(from_c) <= 5 and from_c.isalpha() and from_c.isupper()):
        return False
    if not (2 <= len(to_c) <= 5 and to_c.isalpha() and to_c.isupper()):
        return False
    try:
        float(rate)
    except (TypeError, ValueError):
        return False
    return True


class RatesUpdater:
    """
    Точка входа для логики парсинга: координирует получение данных от клиентов,
    объединение и сохранение. В конструкторе принимает экземпляры API-клиентов и хранилища
    (если не переданы — создаются из config). Итоговый JSON в формате Core Service: data/rates.json.
    """
    
    def __init__(self, config=None, clients=None, storage=None):
        from .api_clients import CoinGeckoClient, ExchangeRateApiClient
        from .config import ParserConfig
        
        self.config = config or ParserConfig.from_env()
        self.config.validate()
        self.logger = get_logger("parser_service")
        self.storage = storage if storage is not None else ParserStorage()
        if clients is not None:
            self.clients = clients
        else:
            self.clients = {
                "coingecko": CoinGeckoClient(self.config),
                "exchangerate": ExchangeRateApiClient(self.config),
            }
    
    def run_update(self, source: str = None) -> Tuple[Dict[str, float], List[str]]:
        """
        1. Вызывает fetch_rates() у каждого клиента.
        2. Объединяет полученные словари с курсами в один.
        3. Добавляет метаданные: source, last_refresh.
        4. Передаёт итоговый объект в storage для сохранения (exchange_rates + rates.json).
        5. Подробное логирование: старт, успех/неудача по каждому клиенту, завершение.
        Возвращает (all_rates, failed_sources) для интеграции с CLI.
        """
        self.logger.info("run_update: старт обновления курсов")
        all_rates: Dict[str, float] = {}
        pair_sources: Dict[str, str] = {}
        failed_sources: List[str] = []
        sources_to_update = [source] if source else list(self.clients.keys())
        
        for source_name in sources_to_update:
            if source_name not in self.clients:
                self.logger.warning("run_update: неизвестный источник %s, пропуск", source_name)
                continue
            try:
                self.logger.info("run_update: опрос клиента %s", source_name)
                t0 = time.perf_counter()
                rates = self.clients[source_name].fetch_rates()
                request_ms = int((time.perf_counter() - t0) * 1000)
                
                if not rates:
                    self.logger.warning("run_update: клиент %s вернул пустой результат", source_name)
                    continue
                
                display_name = SOURCE_DISPLAY_NAMES.get(source_name, source_name)
                timestamp_utc = datetime.now(timezone.utc)
                records: List[Dict[str, Any]] = []
                
                for pair_key, rate in rates.items():
                    if not _validate_pair_and_rate(pair_key, rate):
                        self.logger.warning("run_update: пропуск пары/курса %r = %r", pair_key, rate)
                        continue
                    from_c, to_c = pair_key.split("_", 1)
                    from_c, to_c = from_c.upper(), to_c.upper()
                    meta = {"request_ms": request_ms}
                    if source_name == "coingecko" and getattr(self.config, "CRYPTO_ID_MAP", None):
                        meta["raw_id"] = self.config.CRYPTO_ID_MAP.get(from_c, "")
                    record = build_exchange_rate_record(
                        from_c, to_c, float(rate), timestamp_utc, display_name, meta
                    )
                    records.append(record)
                
                if records:
                    self.storage.append_exchange_rate_records(records, self.config.HISTORY_FILE_PATH)
                    self.logger.info("run_update: успех %s — записей в журнал: %s", source_name, len(records))
                
                for pair_key in rates:
                    pair_sources[pair_key] = display_name
                all_rates.update(rates)
                self.logger.info("run_update: успех %s — курсов получено: %s", source_name, len(rates))
                
            except ApiRequestError as e:
                self.logger.error("run_update: ошибка API от %s — %s", source_name, e)
                failed_sources.append(source_name)
            except Exception as e:
                self.logger.error("run_update: неожиданная ошибка от %s — %s", source_name, e)
                failed_sources.append(source_name)
        
        if all_rates:
            self._save_rates_cache(all_rates, pair_sources)
            self.logger.info("run_update: завершение — всего курсов: %s, сохранено в data/rates.json", len(all_rates))
        else:
            self.logger.warning("run_update: завершение — ни один клиент не вернул курсов")
        return (all_rates, failed_sources)
    
    def _save_rates_cache(self, rates: Dict[str, float], pair_sources: Dict[str, str]):
        '''
        Снимок текущего мира: pairs = { pair: { rate, updated_at, source } }, last_refresh.
        Апдейт побеждает, если updated_at свежее текущего. Атомарная запись: temp file → rename.
        '''
        try:
            import json
            import os
            
            path_abs = os.path.abspath(self.config.RATES_FILE_PATH)
            dir_path = os.path.dirname(path_abs)
            os.makedirs(dir_path, exist_ok=True)
            
            # Читаем текущий кеш (или legacy format)
            try:
                with open(path_abs, 'r', encoding='utf-8') as f:
                    current = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                current = {}
            
            pairs = current.get('pairs')
            if pairs is None and current.get('rates') is not None:
                # Legacy: rates + timestamp
                legacy_ts = current.get('timestamp') or ''
                legacy_src = current.get('source', 'unknown')
                pairs = {
                    pair: {'rate': v, 'updated_at': legacy_ts, 'source': legacy_src}
                    for pair, v in current.get('rates', {}).items()
                }
            if pairs is None:
                pairs = {}
            
            now_ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            for pair_key, rate in rates.items():
                existing = pairs.get(pair_key, {})
                existing_ts = existing.get('updated_at') or ''
                if not existing_ts or now_ts >= existing_ts:
                    pairs[pair_key] = {
                        'rate': float(rate),
                        'updated_at': now_ts,
                        'source': pair_sources.get(pair_key, 'unknown'),
                    }
            
            data_to_save = {'pairs': pairs, 'last_refresh': now_ts}
            temp_path = path_abs + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, path_abs)
            self.logger.info(f'Данные сохранены в {self.config.RATES_FILE_PATH}')
            
        except Exception as e:
            self.logger.error(f'Error saving rates cache: {e}')
    
    def get_update_status(self) -> Dict[str, Any]:
        '''
        Получение статуса последнего обновления
        '''
        try:
            import json
            import os
            
            if os.path.exists(self.config.RATES_FILE_PATH):
                with open(self.config.RATES_FILE_PATH, 'r', encoding='utf-8') as f:
                    rates_data = json.load(f)
                pairs = rates_data.get('pairs', {})
                return {
                    'last_refresh': rates_data.get('last_refresh') or rates_data.get('timestamp'),
                    'total_pairs': len(pairs),
                    'source': ', '.join(set(v.get('source', '') for v in pairs.values())) or 'unknown'
                }
            else:
                return {
                    'last_refresh': None,
                    'total_pairs': 0,
                    'source': 'unknown'
                }
                
        except Exception as e:
            self.logger.error(f'Error getting status: {e}')
            return {
                'last_refresh': None,
                'total_pairs': 0,
                'source': 'error'
            }
            
            
