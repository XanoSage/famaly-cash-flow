# Operations And Cash

Документ описывает экран операций, ручной ввод и учет наличных.

## Transactions Table

Колонки таблицы настраиваемые.

Колонки по умолчанию:

- дата;
- сумма;
- merchant;
- категория;
- банк-категория;
- flow type;
- scope;
- original currency;
- comment.

## Filters

Фильтры:

- период;
- категория;
- merchant;
- сумма;
- scope;
- flow type;
- без категории;
- payment instrument;
- original currency.

## Transaction Editing

Редактирование операции происходит через drawer. Этот подход подходит и для desktop, и для mobile.

Drawer должен позволять редактировать:

- категорию и подкатегорию;
- merchant;
- flow type;
- scope;
- comment;
- статус без категории;
- рабочий/FOP scope;
- включение/исключение из аналитики.

## Manual Transaction Input

Ручной ввод операции для MVP:

- дата;
- сумма;
- merchant;
- категория;
- flow type;
- scope;
- comment.

Recurring/subscription hint добавляется позже.

## Quick Cash Input

Для наличных в вебе нужна отдельная короткая форма.

Quick input строкой вроде `рынок 450 овощи` переносится на будущую версию или Telegram bot.

## Cash Balance

Наличный баланс показывается как приблизительный.

UI показывает:

- снято наличных;
- вручную внесенные наличные расходы;
- предполагаемый остаток;
- пометку, что баланс может быть неточным.

## Forgotten Cash Expenses

В MVP:

- веб-напоминание после снятия наличных;
- отдельный блок наличных расходов.

Позже:

- Telegram reminder после снятия наличных.

## Delete Strategy

Для всех операций используется soft delete.

Операция не удаляется физически из базы, а получает признаки:

- `deleted_at`;
- `deleted_by_user_id`;
- `delete_reason`, если нужно.

По умолчанию soft-deleted операции не попадают в аналитику.

