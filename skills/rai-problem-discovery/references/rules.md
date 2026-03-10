## Rules Question Types

Rules reasoning enforces business logic, validates compliance, and derives classifications from known facts.

**Current platform status:** There is no dedicated RAI rules reasoner. Today, business rules are expressed as **derived ontology properties and concepts** — e.g., `Business.is_high_value_customer` defined as `TYPE='BUYER' AND value_tier='HIGH'`. Complex conditional logic, threshold checks, and derived classifications are modeled directly in PyRel as ontology-layer definitions.

| Type | Question Pattern | Ontology Signal |
|------|-----------------|-----------------|
| **Validation** | "Is this compliant / valid / within policy?" | Concepts with threshold/limit properties, regulatory categories, approval status fields |
| **Classification** | "What category based on business rules?" | Hierarchical categories, conditional membership criteria, tier/grade definitions |
| **Derivation** | "What follows from these facts?" | Transitive relationships (A manages B, B manages C → A indirectly manages C), inheritance patterns |
| **Alerting** | "What violates policy / needs attention?" | Concepts with limit/threshold properties, SLA definitions, overdue/expired status fields |
| **Reconciliation** | "Do these two sources agree?" | Multiple concepts representing overlapping data (orders vs invoices, planned vs actual) |

---

## When Rules vs Other Reasoners

- Deterministic logic over known facts → **rules** (derived ontology properties)
- "Predict whether it will violate" (uncertain outcome) → **predictive** (or predictive → rules chain)
- "Optimize to minimize violations" (decision-making) → **prescriptive**
- "Find all connected violations in the network" → **graph** (or graph → rules chain)
- Simple threshold classification (e.g., "high-value if spend > $10K") → derived property in ontology, not a separate reasoner

**Common chains involving rules:**
- Rules → Predictive: classify/validate entities first, then predict outcomes for the valid subset
- Predictive → Rules: predict risk scores, then apply threshold rules for alerting
- Rules → Prescriptive: identify constrained/valid options first, then optimize among them
- Graph → Rules: identify structural properties (bridges, isolated components), then flag via business rules

---

## Implementation Approach

Since rules are expressed as ontology-layer derivations, the "implementation" for a rules suggestion is:

1. **Identify the rule logic** — what conditions, thresholds, or classifications apply
2. **Model as derived properties/concepts** — define in PyRel using `.where()` conditions and `define()` statements
3. **Reference existing ontology properties** — rules operate on data already in the model

Rules suggestions should include:
- **source_concept**: Which concept the rule applies to
- **condition_properties**: Which properties form the rule condition
- **threshold / logic**: The business rule definition
- **output_property**: What derived property the rule creates (e.g., `is_compliant`, `risk_category`, `is_overdue`)

---

## Rule Pattern Signals

What ontology patterns indicate rules reasoning potential:

- **Threshold/limit properties**: max_capacity, min_balance, credit_limit, sla_hours — natural rule boundaries
- **Status/category fields**: approval_status, risk_tier, compliance_grade — rule-driven classifications
- **Hierarchical concepts**: Category → Subcategory → Item with inheritance of rules down the hierarchy
- **Cross-entity comparisons**: Order.amount vs Customer.credit_limit, Actual.hours vs Plan.hours
- **Temporal compliance**: Due dates, SLA deadlines, review periods — time-based rule triggers

**Minimum viable ontology for rules:** At least one concept with properties that define a business rule boundary (threshold, category, status) and entities to evaluate against it.
