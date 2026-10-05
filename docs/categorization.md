# Categorization

## Подход

Категории двухуровневые:

- категория;
- подкатегория.

Например:

- Еда -> Супермаркеты;
- Еда -> Рынок;
- Еда -> Кафе;
- Здоровье -> Аптеки;
- Здоровье -> Врачи;
- Транспорт -> Такси;
- Дом -> Бытовая химия;
- Подписки -> Сервисы.

## Стартовый набор категорий

Стартуем с компактного двухуровневого набора. В preview импорта можно быстро добавить новую подкатегорию.

Полный согласованный список категорий и подкатегорий хранится в [Category Taxonomy](category-taxonomy.md).

Ключевые принципы:

- собственная структура категорий важнее банковских категорий;
- банк-категория используется как подсказка;
- конкретные магазины и получатели анализируются через `Merchant`;
- split одной операции на несколько категорий не входит в MVP;
- теги для отпуска, события, ребенка/взрослых добавляются позже;
- операции без категории разрешены, но должны быть видны в отдельном блоке.

## Правила

Правила могут быть:

- keyword rule: ключевое слово в описании;
- merchant rule: конкретный продавец всегда ведет в категорию;
- manual correction rule: пользователь исправил категорию, и система предлагает сохранить это как правило.

## Маппинг банковских категорий

Банковская категория хранится как `bank_category_raw` и используется как подсказка. Уверенные категории маппятся автоматически, сомнительные идут на проверку.

Примеры уверенных маппингов:

- `Супермаркети та продукти` -> `Еда / Супермаркеты`;
- `Аптеки` -> `Здоровье / Аптеки`;
- `Комуналка та Інтернет` -> `Дом / Коммуналка` или `Дом / Интернет`;
- `Транспорт` -> `Транспорт / Общественный транспорт`;
- `АЗС` -> `Авто / Топливо`;
- `Зняття готівки` -> cash withdrawal, не обычный расход;
- `Заощадження` + `Скарбничка` -> `Накопления`.

Сомнительные категории:

- `Перекази`;
- `Переказ на свою картку`;
- `Зарахування зі своєї картки`;
- `Платежі за реквізитами`;
- `Інше`;
- потенциально рабочие сервисы.

## Правила по еде

- Обычные супермаркетные чеки автоматически относятся к `Еда / Супермаркеты`.
- Конкретные супермаркеты анализируются через merchant: Сільпо, Фора, Велмарт и другие.
- Крупные супермаркетные чеки отправляются на проверку. Лимит настраиваемый, значение по умолчанию: 2500 UAH.
- Доставка еды по умолчанию относится к `Еда / Доставка`, но merchant rules могут уточнять: доставка продуктов может остаться `Еда / Супермаркеты`.
- `Еда / Кофе и перекусы` определяется по продавцу и сумме как подсказке. Пользователь может исправить и сохранить правило.
- Рестораны/кафе в отпуске или на событиях в MVP отмечаются комментарием. Теги добавляются позже.

## Deterministic import-review engine

The backend applies active rules while building the persisted XLSX preview. Supported rule types are:

- `merchant`: exact match against the NFKC-normalized, whitespace-collapsed, case-folded merchant
  text. A `Merchant` row is not required before confirmation.
- `bank_category`: exact match against normalized bank-category text (`bank_category` is preferred;
  `pattern` is accepted for older rows).
- `keyword`: normalized `pattern` must occur in the description or merchant text.

System rules have `family_id = null`; user corrections are family-specific and are only loaded for
that Family. Higher numeric `priority` wins independently for each output field. The seeded
`Супермаркети та продукти` mapping has priority 100 and resolves through the seeded `Еда` /
`Супермаркеты` taxonomy rows. Saved exact-merchant corrections use priority 300. Keyword rules can
use priority 200. These are defaults, not reserved priority bands.

Rules may propose category, subcategory, flow type, and scope. A rule that omits a field does not
replace that field. If equally highest-priority matching rules disagree on a field, the engine
leaves that field unresolved and adds `rule_conflict`. Equal-priority rules with the same value do
not conflict. A lower-priority subcategory that belongs to a different, higher-priority category is
ignored; an equally or more authoritative incompatible subcategory produces `rule_conflict`.

The system bank-category rules are seeded idempotently by
`python -m app.db.seed_system_categories` after their Category/Subcategory rows exist. The initial
mapping set is deliberately small; it currently includes the documented supermarket/groceries
example, not a broad bank taxonomy.

During import review, `save_rule: true` explicitly creates or updates one family-specific exact
merchant rule. It is never implicit on row edits, bulk actions, or confirmation. An existing
equivalent rule is reused; extra active equivalents are deactivated. Draft preview does not create
Merchant records.

## Без категории

Операцию можно оставить без категории, чтобы не блокировать импорт. Но такие операции должны:

- попадать в блок `Без категории`;
- быть доступны в списке "разобрать позже";
- давать напоминание или инсайт, если сумма заметная.

## Неизвестные операции

Если операция не попадает в известные правила, сервис должен предложить:

- выбрать существующую категорию;
- создать новую категорию или подкатегорию;
- оставить без категории;
- сохранить правило на будущее.

## Продавцы

Продавец должен храниться отдельно от категории, чтобы строить аналитику:

- где чаще покупаем;
- сколько тратим в каждом супермаркете;
- какие продавцы входят в конкретную категорию;
- как меняются траты по продавцам со временем.

## Особые типы операций

### Накопления

Операции `Скарбничка`, округления и 1% от доходов классифицируются как накопления. Они не должны попадать в обычные расходы, но должны отображаться в cash flow и отдельном блоке накоплений.

### Переводы физлицам

Переводы на карту или конкретному человеку отправляются на проверку. После ручной классификации можно сохранить правило:

- получатель -> категория;
- получатель -> scope;
- получатель -> тип операции.

### Переводы жене

Переводы жене учитываются как часть семейного денежного потока. По умолчанию их можно показывать как "Перевод жене", но пользователь может уточнить:

- компенсация семейной траты;
- личные расходы жены;
- другая цель.

### Платежи по реквизитам

Платежи по реквизитам первый раз отправляются на проверку. Затем создается правило получатель -> категория. Примеры:

- школа сына -> Дети / Образование;
- футбол сына -> Дети / Спорт.

### Рабочие/FOP операции

Потенциально рабочие операции, например Upwork, LinkedIn, ChatGPT и похожие сервисы, идут на проверку или правило. Они могут быть помечены scope `work_fop` и скрыты из семейной аналитики по умолчанию.

### Подписки

Подписки и цифровые сервисы выделяются в отдельную категорию. Повторяющиеся платежи по продавцу и похожей сумме могут давать инсайт "возможная подписка".
