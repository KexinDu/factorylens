# FactoryLens architecture

FactoryLens adds evidence retrieval, diagnosis and maintenance workflow to the
MachineGuard AI dashboard and predictive models. The API starts the services
against a single SQLite database per environment.

## System

```mermaid
flowchart LR
    UI["React and Vite UI"] -->|"REST and Markdown downloads"| API["FastAPI"]
    API --> ML["MachineGuard prediction service"]
    UCI["Processed UCI hydraulic cycles"] --> ML
    Models["Bundled classifier and Isolation Forest"] --> ML
    ML --> DB[("SQLite")]
    API --> KB["Knowledge library · TF-IDF and cosine similarity"]
    Examples["Bundled educational documents"] --> KB
    KB --> DB
    API --> Agent["Diagnostic Agent"]
    Agent --> ML
    Agent --> KB
    Agent -->|"Responses API · optional and server-side"| Cloud["OpenAI direct or OpenLux"]
    Agent --> History["Diagnosis history and evidence snapshots"]
    History --> DB
    API --> Orders["Work order service"]
    Orders --> DB
    API --> Reports["Deterministic Markdown exporter"]
    Reports --> History
    Reports --> Orders
```

The cloud path is opt-in and restricted to public UCI equipment records and
verified bundled excerpts. Private uploads and manually entered equipment can
be used in the local retrieval-only workflow.

## Tool calling and RAG

```mermaid
flowchart TD
    Request["Device ID, question and cloud opt-in"] --> Verify["Read selected record and score one sensor snapshot"]
    Verify --> Eligible{"Eligible cloud request?"}
    Eligible -->|Yes| ToolRound["Offer three read-only tools to the model"]
    ToolRound --> Dispatch["Validate tool name, arguments and device scope"]
    Dispatch --> Tools["Return equipment data, ML scores or TF-IDF excerpts"]
    Tools --> Budget{"More search needed and budget remains?"}
    Budget -->|Yes| ToolRound
    Budget -->|No| Final["Send verified context and replay tool results with call IDs"]
    Final --> Structured["Request strict JSON Schema output"]
    Structured --> Valid{"Complete result and valid references?"}
    Valid -->|Yes| Save["Save readings, model findings, output, evidence and trace"]
    Valid -->|No| Local["Run local retrieval and explain the fallback"]
    Eligible -->|No| Local
    ToolRound -->|Provider error or budget exceeded| Local
    Structured -->|Timeout or provider error| Local
    Local --> Save
```

The backend fills numeric findings and keeps source attribution. Execution
trace rows record backend or model-originated tool calls. Limits, citation
validation and evidence snapshot behavior are detailed in the
[Diagnostic Copilot guide](diagnostic-copilot.md).

## Maintenance workflow

```mermaid
flowchart LR
    A["Recorded equipment and model results"] --> B["Saved cloud or fallback diagnosis"]
    B --> C["Human reviews hypotheses, evidence and priority"]
    C --> D["Confirm and create one work order per diagnosis"]
    D --> E["Open"]
    E --> F["In Progress"]
    F -->|"Record handling notes"| G["Resolved"]
    B --> H["Diagnosis Markdown report"]
    D --> I["Work order Markdown report"]
    G --> I
```

Work orders use an immutable diagnosis snapshot and maintain current status
and notes. The report endpoints format saved local data without an API call.
