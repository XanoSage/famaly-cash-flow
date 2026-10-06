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

The implemented MVP uses one idempotently created, family-owned UAH cash wallet. Its approximate
balance is the sum of non-deleted wallet transaction amounts; there is no separate mutable balance
table. A withdrawal is represented as one negative source-account transfer leg and one matching
positive wallet leg. Family income/expense analytics exclude both legs and count the logical transfer
once. A later cash purchase is one ordinary wallet expense and counts as a family expense once.

Web provides a Cash page to create the wallet, record a withdrawal from an active same-currency
non-cash account, record a cash expense with category/scope/comment, and review recent wallet
activity. An eligible imported ATM withdrawal can be linked to the wallet: the imported source row is
reclassified as a transfer and only the destination leg is created. This avoids duplicating the bank
debit. The linked legs are atomic and paired for soft deletion; generic edits are blocked so one leg
cannot be changed independently.

Telegram `/cash 450 Рынок` records a cash expense through the same `TransactionService`. If the
family wallet has not been created, the bot asks the user to create it in Web. Telegram cash entries
use the service's UTC timestamp default. Bank-import wall-time handling remains unchanged.

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

