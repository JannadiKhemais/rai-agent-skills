# Pattern: Scenario Concept result extraction — results live in the ontology
# Key ideas: after a single solve with Scenario as a Concept, results are queryable
# via model.select() like any other property; per-scenario aggregation uses the same
# .where()/.per() patterns as constraints; no variable_values().to_df() needed.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("portfolio")

# --- Ontology ---
Stock = model.Concept("Stock", identify_by={"index": Integer})
Stock.returns = model.Property(f"{Stock} has {Float:returns}")
Stock.covar = model.Property(f"{Stock} and {Stock} have {Float:covar}")

Scenario = model.Concept("Scenario", identify_by={"name": String})
Scenario.min_return = model.Property(f"{Scenario} has {Float:min_return}")
scenario_data = model.data(
    [("conservative", 10), ("moderate", 20), ("aggressive", 30)],
    columns=["name", "min_return"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# Decision variable indexed by Scenario
Stock.x_quantity = model.Property(f"{Stock} in {Scenario} has {Float:quantity}")
x_qty = Float.ref()
PairedStock = Stock.ref()
paired_qty = Float.ref()
covar_value = Float.ref()
budget = 1000

# --- Formulation ---
p = Problem(model, Float)
p.solve_for(Stock.x_quantity(Scenario, x_qty),
            name=[Scenario.name, "qty", Stock.index])
p.satisfy(model.where(Stock.x_quantity(Scenario, x_qty)).require(x_qty >= 0))
p.satisfy(model.where(Stock.x_quantity(Scenario, x_qty)).require(
    sum(x_qty).per(Scenario) <= budget))
p.satisfy(model.where(Stock.x_quantity(Scenario, x_qty)).require(
    sum(x_qty * Stock.returns).per(Scenario) >= Scenario.min_return))

risk = sum(covar_value * x_qty * paired_qty).per(Scenario).where(
    Stock.x_quantity(Scenario, x_qty),
    PairedStock.x_quantity(Scenario, paired_qty),
    Stock.covar(PairedStock, covar_value),
)
p.minimize(sum(risk))

p.solve("highs", time_limit_sec=60)

# --- Result extraction: all queries use model.select() ---

# 1. Solve status
si = p.solve_info()
si.display()
print(f"Status: {si.termination_status}")
print(f"Objective (total risk): {si.objective_value}")

# 2. Per-scenario allocations — results are in the ontology, queryable like any property
print("\nPortfolio allocations per scenario:")
model.select(
    Scenario.name.alias("scenario"),
    Stock.index.alias("stock"),
    Stock.returns,
    x_qty.alias("quantity"),
).where(
    Stock.x_quantity(Scenario, x_qty), x_qty > 0.001
).inspect()

# 3. Per-scenario aggregation — composable with other model queries
print("\nRisk by scenario:")
model.select(Scenario.name, risk.alias("risk")).inspect()

# 4. Per-scenario total allocation
print("\nTotal allocation by scenario:")
total_alloc = sum(x_qty).per(Scenario).where(Stock.x_quantity(Scenario, x_qty))
model.select(Scenario.name, total_alloc.alias("total_invested")).inspect()

# 5. Per-scenario expected return
print("\nExpected return by scenario:")
expected_ret = sum(x_qty * Stock.returns).per(Scenario).where(
    Stock.x_quantity(Scenario, x_qty)
)
model.select(
    Scenario.name,
    Scenario.min_return.alias("target"),
    expected_ret.alias("achieved"),
).inspect()
