# Implementation Readiness

Документ фиксирует критерии, после которых можно начинать реализацию MVP.

## Ready To Start When

ТЗ достаточно готово для старта реализации, когда выполнены:

- заполнен remaining questions опросник;
- ответы перенесены в основные docs;
- есть короткий implementation plan;
- есть минимальные wireframe-описания UI.

## Remaining Before Coding

Перед первым кодовым этапом нужно:

- создать ветку `staging` от `main`;
- подготовить implementation plan по этапам;
- решить, начинать с backend skeleton или monorepo skeleton целиком;
- создать `.env.example`;
- добавить synthetic sample XLSX или synthetic transaction dataset для тестов.

## Recommended First Implementation Slice

1. Monorepo skeleton.
2. Backend FastAPI skeleton.
3. PostgreSQL + Docker Compose.
4. SQLAlchemy + Alembic.
5. Seed system categories from [Category Taxonomy](category-taxonomy.md).
6. Auth skeleton.
7. XLSX parser spike on known bank format.

