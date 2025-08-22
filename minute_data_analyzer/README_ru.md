# EURUSD 1m — Project Guide (FLAT)

**Package generated:** 20250815_145705Z (UTC)

## Runbook (Pipeline)
# Runbook (CLEAN) — EURUSD 1m, годовой конвейер (UTC+0)

**Обновлено:** 2025-08-15 14:20:12 UTC  
**Изменение:** Полностью удалён слой/раздел «Важные мировые события». Каскад теперь: 📆→🎉→⚙️→📢→❗.

## 1. Входы
- HistData: `EURUSD_1m_{YEAR}.csv` (+ опц. `EURUSD_1m_{YEAR}.txt`)
- 2025: помесячные CSV (на выходе всё равно кварталы + отдельный июль)
- Локальный экономический календарь: `calendar_{YEAR}.csv` (UTC, precision=hour; all_day=true допустимо)
- Формат данных: `datetime_utc, open, high, low, close, volume` (volume не используется)

## 2. Валидация
- Чистый UTC+0; сортировка по времени; отсутствие дублей
- Δt между строками; ожидание weekend-гэпов; отсутствие «заливки» пропусков
- OHLC sanity: `0<low≤high`, `open/close∈[low,high]`, без NaN/Inf
- US-праздники: строки на официальные праздники не должны присутствовать
- Стыки источников (год/квартал/месяц): без перекрытий/дыр
- Спец-правила: 2025 (июльский CSV на выход), високосные годы, границы года
- Результат: **autofix: yes/no**

## 3. Поиск гэпов
- Гэп = `Δt > 60s`
- Для каждого гэпа: `start_ts, end_ts, gap_len`

## 4. Классификация (каскад)
**📆 Выходные → 🎉 Праздники США → ⚙️ Тех. перерывы CME/EBS → 📢 Новости (календарь CSV) → ❗ Аномалии**  
- ⚙️ Тех. окна: описываются в локальной TZ площадки; перевод в UTC с учётом DST; правило совпадения: overlap ≥50% или центр-внутри; повторяемость ≥8 недель
- 📢 Новости: precision=hour ⇒ окна ±15 мин; all_day ⇒ UTC-день

## 5. Экстра-проверки (только флаги, данные не меняем)
- DST-эффект на weekend-gap (±≈60 мин около дат переходов)
- Ролловер 5pm New York как тех.профиль
- Детектор «заливки/ресемплинга» (избыточные минуты/неделю)
- Data-glitch: свечи > K×медианный range (K=30)

## 6. Автофикс (только при fail валидации)
- Генерируем **квартальные CSV**: `EURUSD_1m_{YEAR}_Q1.csv.gz` … `Q4.csv.gz` (UTC+0, без выходных/праздников, с сохранёнными гэпами)
- 2025: также отдельный **месячный CSV за июль**
- gzip с фиксированным mtime=0 (детерминистичные SHA-256)

## 7. Отчёты и артефакты
- `reports/annual_report_{YEAR}.md` — 10 разделов (без «мировых событий»)
- `reports/gaps_summary_{YEAR}.md`
- `reports/EURUSD_{YEAR}_anomalies.svg` — только ❗ аномалии
- (2025) `quarterly_report_2025_Q*.md`, `monthly_summary_2025-07.md`

## 8. Манифест и воспроизводимость
- `manifests/artifacts_{YEAR}.sha256` — SHA-256 **всех входов и выходов**, включая `calendar_{YEAR}.csv`
- В конце отчётов печатаем хэш манифеста и заметку про идемпотентность (повторный запуск без изменения входов ⇒ те же SHA-256)




**Детерминированная метка анализа:** вместо реального времени запуска в отчёты подставляется `analysis_utc_ts = max(datetime_utc) из входных CSV`. Это делает хэши отчётов воспроизводимыми при неизменных входах.


---

## Validation Criteria
# Validation Criteria (CLEAN) — EURUSD 1m

**Обновлено:** 2025-08-15 14:20:12 UTC  
**Изменение:** Удалены любые проверки/разделы, связанные с «важными мировыми событиями».

## A. Формат и тайминг
- CSV UTF-8, запятая, корректный заголовок, без BOM
- Колонки: `datetime_utc, open, high, low, close, volume` (volume не используется)
- UTC+0; сортировка; отсутствие дублей; корректная дискретность (1 мин)
- Δt-дистрибуция: видимые weekend-гэпы; отсутствие «заливки» пропусков

## B. OHLC sanity
- `0<low≤high`; `open/close∈[low,high]`; без NaN/Inf
- Доп. флаги (не fail): high==low при активном рынке вокруг; серии open==high==low==close

## C. Классификация гэпов (без «мировых событий»)
- Порог гэпа: `Δt > 60s`
- Каскад: 📆 Выходные → 🎉 US-праздники → ⚙️ CME/EBS (TZ→UTC, DST, паттерны ≥8 недель) → 📢 Экономкалендарь (precision=hour ±15м; all_day — UTC-день) → ❗ Аномалии

## D. Спец-правила
- DST-эффект (±≈60 мин на weekend-gap) — не аномалия
- Ролловер 5pm NY — тех.профиль
- Високосные годы; границы 31-Dec/01-Jan; 29-Feb

## E. Autofix
- Квартальные `.csv.gz` только при fail; 2025 — плюс июльский месячный
- Дет. gzip (mtime=0)

## F. Отчёты
- Годовой: 10 разделов (без «мировых событий»), SVG с ❗
- Квартальные/месячные — без упоминаний «мировых событий»

## G. Манифест
- SHA-256 всех **входов и выходов** за год, включая `calendar_{YEAR}.csv`; проверка `sha256sum -c`




**Детерминированная метка анализа:** вместо реального времени запуска в отчёты подставляется `analysis_utc_ts = max(datetime_utc) из входных CSV`. Это делает хэши отчётов воспроизводимыми при неизменных входах.


---

## Notes
- Flat layout: all files in one directory.
- Determinism: use `helpers.py` for gzip/SVG and content-based `analysis_utc_ts`.


## Strict slicing по периоду `[start, end)`
Для исключения «протечки» минут между периодами используем строгую семантику интервала **[start, end)**:
- Данные фильтруются по кварталу или месяцу строго внутри окна.
- Гэпы считаются **только** между соседними строками **внутри** окна (первую и последнюю минуту периода с внешними рядами не сравниваем).
- Классификация событий (выходные/праздники/техокна/календарь) применяется, только если опорное время/центр события попадает в окно; интервалы — клипуeм краями окна.
- Для специальных правил 2025-07 используем `month_bounds(2025, 7)` параллельно с `quarter_bounds(2025, 3)` (доп. месячный CSV).

В `helpers.py` есть вспомогательные функции:
```python
from helpers import quarter_bounds, month_bounds

start, end = quarter_bounds(YEAR, Q)        # [start, end)
mstart, mend = month_bounds(2025, 7)        # [2025-07-01, 2025-08-01)
```


### Vector outputs (SVG) for bit-for-bit reproducibility
Charts/plots are saved as **SVG** using deterministic settings (fixed `svg.hashsalt`, `svg.fonttype='none'`, `path.simplify=False`, no tight bbox). If you need compressed vector files, use `.svgz` via deterministic gzip (`mtime=0`, empty filename). See helpers: `save_svg_deterministic`, `write_svgz_deterministic`.


## Patched rendering flow (strict)

1) Compute `df` and `gaps`.
2) Build context via `sections.py`:
   - `build_common_blocks(df, gaps, year)`
   - `build_gaps_context(df, gaps, year)`
   - `build_monthly_context(df, gaps, year, "YYYY-MM")`
   - `build_quarterly_context(df, gaps, year, Q)`
3) Render with `helpers.render_template_file_strict(...)`.
4) Pack heavy artifacts with `helpers.make_tar_gz_deterministic(...)` for bit-for-bit reproducibility.

Templates now contain explicit placeholders like `{{durations_section_md}}`, `{{sessions_table_md}}` etc. Any unresolved `{{...}}` will raise.


## Scoring model (0–100)
- Конфигурируется через `project_config.yml` → секция `scoring:` (weights/targets).
- Подсчёт идёт в `sections.py: compute_score(...)` и автоматически попадает в годовой отчёт:
  - **Score (0–100)** в разделе *Final assessment*
  - полный **Scorecard** (таблица) в отдельной секции отчёта.
- Все вычисления детерминированы, не требуют внешних данных.
