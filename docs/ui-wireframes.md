# UI Wireframes

Минимальные wireframe-описания. Это не финальный дизайн, а карта экранов перед реализацией.

## App Shell

```text
┌─────────────────────────────────────────────────────────────┐
│ Top bar: period selector | language | notifications | user  │
├──────────────┬──────────────────────────────────────────────┤
│ Sidebar      │ Page content                                  │
│ Dashboard    │                                              │
│ Import       │                                              │
│ Operations   │                                              │
│ Categories   │                                              │
│ Merchants    │                                              │
│ Cash         │                                              │
│ Budgets      │                                              │
│ Settings     │                                              │
└──────────────┴──────────────────────────────────────────────┘
```

## Dashboard

```text
┌─────────────────────────────────────────────────────────────┐
│ Period selector                                             │
├────────────┬────────────┬────────────┬────────────┬────────┤
│ Expenses   │ Income     │ Savings    │ Budget     │ Review │
├─────────────────────────┬───────────────────────────────────┤
│ Expense timeline        │ Budget risk categories             │
├─────────────────────────┼───────────────────────────────────┤
│ Category bar chart      │ Top merchants                       │
├─────────────────────────┼───────────────────────────────────┤
│ Savings block           │ Work/FOP card/block                 │
└─────────────────────────┴───────────────────────────────────┘
```

## Import Preview

```text
┌─────────────────────────────────────────────────────────────┐
│ Import summary: period, rows, review, duplicates, totals    │
├─────────────────────────────────────────────────────────────┤
│ Filters: needs review | duplicates | errors | merchant ...  │
├─────────────────────────────────────────────────────────────┤
│ Bulk action bar: category | scope | create rule | apply      │
├─────────────────────────────────────────────────────────────┤
│ Preview table                                                │
│ date | amount | merchant | bank cat | proposed cat | status │
├─────────────────────────────────────────────────────────────┤
│ Final summary + Confirm import                              │
└─────────────────────────────────────────────────────────────┘
```

## Operations

```text
┌─────────────────────────────────────────────────────────────┐
│ Filters: period, category, merchant, scope, flow, amount     │
├─────────────────────────────────────────────────────────────┤
│ Table with configurable columns                              │
│ date | amount | merchant | category | flow | scope | comment │
└─────────────────────────────────────────────────────────────┘

Right drawer:
┌──────────────────────────────┐
│ Edit transaction              │
│ category                      │
│ merchant                      │
│ flow type                     │
│ scope                         │
│ comment                       │
│ save / soft delete            │
└──────────────────────────────┘
```

## Cash

```text
┌─────────────────────────────────────────────────────────────┐
│ Approx cash balance | withdrawn | manually spent | reminder │
├─────────────────────────────────────────────────────────────┤
│ Quick cash expense form                                      │
├─────────────────────────────────────────────────────────────┤
│ Cash transactions table                                      │
└─────────────────────────────────────────────────────────────┘
```

## Budgets

```text
┌─────────────────────────────────────────────────────────────┐
│ Month selector | draft/final status                         │
├─────────────────────────────────────────────────────────────┤
│ Total family budget progress                                │
├─────────────────────────────────────────────────────────────┤
│ Category limits table                                       │
│ category | limit | spent | warning | status                 │
└─────────────────────────────────────────────────────────────┘
```

