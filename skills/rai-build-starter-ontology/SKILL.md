---
name: rai-build-starter-ontology
description: Build a starter RAI ontology from Snowflake source tables following ontology design best practices. Use when creating a new model from scratch.
---

# Build Starter Ontology

Read the examples before writing code — they show real production models with annotated patterns:

@references/examples.md

## Summary

**What:** Build a working RAI ontology from Snowflake source tables, applying ontology design best practices from the start.

**When to use:**
- Starting a new RAI project from Snowflake tables
- User has raw tables and wants a base model to query or build on
- Bootstrapping an ontology before optimization or graph analysis

**When NOT to use:**
- Enriching an existing model for optimization — see `rai-ontology-design` (enrichment workflow)
- Reviewing or modifying a modeler-exported model — see `rai-ontology-design` (modeler format)
- PyRel syntax questions — see `rai-pyrel-coding`

**Overview:**
1. Scope the model — what questions must it answer?
2. Discover source tables and columns from Snowflake
3. Identify concepts, relationships, and properties (domain-first, not schema-first)
4. Generate core layer code
5. Generate computed layer code (if derived metrics are needed)
6. Validate the model loads without errors

**Design principles are in `rai-ontology-design`.** This skill is the *workflow* for applying those principles to Snowflake tables. Defer to `rai-ontology-design` for any design decision (concept vs property, Property vs Relationship, enrichment, gap classification).

---

## Instructions

### Step 1 — Scope the model

Before looking at any tables, define:
- **1-3 concrete questions** the model must answer (e.g., "Which suppliers have the longest lead times?", "What is the cost breakdown by product line?")
- **What is out of scope** — explicitly exclude tables/domains that aren't needed yet

Keep the first version to ~10-15 must-have properties. A tight scope avoids rework.

| Goal | In scope | Out of scope |
|---|---|---|
| Identify delayed orders | Orders, shipments, delay timestamps | Returns, carrier contracts, inventory |

---

### Step 2 — Discover source tables

Read `raiconfig.yaml` to get the active Snowflake connection. List tables and columns:

```sql
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM <database>.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = '<schema>'
ORDER BY TABLE_NAME, ORDINAL_POSITION;
```

Record each column's name, data type, and nullability. Note columns with `_ID` suffixes (likely PKs/FKs), `IS_`/`HAS_` prefixes (boolean flags), and repeated string categories (enums).

---

### Step 3 — Identify concepts, relationships, and properties

**Work domain-first.** Think about what business entities exist, then map to tables — not the other way around.

For each table, determine:

1. **Is it an entity?** Tables with a clear natural key (ID column) become concepts. Name them as singular business nouns: `Customer`, `Order`, `Product` — never `CUSTOMER_TABLE` or `TBL_CUST`.

2. **Is it a junction/fact table?** Tables joining two entities (e.g., `ORDER_ITEMS` links Order and Product) may become a concept with compound identity, or a relationship — depending on whether the junction has its own meaningful properties.

3. **FK columns become Relationships.** Use `Relationship` for all concept-to-concept links, even many-to-one. `Property` is for scalar values only (see `rai-ontology-design` § Relationship Principles).

4. **Boolean flags become unary Relationships.** `IS_ACTIVE`, `HAS_DISCOUNT` → `Customer.is_active = model.Relationship(f"{Customer} is active")`. Not boolean properties.

5. **Enum/status columns become value-type Concepts.** `STATUS`, `TYPE`, `CATEGORY` columns with repeated string values → typed enum concepts, not raw strings.

6. **Remaining columns become Properties.** Scalar attributes on their parent concept. Not every column needs a property — omit columns with no business meaning for the scoped questions.

**Validate before coding:**
- Are proposed concepts orthogonal? (No two concepts with identical entity sets)
- Can each concept be grounded to at least one source table?
- Do FK relationships connect independently meaningful concepts?

---

### Step 4 — Generate core layer code

For each entity, create a file following this structure:

```python
import relationalai.semantics as rai

def define_customer(m: rai.Model, source: rai.Model.Table):
    # Identity
    m.CustomerId = m.Concept("CustomerId", extends=[rai.String])
    m.Customer = m.Concept("Customer", identify_by={"id": m.CustomerId})

    # Value types for key properties
    m.CustomerName = m.Concept("CustomerName", extends=[rai.String])
    m.CustomerCreditLimit = m.Concept("CustomerCreditLimit", extends=[rai.Float])

    # Properties (concept -> scalar value)
    m.Customer.name = m.Property(f"{m.Customer} has name {m.CustomerName}")
    m.Customer.credit_limit = m.Property(f"{m.Customer} has credit limit {m.CustomerCreditLimit}")

    # Relationships (concept -> concept) — even for many-to-one FKs
    m.Customer.home_region = m.Relationship(f"{m.Customer} home region {m.Region}")
    m.Region.has_customer = m.Relationship(f"{m.Region} has customer {m.Customer}")

    # Unary flags (boolean columns)
    m.Customer.is_active = m.Relationship(f"{m.Customer} is active")

    # Data binding
    m.define(m.Customer.new(id=source["CUST_ID"]))
    cust = m.where(m.Customer.id == source["CUST_ID"])
    cust.define(m.Customer.name(source["CUST_NAME"]))
    cust.define(m.Customer.credit_limit(source["CREDIT_LIMIT"]))

    # FK binding — use the referenced entity's identity
    m.where(
        m.Customer.id == source["CUST_ID"],
        m.Region.id == source["REGION_ID"],
    ).define(m.Customer.home_region(m.Region))

    # Unary flag binding
    m.where(
        cust := m.Customer.filter_by(id=source["CUST_ID"]),
        source["IS_ACTIVE"] == "Y",
    ).define(m.Customer.is_active())
```

**Key rules:**
- `Property` for scalar values only (concept -> primitive). `Relationship` for all concept-to-concept links.
- Use bracket syntax for column access: `source["COL"]` not `source.COL`
- Domain names for concepts and properties, not schema names
- Define inverses for navigable relationships

**Snowflake type mapping:**

| Snowflake type | RAI base type |
|---|---|
| VARCHAR, TEXT | `rai.String` |
| NUMBER(p,s) where s > 0 | `rai.Float` (or `rai.Number.size(p,s)` for precision) |
| NUMBER, INT (no scale) | `rai.Integer` |
| FLOAT, DOUBLE | `rai.Float` |
| DATE | `rai.Date` |
| TIMESTAMP_NTZ, TIMESTAMP | `rai.DateTime` |
| BOOLEAN | Unary `Relationship` (not boolean property) |

---

### Step 5 — Generate computed layer (optional)

Only add computed concepts when the scoped questions require derived metrics that aren't directly in source tables.

**Aggregation metrics:**
```python
m.CustomerOrderCount = m.Concept("CustomerOrderCount", extends=[rai.Integer])
m.Customer.order_count = m.Property(f"{m.Customer} has order count {m.CustomerOrderCount}")
m.define(m.Customer.order_count(rai.count(m.Order).per(m.Customer)))
```

**Entity subtypes** (promote recurring filters):
```python
m.HighValueCustomer = m.Concept("HighValueCustomer", extends=[m.Customer])
m.define(m.HighValueCustomer(m.Customer)).where(
    m.Customer.total_spend >= 10000,
)
```

**Rules:**
- Core layer owns identity and source-column bindings. Computed layer derives from core — no direct source column references.
- Prefer recomputing from base facts over importing pre-computed columns (see `rai-ontology-design` § Computed vs pre-computed data).

---

### Step 6 — Create entry point and validate

Create an `__init__.py` that calls all `define_*` functions in dependency order (referenced entities before referencing ones):

```python
def define_model(m, db, schema):
    src = lambda t: m.Table(f"{db}.{schema}.{t}")
    define_region(m, src("REGIONS"))
    define_customer(m, src("CUSTOMERS"))  # depends on Region
    define_order(m, src("ORDERS"))        # depends on Customer
    return m
```

Validate:
```bash
python -c "import relationalai.semantics as rai; m = rai.Model('test'); from <package>.model import define_model; define_model(m, '<DB>', '<SCHEMA>')"
```

Fix any import errors. Report the entity map: which tables became concepts, which became relationships, what computed metrics were added.

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Using `Property` for FK relationships | Use `Relationship` for all concept-to-concept links. Property is for scalar values only. |
| Schema-driven names (`CUST_TABLE`, `ORD_AMT`) | Use business domain names (`Customer`, `amount`) |
| Boolean columns as `Property(f"... {Boolean:is_active}")` | Use unary `Relationship(f"... is active")` |
| Importing pre-computed aggregates | Recompute from base facts when possible |
| Modeling every column | Only model columns relevant to the scoped questions |
| Missing inverses on relationships | Define both directions for navigable relationships |
| Using `source.COL` dot syntax | Use `source["COL"]` bracket syntax (safer) |
