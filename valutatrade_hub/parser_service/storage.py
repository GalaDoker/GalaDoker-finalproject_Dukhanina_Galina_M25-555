# valutatrade_hub/parser_service/storage.py
"""
Журнал измерений exchange_rates.json: одна запись = одна пара валют.
id = FROM_TO_ISO-UTC (уникальный идентификатор), запись атомарно (temp file → rename).
"""
import json
import os
from datetime import datetime
from typing import Any, Dict, List


def make_rate_id(from_currency: str, to_currency: str, timestamp_utc: datetime) -> str:
    """
    id = FROM_TO_<ISO-UTC timestamp>.
    Коды валют — верхний регистр, 2–5 символов.
    """
    from_c = (from_currency or "").upper()[:5]
    to_c = (to_currency or "").upper()[:5]
    ts = timestamp_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"{from_c}_{to_c}_{ts}"


def build_exchange_rate_record(
    from_currency: str,
    to_currency: str,
    rate: float,
    timestamp_utc: datetime,
    source: str,
    meta: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Одна запись для журнала: пара, курс, время (UTC), источник, meta.
    Коды валют нормализуются в верхний регистр (2–5 символов).
    """
    from_c = (from_currency or "").upper()[:5]
    to_c = (to_currency or "").upper()[:5]
    ts_str = timestamp_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    record_id = f"{from_c}_{to_c}_{ts_str}"
    return {
        "id": record_id,
        "from_currency": from_c,
        "to_currency": to_c,
        "rate": float(rate),
        "timestamp": ts_str,
        "source": source,
        "meta": dict(meta) if meta else {},
    }


class ParserStorage:
    """
    Работа с хранилищем парсера: журнал exchange_rates.json (одна запись — одна пара),
    атомарная запись (временный файл → rename).
    """

    def append_exchange_rate_records(self, records: List[Dict[str, Any]], file_path: str) -> None:
        """
        Добавляет записи в журнал без дубликатов по id.
        Запись выполняется атомарно: запись во временный файл → os.replace.
        """
        if not records:
            return
        path_abs = os.path.abspath(file_path)
        dir_path = os.path.dirname(path_abs)
        os.makedirs(dir_path, exist_ok=True)

        try:
            with open(path_abs, "r", encoding="utf-8") as f:
                try:
                    current = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    current = []
        except FileNotFoundError:
            current = []

        if not isinstance(current, list):
            current = [current] if current else []

        existing_ids = {r.get("id") for r in current if r.get("id")}
        new_records = [r for r in records if r.get("id") and r["id"] not in existing_ids]
        if not new_records:
            return

        result = current + new_records
        temp_path = path_abs + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        os.replace(temp_path, path_abs)

    def get_historical_rates(self, currency_pair: str, limit: int = 100) -> List[Dict]:
        """Исторические записи по паре валют (from_currency или to_currency)."""
        from ..infra.database import db

        history = db.load_data("exchange_rates") or []
        if not isinstance(history, list):
            history = [history] if history else []
        pair_upper = (currency_pair or "").upper()
        filtered = [
            r
            for r in history
            if (r.get("from_currency") or "").upper() == pair_upper
            or (r.get("to_currency") or "").upper() == pair_upper
        ]
        return filtered[-limit:]
