# Передача проекта на другой компьютер

Контекст для новой сессии Claude Code. Секретов здесь нет: токен и chat id лежат только в `.env`.

## Что это

Бот проверяет аренду квартир в Лимассоле (Bazaraki, RERA.cy, home.cy, index.cy) каждые 15 минут и шлёт подходящие в Telegram-бота **@limassol_rent_watcher_bot**. Настройки поиска в `config.yaml`, подробности в `README.md`.

## Пожелания пользователя (важно)

- **Всё общение по-русски**, включая вопросы, кнопки и итоги.
- **Только квартиры с фотовольтаикой** (`require_pv: true`). Пользователь был очень недоволен, когда первый запуск прислал 71 объявление без PV. Не присылать «всё подряд», не устраивать массовых рассылок без спроса.
- «Solar panels» без уточнения не считается: обычно это бойлер (`send_unclear_solar: false`).
- Остальные условия: 1–2 спальни, от 50 м², дом 2016+ (неизвестный год с пометкой), до €1 700 (цель €1 600 + торг), до 10 км от центра Лимассола.

## Получатели

`TELEGRAM_CHAT_ID` в `.env` содержит два id через запятую: первый — владелец (Даниил, @D1k3Y), второй — Юлия (@juliaaa_ku). Добавить ещё кого-то: `python -m watcher.add_user <ник>` (человек сначала жмёт Start у бота).

## Что выяснено

- **Bazaraki (Cloudflare) блокирует IP дата-центров**: с GitHub Actions он отдаёт 403. Обходить защиту не надо. Поэтому бот работает с домашнего IP. Workflow на GitHub выключен.
- home.cy после ~30 запросов подряд показывает «Verify you are not a robot», поэтому стоит лимит 12 детальных страниц за проверку.
- Spitogatos и BuySellCyprus не подключены: Imperva / Cloudflare challenge.
- На старом ПК Python требовал `truststore` из-за перехвата TLS (антивирус). В коде это уже учтено.

## Текущее состояние (на 23.10.2026)

- На старом ПК (Windows) бот работает через Планировщик задач: задача `LimassolRentWatcher`, `install_task.ps1`.
- **Не запускать бота на двух компьютерах одновременно**, иначе будут дубли. После переезда на старом ПК выполнить:
  `Unregister-ScheduledTask -TaskName LimassolRentWatcher -Confirm:$false`
- Начат переезд на бесплатный сервер **Oracle Cloud Free**: готов `deploy/setup_server.sh` (systemd-таймер раз в 15 мин). Пользователь должен был создать VM (Ubuntu 24.04, VM.Standard.E2.1.Micro) и прислать Public IP; это ещё не сделано. Первым делом на сервере проверить, отдаёт ли Bazaraki 200, а не 403. Если блокирует — предложить Raspberry Pi дома (у пользователя она есть).
- SSH-ключ для Oracle был создан на старом ПК (`~/.ssh/oracle_rent_watcher`). На новом компьютере проще создать новый ключ.

## Как поднять на новом компьютере (Windows)

```bash
git clone https://github.com/D1Keyy/limassol-rent-watcher.git
cd limassol-rent-watcher
pip install -r requirements.txt
```
Затем положить в папку проекта `.env` и `state/seen.json` из архива переноса (их нет на GitHub) и выполнить:
```bash
python -m watcher.main --dry-run
powershell -ExecutionPolicy Bypass -File install_task.ps1
```
`state/seen.json` нужен, чтобы бот не прислал повторно уже отправленное.
