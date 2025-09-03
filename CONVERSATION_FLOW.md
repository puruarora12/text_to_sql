# Text-to-SQL Conversation Flow Documentation

This document describes the complete flow of how conversations work in the Text-to-SQL AI Chat System, from user input to AI response, including all the decision points and processing steps.

## High-Level Flow Chart

```mermaid
flowchart TD
    A[User Types Message] --> B[Frontend: Send Message]
    B --> C[Backend: Receive Request]
    C --> D[Validate Request]
    D --> E[Process Chat Message]
    E --> F[Extract Latest User Query]
    F --> G[Fetch Context & Schema]
    G --> H[Generate SQL Query]
    H --> I{SQL Generated?}
    I -->|No| J[Return Error]
    I -->|Yes| K[Validate SQL]
    K --> L{Validation Passed?}
    L -->|No| M{Need Clarification?}
    L -->|Yes| N{Requires Human Verification?}
    M -->|Yes| O[Request Clarification]
    M -->|No| P[Regenerate SQL]
    N -->|Yes| Q[Request Human Verification]
    N -->|No| R[Execute SQL]
    O --> S[Return to User]
    P --> H
    Q --> T[User Responds Yes/No]
    T --> U{User Approved?}
    U -->|Yes| R
    U -->|No| V[Cancel Execution]
    R --> W{Execution Successful?}
    W -->|Yes| X[Return Results]
    W -->|No| Y[Analyze Error]
    Y --> Z{Should Regenerate?}
    Z -->|Yes| P
    Z -->|No| AA[Return Error Message]
    X --> BB[Frontend: Display Results]
    V --> CC[Return Cancelled Message]
    AA --> DD[Frontend: Display Error]
    S --> EE[Frontend: Display Clarification Request]
    CC --> FF[Frontend: Display Cancelled]
    DD --> GG[Frontend: Display Error]
    BB --> HH[Conversation Continues]
    EE --> HH
    FF --> HH
    GG --> HH
```

## Combined Detailed Flow Chart

```mermaid
flowchart TD
    %% Step 1: Frontend User Interaction
    A[User Types Message] --> B[Frontend: Validate Input]
    B --> C[Frontend: Send POST Request]
    C --> D[Backend: Receive HTTP Request]
    
    %% Step 2: Backend Request Processing
    D --> E[Middleware: Auth & Logging]
    E --> F[Route Handler: /threads/conversation]
    F --> G[Schema Validation]
    G --> H[Controller: ThreadController.conversation]
    H --> I[Command: ConversationCommand]
    I --> J[Command: ProcessChatMessageCommand]
    
    %% Step 3: AI Pipeline - Initial Processing
    J --> K[Extract Latest User Request]
    K --> L[db_schema_vector_search]
    L --> M[Vector Search for Context]
    M --> N[Get Database Schema]
    N --> O[text_to_sql Tool]
    
    %% Step 4: SQL Generation Process
    O --> P[LLM Session Creation]
    P --> Q[System Message Construction]
    Q --> R[User Message Construction]
    R --> S[LLM API Call]
    S --> T[Extract SQL from Response]
    T --> U{SQL Extracted?}
    U -->|No| V[Return Error]
    U -->|Yes| W{Is VAGUE_QUERY?}
    W -->|Yes| X[Enhanced Context Usage]
    X --> Y[Second LLM Attempt]
    Y --> Z[Extract SQL from Enhanced Response]
    Z --> AA{Still VAGUE_QUERY?}
    AA -->|Yes| BB[Return VAGUE_QUERY]
    AA -->|No| CC[Return Generated SQL]
    W -->|No| CC
    
    %% Step 5: Validation Orchestration
    CC --> DD[validation_orchestrator]
    DD --> EE[Analyze Query Complexity]
    EE --> FF{Complexity Level}
    FF -->|Simple| GG[Minimal Validation]
    FF -->|Medium| HH[Sequential Validation]
    FF -->|Complex| II[Parallel Validation]
    GG --> JJ[Basic Schema + Security Check]
    HH --> KK[Schema + Security + Query + Guardrail]
    II --> LL[Parallel Execution of All Validations]
    JJ --> MM[Return Validation Result]
    KK --> MM
    LL --> MM
    MM --> NN{Validation Passed?}
    NN -->|No| OO{Need Clarification?}
    NN -->|Yes| PP{sql_guardrail Decision}
    
    %% Step 6: Human Verification Flow
    PP -->|Accept| QQ[Execute SQL]
    PP -->|Human Verification| RR[Request User Approval]
    PP -->|Reject| SS[Return Rejection]
    RR --> TT[Frontend: Display SQL + Buttons]
    TT --> UU[User Responds Yes/No]
    UU --> VV{User Approved?}
    VV -->|Yes| QQ
    VV -->|No| WW[Return Cancelled]
    
    %% Step 7: SQL Execution and Regeneration
    QQ --> XX{Execution Successful?}
    XX -->|Yes| YY[Return Results]
    XX -->|No| ZZ[sql_execution_analyzer]
    ZZ --> AAA[Analyze Error Type]
    AAA --> BBB{Error Type}
    BBB -->|SQL Structure| CCC[Should Regenerate = True]
    BBB -->|Data Issue| DDD[Should Regenerate = False]
    BBB -->|Permission Issue| EEE[Should Regenerate = False]
    CCC --> FFF[sql_regeneration_tool]
    FFF --> GGG[Extract Error Feedback]
    GGG --> HHH[Add Regeneration Context]
    HHH --> III[Call text_to_sql with Feedback]
    III --> JJJ[Generate New SQL]
    JJJ --> KKK{New SQL Generated?}
    KKK -->|Yes| LL[Validate New SQL]
    KKK -->|No| MMM[Return Regeneration Failed]
    LL --> NN{Validation Passed?}
    NN -->|Yes| QQ
    NN -->|No| NNN[Return Validation Failed]
    DDD --> OOO[Return User-Friendly Error]
    EEE --> PPP[Return Permission Error]
    
    %% Step 8: Frontend Response Handling
    YY --> QQQ[Backend: Return Success Response]
    SS --> RRR[Backend: Return Rejection Response]
    WW --> SSS[Backend: Return Cancelled Response]
    OOO --> TTT[Backend: Return Error Response]
    PPP --> UUU[Backend: Return Error Response]
    MMM --> VVV[Backend: Return Error Response]
    NNN --> WWW[Backend: Return Error Response]
    
    QQQ --> XXX[Frontend: Receive API Response]
    RRR --> XXX
    SSS --> XXX
    TTT --> XXX
    UUU --> XXX
    VVV --> XXX
    WWW --> XXX
    
    XXX --> YYY[Parse Response Payload]
    YYY --> ZZZ{Response Type}
    ZZZ -->|Success| AAAA[Display SQL + Results]
    ZZZ -->|Human Verification| BBBB[Display SQL + Buttons]
    ZZZ -->|Clarification| CCCC[Display Clarification Request]
    ZZZ -->|Regeneration Request| DDDD[Display Regeneration Message]
    ZZZ -->|Error| EEEE[Display Error Message]
    
    AAAA --> FFFF[Format Results]
    FFFF --> GGGG[Add to Chat History]
    GGGG --> HHHH[Update UI]
    
    BBBB --> IIII[Show Yes/No Buttons]
    IIII --> JJJJ[Wait for User Input]
    JJJJ --> UU
    
    CCCC --> KKKK[Show Clarification Text]
    KKKK --> LLLL[Wait for User Input]
    LLLL --> MMMM[Handle User Response]
    MMMM --> NNNN[Send Response to Backend]
    
    DDDD --> OOOO[Show Regeneration Progress]
    OOOO --> PPPP[Auto-trigger Regeneration]
    PPPP --> QQQQ[Handle Regeneration]
    QQQQ --> NNNN
    
    EEEE --> RRRR[Show Error Details]
    RRRR --> SSSS[Update UI]
    
    HHHH --> TTTT[Conversation Continues]
    SSSS --> TTTT
    
    %% Clarification and Regeneration Loops
    OO -->|Yes| CCCC
    OO -->|No| FFF
    
    %% Error Handling
    V --> UUUU[Frontend: Display Error]
    UUUU --> TTTT
```

## Detailed Flow Breakdown

### 1. Frontend User Interaction

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend (React)
    participant B as Backend (Flask)
    participant AI as AI Pipeline
    participant DB as Database

    U->>F: Type message in chat input
    F->>F: Validate input (not empty, session exists)
    F->>B: POST /v1/threads/conversation
    Note over F,B: {session_id, messages: [{role: "user", content: "query"}]}
    B->>B: Validate request schema
    B->>AI: Process chat message
    AI->>AI: Extract latest user query
    AI->>AI: Fetch context & schema
    AI->>AI: Generate SQL
    AI->>AI: Validate SQL
    AI->>B: Return response
    B->>F: Return structured response
    F->>F: Parse response
    F->>U: Display formatted response
```

### 2. Backend Request Processing

```mermaid
flowchart TD
    A[HTTP Request] --> B[Middleware: Auth & Logging]
    B --> C[Route Handler: /threads/conversation]
    C --> D[Schema Validation]
    D --> E[Controller: ThreadController.conversation]
    E --> F[Command: ConversationCommand]
    F --> G[Command: ProcessChatMessageCommand]
    G --> H[AI Pipeline Execution]
    H --> I[Response Formatting]
    I --> J[Return JSON Response]
```

### 3. AI Pipeline Detailed Flow

```mermaid
flowchart TD
    A[ProcessChatMessageCommand] --> B[Extract Latest User Request]
    B --> C[db_schema_vector_search]
    C --> D[Vector Search for Context]
    D --> E[Get Database Schema]
    E --> F[text_to_sql Tool]
    F --> G[Generate Initial SQL]
    G --> H{SQL Generated?}
    H -->|No| I[Return Error]
    H -->|Yes| J{Query Too Vague?}
    J -->|Yes| K[Request Clarification]
    J -->|No| L[validation_orchestrator]
    L --> M[Analyze Query Complexity]
    M --> N[Execute Validation Strategy]
    N --> O{Validation Passed?}
    O -->|No| P{Need Clarification?}
    O -->|Yes| Q{sql_guardrail Decision}
    P -->|Yes| K
    P -->|No| R[sql_regeneration_tool]
    Q -->|Accept| S[Execute SQL]
    Q -->|Human Verification| T[Request User Approval]
    Q -->|Reject| U[Return Rejection]
    R --> F
    S --> V{Execution Successful?}
    V -->|Yes| W[Return Results]
    V -->|No| X[sql_execution_analyzer]
    X --> Y{Should Regenerate?}
    Y -->|Yes| R
    Y -->|No| Z[Return Error Message]
    T --> AA[User Responds]
    AA --> BB{User Approved?}
    BB -->|Yes| S
    BB -->|No| CC[Return Cancelled]
    K --> DD[Return Clarification Request]
    U --> EE[Return Rejection Message]
    W --> FF[Return Success Response]
    Z --> GG[Return Error Response]
    CC --> HH[Return Cancelled Response]
    DD --> II[Return Clarification Response]
    EE --> JJ[Return Rejection Response]
```

### 4. SQL Generation Process

```mermaid
flowchart TD
    A[text_to_sql Tool] --> B[Input: Natural Language Query]
    B --> C[Input: Context Text]
    C --> D[Input: Schema Text]
    D --> E[Input: User Type]
    E --> F[LLM Session Creation]
    F --> G[System Message Construction]
    G --> H[User Message Construction]
    H --> I[LLM API Call]
    I --> J[Extract SQL from Response]
    J --> K{SQL Extracted?}
    K -->|No| L[Return Error]
    K -->|Yes| M{Is VAGUE_QUERY?}
    M -->|Yes| N[Enhanced Context Usage]
    N --> O[Second LLM Attempt]
    O --> P[Extract SQL from Enhanced Response]
    P --> Q{Still VAGUE_QUERY?}
    Q -->|Yes| R[Return VAGUE_QUERY]
    Q -->|No| S[Return Generated SQL]
    M -->|No| S
    S --> T[Return SQL for Validation]
```

### 5. Validation Orchestration

```mermaid
flowchart TD
    A[validation_orchestrator] --> B[Analyze Query Complexity]
    B --> C{Complexity Level}
    C -->|Simple| D[Minimal Validation]
    C -->|Medium| E[Sequential Validation]
    C -->|Complex| F[Parallel Validation]
    D --> G[Basic Schema Check]
    G --> H[Basic Security Check]
    H --> I[Return Validation Result]
    E --> J[Schema Validation]
    J --> K[Security Validation]
    K --> L[Query Validation]
    L --> M[Guardrail Check]
    M --> I
    F --> N[Parallel Execution]
    N --> O[Schema + Security + Query + Guardrail]
    O --> P[Aggregate Results]
    P --> I
    I --> Q{Validation Passed?}
    Q -->|Yes| R[Proceed to Execution]
    Q -->|No| S[Return Validation Errors]
```

### 6. Human Verification Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant B as Backend
    participant AI as AI Pipeline

    AI->>B: SQL requires human verification
    B->>F: Return verification request
    F->>U: Display SQL + Yes/No buttons
    U->>F: Click "Yes" or "No"
    F->>B: Send user response
    B->>AI: Process verification response
    AI->>AI: Check user decision
    alt User approved
        AI->>AI: Execute SQL
        AI->>B: Return execution results
        B->>F: Return success response
        F->>U: Display results
    else User rejected
        AI->>B: Return cancelled response
        B->>F: Return cancelled message
        F->>U: Display cancelled message
    end
```

### 7. SQL Regeneration Flow

```mermaid
flowchart TD
    A[SQL Execution Failed] --> B[sql_execution_analyzer]
    B --> C[Analyze Error Type]
    C --> D{Error Type}
    D -->|SQL Structure| E[Should Regenerate = True]
    D -->|Data Issue| F[Should Regenerate = False]
    D -->|Permission Issue| G[Should Regenerate = False]
    E --> H[sql_regeneration_tool]
    H --> I[Extract Error Feedback]
    I --> J[Add Regeneration Context]
    J --> K[Call text_to_sql with Feedback]
    K --> L[Generate New SQL]
    L --> M{New SQL Generated?}
    M -->|Yes| N[Validate New SQL]
    M -->|No| O[Return Regeneration Failed]
    N --> P{Validation Passed?}
    P -->|Yes| Q[Execute New SQL]
    P -->|No| R[Return Validation Failed]
    Q --> S{Execution Successful?}
    S -->|Yes| T[Return Success]
    S -->|No| U[Return Execution Failed]
    F --> V[Return User-Friendly Error]
    G --> W[Return Permission Error]
    O --> X[Return Regeneration Error]
    R --> Y[Return Validation Error]
    U --> Z[Return Execution Error]
    T --> AA[Return Success Response]
    V --> BB[Return Error Response]
    W --> CC[Return Error Response]
    X --> DD[Return Error Response]
    Y --> EE[Return Error Response]
    Z --> FF[Return Error Response]
```

### 8. Frontend Response Handling

```mermaid
flowchart TD
    A[Receive API Response] --> B[Parse Response Payload]
    B --> C{Response Type}
    C -->|Success| D[Display SQL + Results]
    C -->|Human Verification| E[Display SQL + Buttons]
    C -->|Clarification| F[Display Clarification Request]
    C -->|Regeneration Request| G[Display Regeneration Message]
    C -->|Error| H[Display Error Message]
    D --> I[Format Results]
    I --> J[Add to Chat History]
    E --> K[Show Yes/No Buttons]
    K --> L[Wait for User Input]
    F --> M[Show Clarification Text]
    M --> N[Wait for User Input]
    G --> O[Show Regeneration Progress]
    O --> P[Auto-trigger Regeneration]
    H --> Q[Show Error Details]
    J --> R[Update UI]
    L --> S[Handle User Response]
    N --> T[Handle User Response]
    P --> U[Handle Regeneration]
    Q --> V[Update UI]
    S --> W[Send Response to Backend]
    T --> W
    U --> W
    W --> X[Process New Response]
    X --> B
```

## Key Decision Points

### 1. SQL Generation Decisions
- **Vague Query Detection**: If the query lacks sufficient detail
- **Context Usage**: How aggressively to use available context
- **Schema Matching**: How to match user intent to database schema

### 2. Validation Decisions
- **Complexity Analysis**: Determines validation strategy
- **Security Assessment**: Checks for SQL injection and dangerous operations
- **Schema Compliance**: Validates against actual database schema
- **Permission Check**: Verifies user has appropriate permissions

### 3. Execution Decisions
- **Human Verification**: Required for destructive operations
- **Auto-execution**: Safe queries execute automatically
- **Error Handling**: How to respond to execution failures

### 4. Regeneration Decisions
- **Error Analysis**: Determines if regeneration is appropriate
- **Feedback Integration**: How to use error information
- **Retry Limits**: Prevents infinite regeneration loops

## Error Handling Flow

```mermaid
flowchart TD
    A[Error Occurs] --> B[Error Classification]
    B --> C{Error Type}
    C -->|Validation Error| D[Return Validation Feedback]
    C -->|Execution Error| E[Analyze Execution Error]
    C -->|API Error| F[Return API Error]
    C -->|System Error| G[Return System Error]
    E --> H{Should Regenerate?}
    H -->|Yes| I[Trigger Regeneration]
    H -->|No| J[Return User-Friendly Error]
    I --> K[Regeneration Process]
    K --> L{Regeneration Successful?}
    L -->|Yes| M[Return New Results]
    L -->|No| N[Return Regeneration Failed]
    D --> O[Frontend: Display Error]
    F --> O
    G --> O
    J --> O
    M --> P[Frontend: Display Results]
    N --> Q[Frontend: Display Error]
```

## Performance Considerations

### 1. Parallel Processing
- **Validation Orchestration**: Complex queries use parallel validation
- **Vector Search**: Concurrent context retrieval
- **Database Operations**: Async execution where possible

### 2. Caching Strategy
- **Schema Caching**: Database schema cached for performance
- **Context Caching**: Vector search results cached
- **Session State**: Conversation context maintained

### 3. Rate Limiting
- **API Calls**: OpenAI API rate limiting
- **Database Queries**: Query execution limits
- **User Sessions**: Session-based rate limiting

## Security Considerations

### 1. Input Validation
- **SQL Injection Prevention**: Multiple validation layers
- **Schema Validation**: Ensures queries match actual schema
- **Permission Checks**: User type-based access control

### 2. Output Sanitization
- **Result Filtering**: Sensitive data filtering
- **Error Message Sanitization**: Prevents information leakage
- **Response Validation**: Ensures safe response format

### 3. Access Control
- **User Type Validation**: Admin vs User permissions
- **Session Management**: Secure session handling
- **API Authentication**: Request authentication middleware

## Monitoring and Observability

### 1. Langfuse Integration
- **Trace Logging**: Complete conversation traces
- **Performance Metrics**: Response time tracking
- **Error Tracking**: Detailed error logging

### 2. Application Logging
- **Request Logging**: All API requests logged
- **Error Logging**: Detailed error information
- **Performance Logging**: Response time metrics

### 3. Metrics Collection
- **Validation Metrics**: Success/failure rates
- **Execution Metrics**: Query performance
- **User Metrics**: Session and usage statistics

---

This flow documentation provides a comprehensive view of how the Text-to-SQL conversation system works, from initial user input through all the AI processing steps to final response delivery. Understanding this flow is essential for debugging, optimization, and extending the system.
