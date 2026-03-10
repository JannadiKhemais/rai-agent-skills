# RelationalAI-Cortex Integration

Deploy Snowflake Cortex AI agents powered by RelationalAI semantic models for Snowflake Intelligence.

## Quickstart

```python
from snowflake import snowpark

from relationalai.semantics import Model
from relationalai.config import create_config, SnowflakeConnection
from relationalai.agent.cortex import CortexAgentManager, DeploymentConfig, discover_imports, ToolRegistry

# Create session using role for deployment
session: snowpark.Session = create_config().get_session(SnowflakeConnection)

# Configure manager
manager = CortexAgentManager(
    session=session,
    config=DeploymentConfig(
        agent_name="MY_ASSISTANT",  # Unique name for the agent
        database="MY_DB",           # Snowflake database for deployment (sprocs & agent)
        schema="MY_SCHEMA",         # Snowflake schema for deployment (sprocs & agent)
        warehouse="COMPUTE_WH"))    # Warehouse for RAI tool execution (SI users need USAGE)

# Your model definition function
def initialize(m: Model):
    # Define your entities, relationships, and computed properties
    ...

# Initialize RAI Tools
def init_tools(model: Model):
    initialize(model)  # Initialize RAI Model with your semantics
    return ToolRegistry().add(
        model=model,   # Expose model through tools
        description="...")


# Deploy
manager.deploy(
    init_tools=init_tools,       # Initialize RAI Tools
    imports=discover_imports())  # Specify local python modules to package into sproc

print(manager.status())
```

After deployment, you can find the Cortex Agent in the Snowflake UI under **AI & ML > Agents**. The UI allows you to chat with the agent, preview or add it to Snowflake Intelligence, and view traces of conversations the agent participates in.

For programmatic access (testing, automation):

```python
chat = manager.chat()
response = chat.send("What can I ask about?")
print(response.full_text())
```

Conversations through the programmatic interface are persisted and available through the Monitoring tab for the agent in the Snowflake UI.

## How It Works

The RelationalAI-Cortex integration
1) operationalizes your RAI Model into Snowflake stored procedures
2) configures a Cortex Agent with these tools, and instructions on how to explore your semantic models and answer questions about your data.

| Tool | Purpose |
|------|---------|
| `RAI_DISCOVER_MODELS` | Discover available models and their key concepts |
| `RAI_VERBALIZE_MODEL` | Get detailed model structure and relationships |
| `RAI_EXPLAIN_CONCEPT` | Understand business rules for specific concepts |
| `RAI_QUERY_MODEL` | Execute pre-defined queries (**PREVIEW** — requires `allow_preview=True`) |

### RBAC: Caller's Rights

All stored procedures are created with **CALLER'S RIGHTS** — they execute under the SI user's Snowflake role, not the deployer's role. This means:

- **Data access is governed by the caller's role.** Users only see data their role can `SELECT`.
- **No privilege escalation.** The agent never operates with more permissions than the person using it.

This makes Snowflake's existing RBAC the single source of truth for data governance across all agent interactions.

## Snowflake Privileges

The following permissions are required for two roles:
1) **deployer/admin** who creates the Cortex Agent
2) **SI users** who interact with it through the Snowflake Intelligence UI (or, programmatic users of the Cortex Agent)

Both require the `rai_developer` role.

### `rai_developer` Role

The `rai_developer` role is created during RAI Native App installation. It grants access to RAI and includes the following privileges by default:

| Privilege | Purpose |
|-----------|---------|
| `USAGE` on `S3_RAI_INTERNAL_BUCKET_EGRESS_INTEGRATION` | External access for RAI stored procedures |
| `USAGE` on `PYPI_ACCESS_INTEGRATION` | Access to Python packages during sproc execution |

These are necessary to execute the Snowflake stored procedures.

### Deployer / Admin

| Privilege | Purpose |
|-----------|---------|
| `CREATE STAGE` on target schema | Store sproc dependencies (if `manage_stage=True`) |
| `CREATE PROCEDURE` on target schema | Register RAI tool sprocs |
| `CREATE AGENT` on target schema | Register the Cortex agent |
| `database role snowflake.cortex_user` | Access Cortex services |
| `database role snowflake.pypi_repository_user` | Install Python packages in the sproc environment |
| `application role snowflake.ai_observability_events_lookup` | Monitor AI observability events |
| `rai_developer` role | Access RAI (see above) |
| `USAGE` on database and schema | Access the deployment target |

### SI Users

Because sprocs use CALLER'S RIGHTS, SI users need privileges on the resources the agent accesses at runtime:

| Privilege | Purpose |
|-----------|---------|
| `USAGE` on warehouse | Execute sprocs (warehouse from `DeploymentConfig`, or session default) |
| `database role snowflake.cortex_user` | Access Cortex services |
| `database role snowflake.pypi_repository_user` | Install Python packages in the sproc environment |
| `rai_developer` role | Access RAI (see above) |
| `USAGE` on database and schema | Access the data |
| `SELECT` on tables | Read data accessed by the model |
| `EXECUTE` on stored procedures | Invoke RAI tools |

### Example Role Definitions

```sql
-- Deployer role
create role my_deployer_role;
grant create stage on schema my_db.my_schema to role my_deployer_role;
grant create procedure on schema my_db.my_schema to role my_deployer_role;
grant create agent on schema my_db.my_schema to role my_deployer_role;
grant database role snowflake.cortex_user to role my_deployer_role;
grant database role snowflake.pypi_repository_user to role my_deployer_role;
grant application role snowflake.ai_observability_events_lookup to role my_deployer_role;
grant role rai_developer to role my_deployer_role;
grant usage on database my_db to role my_deployer_role;
grant usage on schema my_db.my_schema to role my_deployer_role;

-- SI user role
create role my_si_user_role;
grant usage on warehouse compute_wh to role my_si_user_role;
grant database role snowflake.cortex_user to role my_si_user_role;
grant database role snowflake.pypi_repository_user to role my_si_user_role;
grant role rai_developer to role my_si_user_role;
grant usage on database my_db to role my_si_user_role;
grant usage on schema my_db.my_schema to role my_si_user_role;
grant select on all tables in schema my_db.my_schema to role my_si_user_role;
grant execute on all procedures in schema my_db.my_schema to role my_si_user_role;
```

## Configuration

### DeploymentConfig

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `database` | Yes | - | Snowflake database where agent will be deployed |
| `schema` | Yes | - | Snowflake schema where agent will be deployed. To enable interaction through the Snowflake Intelligence UI, deploy to the schema configured for your account (typically `AGENTS`) |
| `agent_name` | Yes | - | Unique name for the Cortex agent within the schema |
| `model_name` | No | Same as `agent_name` | Name for the `Model` instance created inside each stored procedure |
| `warehouse` | No | None | Snowflake warehouse the Cortex agent will use when executing RAI tools. SI users need USAGE on this warehouse. If omitted, tools use the caller's session warehouse. Stored procedures are created with CALLER'S RIGHTS |
| `stage_name` | No | `"rai_sprocs"` | Name of the Snowflake stage for storing sproc dependencies |
| `manage_stage` | No | `True` | If `True`, automatically create/drop the stage during deploy/cleanup. Set to `False` if using a pre-existing stage |
| `llm` | No | `"claude-sonnet-4-5"` | Language model for agent orchestration. Must be available in Snowflake Cortex |
| `query_timeout_s` | No | `300` | Timeout in seconds for stored procedure execution |
| `budget_seconds` | No | None | Time budget in seconds for agent execution. Can be used with `budget_tokens` |
| `budget_tokens` | No | None | Token budget for model consumption. Can be used with `budget_seconds` |
| `external_access_integration` | No | `"S3_RAI_INTERNAL_BUCKET_EGRESS_INTEGRATION"` | External access integration for sprocs. USAGE is granted by the `rai_developer` role by default |
| `artifact_repository` | No | `"snowflake.snowpark.pypi_shared_repository"` | Artifact repository for Python packages |
| `allow_preview` | No | `False` | Allow Preview capabilities (e.g., queries) |

## Verbalizers

Verbalizers control how model structure is presented to the agent.

### ModelVerbalizer (Default)

Returns relationship readings extracted from the RAI model:

```
Customer has many Orders
Order has one Customer
Order contains many OrderItems
...
```

This is the default — no configuration needed.

### SourceCodeVerbalizer

Extends `ModelVerbalizer`: `explain_model` returns the standard relationship
readings, while `explain_concept` returns the Python source code from the
modules you provide, filtered to those that reference the requested concept.

Pass the model as the first argument, followed by your model definition functions:

```python
from relationalai.agent.cortex import SourceCodeVerbalizer


def init_tools(model: Model):
    init_model(model)
    return ToolRegistry().add(
        model=model,
        description="Customers and orders",
        verbalizer=SourceCodeVerbalizer(model, init_model)
    )
```

The agent sees actual Python code for specific concepts, including business logic and computed properties.

Comments are included, so clarifications and justifications of your code will benefit the agent as well.

## Queries (PREVIEW)

> **Note:** The queries capability is in PREVIEW. Deployment requires `allow_preview=True`. Please contact us first!

Pre-defined queries let domain experts create common analytical queries that agents can discover and execute.

### Defining Queries

Create a class to hold your queries with the model as a dependency:

```python
import relationalai.semantics as rai

class CustomerAnalysis:
    def __init__(self, m):
        self.m = m

    def segment_summary(self) -> rai.Fragment:
        """Topline metrics per customer value segment"""
        customer = self.m.Customer.ref()
        segment = self.m.Customer.ValueSegment.ref()
        order = self.m.Order.ref()
        g = rai.per(segment)
        return self.m.select(
            segment.name.alias("segment"),
            g.sum(customer.ltv).alias("revenue"),
            g.sum(order.profit)
            .where(customer.order(order))
            .alias("profit")
        ).where(
            customer.value_segment(segment)
        )
```

### Registering Queries

```python
from relationalai.agent.cortex import QueryCatalog


def init_tools(model: Model):
    init_model(model)
    queries = CustomerAnalysis(model)
    return ToolRegistry().add(
        model=model,
        description="Customers and orders",
        verbalizer=SourceCodeVerbalizer(model, init_model),
        queries=QueryCatalog(queries.segment_summary)
    )


# Deploy with preview enabled — set allow_preview on DeploymentConfig
manager = CortexAgentManager(
    session=session,
    config=DeploymentConfig(
        agent_name="MY_ASSISTANT",
        database="EXAMPLE",
        schema="CORTEX",
        warehouse="COMPUTE_WH",
        allow_preview=True,
    )
)

manager.deploy(
    init_tools=init_tools,
    imports=discover_imports(),
)
```

The agent can discover these queries and execute them with appropriate parameters based on user requests.

## Packaging Code for Deployment

When deploying, you need to provide code that runs inside Snowflake stored procedures. There are two parameters for this:

### `imports` - Your Project Code

The `imports` parameter packages your local Python files (model definitions, queries, etc.) and uploads them to Snowflake. Use `discover_imports()` to automatically find all modules imported by your `init_tools` function:

```python
manager.deploy(
    init_tools=init_tools,
    imports=discover_imports()  # Packages your project code
)
```

`discover_imports()` recursively discovers all local imports starting from the calling file. It excludes standard library and installed packages.

### `extra_packages` - PyPI Dependencies

The `extra_packages` parameter specifies PyPI packages that Snowflake will install in the stored procedure environment. Use this for third-party libraries your code depends on:

```python
manager.deploy(
    init_tools=init_tools,
    imports=discover_imports(),
    extra_packages=["pandas==2.0.0", "numpy"]  # Installed by Snowflake
)
```

Note: `relationalai` is included automatically.

## Updating Agents

Update tool definitions without recreating the agent:

```python
def init_tools_v2(model: Model):
    # Updated tool definitions
    ...

manager.update(init_tools=init_tools_v2, imports=discover_imports())
```

## Lifecycle

Check deployment status or tear down all resources:

```python
print(manager.status())   # Reports what exists (agent, stage, sprocs)
manager.cleanup()          # Drops agent, sprocs, and stage — permanently loses SI conversation history
```

## Examples

This directory contains three examples that progressively add capabilities:

| Example | File | Description |
|---------|------|-------------|
| Default | `cortex.py` | Minimal setup using built-in model verbalization |
| Verbalizer | `cortex_verbalizer.py` | Adds `SourceCodeVerbalizer` for richer model context |
| Verbalizer + Queries | `cortex_verbalizer_queries.py` | Adds `QueryCatalog` for pre-defined queries (PREVIEW) |

Run any example with:

```bash
python -m example.cortex.cortex
python -m example.cortex.cortex_verbalizer
python -m example.cortex.cortex_verbalizer_queries
```
