I'll scan the repository to understand the current Flask setup, any existing text-to-SQL code, and how secrets (Doppler) and database are handled, so I can explain the current system and craft a plan. Running quick searches and a directory listing in parallel.
Ran tool
Search files...
Search files...
Search files...
Search files...

Ran tool

I'll open the key files to explain the current system (endpoints, controllers, command flow, prompts, schemas, and the text-to-SQL structured output) so I can describe setup and plan accurately.
Ran tool
Ran tool
Ran tool
Ran tool
Ran tool

Ran tool

Ran tool
Ran tool

### Step 1 — What you need to set up and configure

- **Prereqs**
  - **Python**: 3.12 installed and on PATH.
  - **Git**: repo cloned to `D:\textlayer`.
  - **Doppler**: CLI installed; you will receive a service token.

- **Windows (PowerShell) setup**
  1. Create and activate a virtualenv:
     ```powershell
     cd D:\textlayer
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
  2. Install dependencies:
     ```powershell
     pip install -r requirements.txt
     ```
  3. Configure environment:
     - If using `.env` locally:
       ```powershell
       copy .env.example .env   # If you don’t see it, it likely exists (dotfiles are hidden in the listing)
       # Edit .env with your values:
       # FLASK_CONFIG=DEV
       # OPENAI_API_KEY=sk-...
       # CHAT_MODEL=gpt-4o-mini
       # EMBEDDING_MODEL=text-embedding-3-small
       # KNN_EMBEDDING_DIMENSION=1536
       # Optional Langfuse keys for observability
       ```
     - If using Doppler (recommended for secrets):
       - Install Doppler CLI (any one method):
         - Chocolatey: `choco install doppler`
         - Scoop: `scoop install doppler`
         - MSI: download from `https://cli.doppler.com/install/windows`
       - Set your service token in the current shell:
         ```powershell
         $env:DOPPLER_TOKEN = "dp.pt.YOUR_TOKEN_HERE"
         ```
       - Ensure your Doppler project has these config keys defined:
         - `OPENAI_API_KEY`, `CHAT_MODEL`, `EMBEDDING_MODEL`, `KNN_EMBEDDING_DIMENSION`
         - Optional: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
  4. Run the API:
     - With Doppler:
       ```powershell
       doppler run -- flask --app application.py run
       ```
     - Or with local `.env`:
       ```powershell
       $env:FLASK_APP="application.py"
       python -m flask run
       ```
  5. Test the API:
     - Health:
       ```powershell
       curl http://127.0.0.1:5000/v1/health
       ```
     - Chat (text-to-SQL flow):
       ```powershell
       curl -X POST http://127.0.0.1:5000/v1/threads/chat `
         -H "Content-Type: application/json" `
         -d '{ "messages": [ { "role": "user", "content": "Show total expenses by quarter for 2023" } ] }'
       ```

Notes:
- Base path is `/v1`. The chat endpoint is `POST /v1/threads/chat`.
- The financial dataset is a DuckDB file at `app/data/data.db`. Queries are executed against it.

### Step 2 — Plan to improve the text-to-SQL quality

- Prompting and context
  - Replace the default system prompt with a domain-specific one: finance analytics, SQL style rules, safe patterns.
  - Add few-shot examples: NL question → SQL → brief NL explanation → limit results.
  - Add dynamic context (RAG): introspect DuckDB schema via `DuckDBDatastore.get_columns`/`information_schema` and inject a compact “data dictionary” and sample rows into the system/context messages.

- Safer generation and execution
  - Enforce structured output for SQL using `SqlQuery` so the model returns a single `query` string (SELECT-only).
  - Validate SQL before execution:
    - Reject non-SELECT statements; add regex and a simple SQL parser guard.
    - Enforce `LIMIT` (e.g., 100) if absent.
    - Run `EXPLAIN` first; block queries that would scan massive tables without filters.
    - Optional: LLM-as-a-Judge pass to critique and approve the SQL against the schema context.
  - Parameterize literals when possible (defend against injection-y patterns from model hallucinations).

- Answer composition
  - After execution, generate a concise NL answer summarizing findings; include a small table (first N rows) in Markdown and mention applied filters/assumptions.
  - If no results or low confidence, ask a clarification question.

- Iterative tool flow
  - First call: produce SQL (structured output).
  - Optional judge call: validate SQL (explain reasoning and risks).
  - If approved, execute; else request refinement/clarification.
  - Final call: produce NL summary with the table.

- Observability and evals
  - Keep Langfuse spans for each step (generate → judge → execute → summarize).
  - Add a few evaluation prompts (unit-like) to regression-test SQL validation and summarization.

- Deliverables
  - Enhanced prompt in `app/services/llm/prompts/chat_prompt.py`.
  - SQL generation step via `LLMSession.get_structured_output(SqlQuery)`.
  - SQL validator utility and enforced guards in the command or a new service.
  - Schema-RAG helper in datastore service to fetch and format schema context.
  - Improved response formatting for consistent outputs.

### Step 3 — What the current system is (today)

- Entrypoint and configuration
  - `application.py` creates the Flask app with `create_app(os.getenv('FLASK_CONFIG') or 'DEV')`.
  - `config.py` reads env vars for `OPENAI_API_KEY`, `CHAT_MODEL` (default `gpt-4o-mini`), `EMBEDDING_MODEL` (default `text-embedding-3-small`), and optional Langfuse; sets LiteLLM callbacks accordingly.
  - `app/__init__.py` initializes logging, loads config, registers routes and extensions.

- Routing
  - Base path is remapped to `/v1` via `DispatcherMiddleware`.
  - `app/routes/routes.py` registers the `thread_routes` blueprint at `/threads` and provides `/` and `/health`.
  - Primary endpoint: `POST /v1/threads/chat`.

- Request handling
  - `app/routes/thread_routes.py` validates the request with `chat_messages_schema` and calls `ThreadController.process_chat_message`.
  - `app/schemas/thread_schemas.py` expects:
    ```json
    { "messages": [ { "role": "user", "content": "..." }, ... ] }
    ```

- Controller and command flow
  - `ThreadController` delegates to `ProcessChatMessageCommand`.
  - `ProcessChatMessageCommand`:
    - Builds an `LLMSession` using `CHAT_MODEL` and `EMBEDDING_MODEL`.
    - Registers a single tool `text_to_sql` (via `vaul.Toolkit`).
    - Prepares messages by trimming history and prefixing a minimal system prompt from `chat_prompt()` (currently: “You are a helpful assistant.”).
    - Calls `LLMSession.chat(messages=..., tools=...)` using LiteLLM. If the model returns `tool_calls`, it executes them and appends tool results to the message list. Otherwise it just appends the assistant message.

- LLM session
  - `app/services/llm/session.py` wraps LiteLLM’s `completion` and `embedding`.
  - Adds optional Bedrock Guardrails if configured.
  - Provides message-trimming to meet token limits and Langfuse metadata propagation.

- Text-to-SQL tool and datastore
  - `app/services/llm/tools/text_to_sql.py` exposes a tool `text_to_sql(query: str) -> SqlQuery`. Despite the docstring, it currently:
    - Connects to DuckDB at `app/data/data.db`.
    - Executes the provided SQL string directly.
    - Returns a Markdown table string of the result.
  - `app/services/datastore/duckdb_datastore.py` manages DuckDB connections and queries.

- Current gaps for your task
  - No schema/context is provided to the model; it must guess table/columns.
  - The “text_to_sql” tool does not actually generate SQL from NL; it expects the model to produce SQL and simply executes it.
  - No safety checks (non-SELECT, limits, large scans, injection-like patterns).
  - Minimal prompting; no few-shot, no RAG, no LLM-as-a-Judge.
  - Final response is just whatever the model/tool returns; there’s no guaranteed NL summary + data table format.

- Call shape today
  - You send user messages to `/v1/threads/chat`. If the model decides to call `text_to_sql` with a `query` arg, the system executes it on DuckDB and returns messages including the tool result (Markdown).

- Where to change things
  - Prompt: `app/services/llm/prompts/chat_prompt.py`
  - Tooling and flow: `app/commands/threads/process_chat_message.py`
  - Tool behavior: `app/services/llm/tools/text_to_sql.py`
  - Datastore/schema helpers: `app/services/datastore/duckdb_datastore.py`
  - Structured output: `app/services/llm/structured_outputs/text_to_sql.py`

- Example request to try
  ```bash
  curl -X POST http://127.0.0.1:5000/v1/threads/chat \
    -H "Content-Type: application/json" \
    -d '{ "messages": [ { "role": "user", "content": "List the top 5 categories by total spend in 2023" } ] }'
  ```

- Expected behavior today
  - The model may:
    - Respond in text directly, or
    - Produce a tool call with `query = "SELECT ... LIMIT 5"`, which gets executed and returned as a Markdown table in the assistant/tool messages.

- Next, I can implement the plan: enrich the prompt + schema RAG, enforce structured SQL output, add SQL validator, and format the final NL response with a safe, limited result table.

- Added a fuller understanding of your repository layout, endpoints, and flow so you can align Doppler and model configuration accordingly.
graph TD
   



FLOW  ------------------------------ FLOW ----------------------------------- FLOW -----------------------


I'll analyze the codebase to understand the logical flow and create a detailed diagram showing how the system processes user requests. Let me start by examining the key files to understand the architecture.
Ran tool
Ran tool
Ran tool
Ran tool
Ran tool
Ran tool
Now let me examine the core components like controllers, middlewares, and thread routes to understand the processing flow:
Ran tool
Ran tool
Ran tool
Ran tool
Ran tool
Let me examine the core components and base classes to complete the picture:
Ran tool
Ran tool
Ran tool
Ran tool
Ran tool
Now let me check the schemas and services to understand the data validation and LLM processing:
Ran tool
Ran tool
Ran tool
Ran tool
Now let me examine some additional components to complete the understanding:
Ran tool
Ran tool
Ran tool
Ran tool
Now I have a comprehensive understanding of the system. Let me create a detailed flow documentation and then the visual diagram.

## Detailed Logical Processing Flow

Based on my analysis of the TextLayer codebase, here's how the system processes user requests:

### System Architecture Overview

The TextLayer API is a Flask-based application that provides a chat interface with LLM integration and text-to-SQL capabilities. The system follows a clean architecture pattern with clear separation of concerns.

### Request Processing Flow

#### 1. **Entry Point** (`application.py`)
- Application starts and loads environment configuration
- Creates Flask app instance using factory pattern
- Sets configuration based on `FLASK_CONFIG` environment variable (DEV/TEST/STAGING/PROD)

#### 2. **Application Initialization** (`app/__init__.py`)
- `create_app()` function initializes the Flask application
- Configures logging based on `LOG_LEVEL` environment variable
- Initializes extensions (CORS, Marshmallow, Mail)
- Registers routes and middleware

#### 3. **Route Registration** (`app/routes/routes.py`)
- `init_routes()` sets up the WSGI middleware with `/v1` base path
- Registers blueprints for different route groups:
  - `/threads` → `thread_routes`
- Configures global middleware:
  - `get_current_user` (auth middleware) - **BEFORE REQUEST**
  - `log_request_info` (logger middleware) - **BEFORE REQUEST**
  - `log_response_info` (logger middleware) - **AFTER REQUEST**

#### 4. **User Request Hits Endpoint** (`POST /v1/threads/chat`)
**File**: `app/routes/thread_routes.py`

```python
@thread_routes.post("/chat")
@handle_exceptions
def chat():
    validated_request_data = chat_messages_schema.load(request.get_json())
    messages = thread_controller.process_chat_message(validated_request_data.get("messages"))
    return Response.make(messages, Response.HTTP_SUCCESS)
```

**Processing Steps:**

##### A. **Middleware Execution (Before Request)**
1. **Authentication Middleware** (`app/middlewares/auth_middleware.py`)
   - `get_current_user()` extracts API key from headers or query params
   - Validates against `current_app.config["API_KEY"]`
   - Supports both `x-api-key` header and `Authorization: Bearer` token

2. **Logging Middleware** (`app/middlewares/logger_middleware.py`)
   - `log_request_info()` logs incoming request headers and JSON body
   - Generates unique request ID for correlation tracking

##### B. **Request Validation** (`app/schemas/thread_schemas.py`)
- `chat_messages_schema.load()` validates incoming JSON
- Schema expects: `{"messages": [{"role": "user|assistant", "content": "..."}]}`
- Uses Marshmallow for validation

##### C. **Exception Handling** (`app/decorators.py`)
- `@handle_exceptions` decorator wraps the endpoint
- Catches and handles various exception types:
  - `ProcessingException` → HTTP 400
  - `ValidationException` → HTTP 400
  - `ValidationError` → HTTP 400
  - General `Exception` → HTTP 500

#### 5. **Controller Layer** (`app/controllers/thread_controller.py`)
```python
def process_chat_message(self, chat_messages: list) -> list:
    return self.executor.execute_write(ProcessChatMessageCommand(chat_messages))
```

- Inherits from base `Controller` class
- Uses singleton `Executor` pattern for command execution
- Delegates to command pattern for business logic

#### 6. **Command Execution** (`app/core/executor.py`)
```python
@staticmethod
def execute_write(command):
    return command.execute()
```

- Singleton pattern ensures single executor instance
- Simple delegation to command's `execute()` method
- Supports both read and write operations

#### 7. **Chat Message Processing** (`app/commands/threads/process_chat_message.py`)

This is the core business logic where the main processing happens:

##### A. **Command Initialization**
```python
def __init__(self, chat_messages: List[Dict[str, str]]) -> None:
    self.chat_messages = chat_messages
    self.llm_session = LLMSession(
        chat_model=current_app.config.get("CHAT_MODEL"),
        embedding_model=current_app.config.get("EMBEDDING_MODEL"),
    )
    self.toolkit = Toolkit()
    self.toolkit.add_tools(*[text_to_sql_tool])
```

##### B. **Validation**
- Checks if `chat_messages` is not empty
- Raises `ValidationException` if validation fails

##### C. **Message Preparation** (`prepare_chat_messages()`)
- **Message History Trimming**: Uses tokenizer to ensure messages fit within model's token limit
- **System Prompt Injection**: Adds system prompt from `chat_prompt()` function
- **Token Management**: Removes oldest messages if total exceeds model's capacity

##### D. **LLM Session Interaction** (`app/services/llm/session.py`)
```python
response = self.llm_session.chat(**chat_kwargs)
```

**LLM Configuration:**
- Supports multiple models: GPT-4o, Claude, O1, etc.
- Token limits vary by model (28K to 200K tokens)
- Uses LiteLLM for model abstraction
- Integrates with Langfuse for observability

**Chat Parameters:**
- `messages`: Prepared and trimmed message history
- `tools`: Available tools (text-to-SQL in this case)
- `model`: Configured chat model
- Guardrails configuration if enabled

##### E. **Tool Execution** (if LLM decides to use tools)
When `finish_reason == "tool_calls"`:

1. **Tool Call Processing**: Extracts tool calls from LLM response
2. **Tool Execution**: Uses Vaul toolkit to execute `text_to_sql_tool`
3. **Database Query**: 
   - `text_to_sql_tool` → `DuckDBDatastore` → SQL execution
   - Returns results as markdown-formatted table

**Text-to-SQL Tool Flow** (`app/services/llm/tools/text_to_sql.py`):
```python
@tool_call
@observe
def text_to_sql(query: str) -> SqlQuery:
    datastore = DuckDBDatastore(database="app/data/data.db")
    result = datastore.execute(query)
    return result.to_markdown(index=False, floatfmt=".2f")
```

##### F. **Response Assembly**
- Creates assistant message with LLM response
- Adds tool execution results as tool messages
- Appends all new messages to conversation history
- Returns complete updated message thread

#### 8. **Response Formation** (`app/utils/response.py`)
```python
return Response.make(messages, Response.HTTP_SUCCESS)
```

**Response Structure:**
```json
{
    "status": 200,
    "payload": [...], // Updated message history
    "correlation_id": "uuid-for-request-tracking"
}
```

#### 9. **Middleware Execution (After Request)**
- `log_response_info()` logs the response data for debugging/monitoring

#### 10. **Response Delivery**
- Flask returns JSON response to client
- HTTP status codes indicate success/failure
- Client receives updated conversation with LLM responses and tool results

### Key Components Summary

| Component | File | Responsibility |
|-----------|------|---------------|
| **Entry Point** | `application.py` | App initialization and configuration |
| **App Factory** | `app/__init__.py` | Flask app creation and setup |
| **Route Setup** | `app/routes/routes.py` | Route registration and middleware |
| **Chat Endpoint** | `app/routes/thread_routes.py` | HTTP endpoint definition |
| **Controller** | `app/controllers/thread_controller.py` | Request orchestration |
| **Executor** | `app/core/executor.py` | Command pattern execution |
| **Business Logic** | `app/commands/threads/process_chat_message.py` | Core chat processing |
| **LLM Integration** | `app/services/llm/session.py` | Model interaction and management |
| **Database Tool** | `app/services/llm/tools/text_to_sql.py` | SQL execution capability |
| **Data Access** | `app/services/datastore/duckdb_datastore.py` | Database operations |
| **Auth Middleware** | `app/middlewares/auth_middleware.py` | Authentication |
| **Log Middleware** | `app/middlewares/logger_middleware.py` | Request/response logging |
| **Exception Handler** | `app/decorators.py` | Error handling |
| **Response Builder** | `app/utils/response.py` | Response formatting |
Ran tool
Now let me create a visual diagram to illustrate this flow:
Ran tool
Ran tool
## Summary

I've created a comprehensive analysis of the TextLayer system's logical processing flow. Here's what I've provided:

### 1. **Detailed Flow Documentation**
The system follows a clean, layered architecture with clear separation of concerns:

- **Entry Layer**: Application initialization and configuration
- **Routing Layer**: HTTP endpoint definitions and middleware
- **Controller Layer**: Request orchestration using command pattern
- **Service Layer**: Business logic, LLM integration, and data access
- **Data Layer**: DuckDB database operations

### 2. **Visual Flow Diagram**
The diagram shows the complete request flow from client to response, including:

- **🔵 Blue**: HTTP endpoints and client interaction
- **🟣 Purple**: Middleware components (auth, logging)
- **🟢 Green**: Controllers and executors
- **🟠 Orange**: Command processing and business logic
- **🟡 Yellow**: LLM and AI services
- **🟢 Light Green**: Database operations
- **🔴 Red**: Error handling paths

### 3. **Key Processing Steps**

When a user calls `POST /v1/threads/chat`:

1. **Request flows through middleware** (auth, logging)
2. **Validation** occurs using Marshmallow schemas
3. **Controller delegates** to command pattern
4. **Chat processing command** handles the core logic:
   - Validates input messages
   - Trims message history for token limits
   - Adds system prompts
   - Calls LLM via LiteLLM
   - Executes tools (text-to-SQL) if needed
   - Queries DuckDB database when required
   - Assembles complete response with conversation history
5. **Response is formatted** and returned to client

### 4. **File-by-File Mapping**
Each component in the diagram includes the specific file path where the logic resides, making it easy to navigate the codebase and understand the implementation details.

This architecture provides excellent separation of concerns, testability, and maintainability while supporting complex AI-powered chat interactions with database querying capabilities.