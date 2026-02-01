# Valutatrade Hub

## Идея проекта

Консольное приложение для торговли валютой: регистрация и вход пользователей, просмотр портфеля, покупка/продажа валют по актуальным курсам. Курсы загружаются через Parser Service (ExchangeRate-API для фиата, CoinGecko для криптовалют) и кэшируются с настраиваемым TTL.

---

## Структура каталогов

```
finalproject_Dukhanina_Galina_M25-555/
├── data/                    # JSON: users.json, portfolios.json, rates.json, exchange_rates.json
├── valutatrade_hub/
│   ├── cli/                 # Интерфейс: interface.py
│   ├── core/                 # Модели, use cases, валюта, исключения
│   ├── infra/                # База данных, настройки (SettingsLoader)
│   ├── parser_service/       # API-клиенты, конфиг, планировщик, хранилище курсов
│   ├── decorators.py
│   └── logging_config.py
├── main.py
├── Makefile
├── pyproject.toml
└── poetry.lock
```

---

## Установка и запуск

- **Установка зависимостей:** `make install`  
  (или `poetry install`)

- **Запуск приложения:** `make project`  
  (или `poetry run project`)

Дополнительные цели Makefile: `make build`, `make publish`, `make package-install`, `make lint` (ruff).

---

## Команды CLI (инструкция по работе)

| Команда      | Описание |
|-------------|----------|
| **register** | Регистрация пользователя (стартовый счёт: 10 000 USD) |
| **login**    | Вход в аккаунт |
| **portfolio** | Просмотр финансового портфеля |
| **buy**     | Покупка валюты |
| **sell**    | Продажа валюты |
| **get-rate** | Просмотр списка курсов валют |
| **show-rates** | Просмотр курсов с фильтрацией |
| **update**  | Обновление списка курсов (update-rates) |
| **parser**  | Состояние парсера |
| **autoupdate** | Запуск автоматического обновления парсера |
| **stop**    | Остановка автоматического обновления |
| **exit**    | Выход из приложения |

**Пример полного цикла:** `register` → `login` → `get-rate` / `show-rates` → `buy` / `sell` → `portfolio` → `update` при необходимости → `exit`.

---

## Кэш и TTL

- **Курсы валют** кэшируются в `data/rates.json` (и при необходимости в `data/exchange_rates.json`).
- **TTL курсов** (`rates_ttl_seconds`): по умолчанию **300** секунд. Пока данные «свежие», используются из кэша; при истечении TTL приложение может запрашивать обновление (например, через команду **update** или фоновый парсер).
- **TTL данных о валютах** (`currency_info_ttl_seconds`): по умолчанию **3600** секунд.
- Настройки задаются в `pyproject.toml` в секции `[tool.valutatrade]` или через переменные окружения, например `VALUTATRADE_RATES_TTL` (секунды).

---

## Parser Service: включение и хранение API-ключа

Parser Service подтягивает курсы с внешних API (ExchangeRate-API, CoinGecko). Для работы с фиатными валютами нужен API-ключ ExchangeRate-API.

**Как включить и где хранить ключ:**

1. Зарегистрируйтесь на [ExchangeRate-API](https://app.exchangerate-api.com/sign-up) и получите ключ.
2. Задайте ключ одним из способов:
   - **Переменная окружения:** `EXCHANGERATE_API_KEY=ваш_ключ`
   - **Локальный файл в корне проекта** (файлы не отслеживаются git):
     - `.env.parser` или `parser_secrets.env`
     - Содержимое одной строкой: `EXCHANGERATE_API_KEY=ваш_ключ`

Ключ **не** храните в коде и **не** коммитьте файлы с секретами. Команды **parser**, **update**, **autoupdate** используют эту конфигурацию.

---

## Демонстрация (asciinema)

Демонстрация функционала: полный цикл (register → login → buy/sell → show-portfolio → get-rate), **update-rates**, **show-rates**, обработка ошибок (недостаточно средств, неизвестная валюта).

[![asciicast](https://asciinema.org/a/csyOcp3wSUsoBvW0.svg)](https://asciinema.org/a/csyOcp3wSUsoBvW0)
