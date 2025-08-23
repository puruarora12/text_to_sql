from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum


class UserType(str, Enum):
    """User type enumeration for permission levels."""
    USER = "user"
    ADMIN = "admin"


class QueryType(str, Enum):
    """Query type enumeration."""
    READ = "read"
    UPDATE = "update"
    INSERT = "insert"
    DELETE = "delete"
    UNKNOWN = "unknown"


class ValidationStrategy(str, Enum):
    """Validation strategy enumeration."""
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    MINIMAL = "minimal"


class QueryComplexity(str, Enum):
    """Query complexity enumeration."""
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ValidationStatus(str, Enum):
    """Validation status enumeration."""
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING = "pending"


class DecisionType(str, Enum):
    """Decision type enumeration."""
    ACCEPT = "accept"
    REJECT = "reject"
    HUMAN_VERIFICATION = "human_verification"
    EXECUTED_AFTER_VERIFICATION = "executed_after_verification"
    CANCELLED_BY_USER = "cancelled_by_user"
    EXECUTION_FAILED = "execution_failed"


# ============================================================================
# Database Schema Vector Search Tool Schemas
# ============================================================================

@dataclass
class DBSchemaVectorSearchInput:
    """Input schema for db_schema_vector_search tool."""
    natural_language_query: str
    n_results: int = 3


@dataclass
class DBSchemaVectorSearchOutput:
    """Output schema for db_schema_vector_search tool."""
    context_text: str
    schema_text: str


# ============================================================================
# Text-to-SQL Tool Schemas
# ============================================================================

@dataclass
class TextToSQLInput:
    """Input schema for text_to_sql tool."""
    natural_language_query: str
    context_text: str = ""
    schema_text: str = ""
    user_type: UserType = UserType.USER
    previous_chat: str = ""


@dataclass
class SQLExecutionResult:
    """Schema for SQL execution results."""
    row_count: int
    rows: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SQLExecutionInput:
    """Input schema for sql_execution_handler tool."""
    sql_query: str
    user_response: str
    original_feedback: str = ""


@dataclass
class SQLExecutionOutput:
    """Output schema for sql_execution_handler tool."""
    query: str
    decision: DecisionType
    feedback: str
    row_count: Optional[int] = None
    rows: Optional[List[Dict[str, Any]]] = None
    user_response: str = ""


@dataclass
class TextToSQLOutput:
    """Output schema for text_to_sql tool."""
    query: str
    decision: DecisionType
    feedback: str
    row_count: Optional[int] = None
    rows: Optional[List[Dict[str, Any]]] = None
    validation_time: Optional[float] = None
    validation_strategy: Optional[ValidationStrategy] = None
    type: Optional[str] = None  # For human verification payloads
    requires_clarification: Optional[bool] = None
    original_query: Optional[str] = None
    sql: Optional[str] = None  # For human verification payloads


# ============================================================================
# Validation Orchestrator Tool Schemas
# ============================================================================

@dataclass
class ValidationOrchestratorInput:
    """Input schema for validation_orchestrator tool."""
    user_query: str
    generated_sql: str
    db_schema: str
    context_data: str
    user_type: UserType = UserType.USER


@dataclass
class ComplexityAnalysis:
    """Schema for query complexity analysis."""
    complexity: QueryComplexity
    complexity_score: int
    complexity_factors: List[str] = field(default_factory=list)
    strategy: ValidationStrategy = ValidationStrategy.SEQUENTIAL


@dataclass
class ValidationTaskResult:
    """Schema for individual validation task results."""
    result: Optional[Dict[str, Any]] = None
    parallel: bool = False
    status: ValidationStatus = ValidationStatus.PENDING
    error: Optional[str] = None


@dataclass
class PerformanceMetrics:
    """Schema for performance metrics."""
    total_time: float
    steps_completed: int
    parallel_steps: int


@dataclass
class ValidationOrchestratorOutput:
    """Output schema for validation_orchestrator tool."""
    is_valid: bool
    validation_results: Dict[str, ValidationTaskResult]
    total_validation_time: float
    validation_steps: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    query_complexity: QueryComplexity = QueryComplexity.UNKNOWN
    validation_strategy: ValidationStrategy = ValidationStrategy.SEQUENTIAL
    performance_metrics: PerformanceMetrics = field(default_factory=lambda: PerformanceMetrics(0.0, 0, 0))


# ============================================================================
# Individual Validation Tool Schemas
# ============================================================================

@dataclass
class StrictSchemaValidatorInput:
    """Input schema for strict_schema_validator tool."""
    generated_sql: str
    db_schema: str
    user_query: str


@dataclass
class StrictSchemaValidatorOutput:
    """Output schema for strict_schema_validator tool."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class SQLInjectionDetectorInput:
    """Input schema for sql_injection_detector tool."""
    generated_sql: str
    user_type: UserType = UserType.USER


@dataclass
class SQLInjectionDetectorOutput:
    """Output schema for sql_injection_detector tool."""
    is_injection: bool
    confidence: str = "unknown"
    reason: Optional[str] = None
    detected_patterns: List[str] = field(default_factory=list)


@dataclass
class SQLQueryValidatorInput:
    """Input schema for sql_query_validator tool."""
    user_query: str
    db_schema: str
    context_data: str
    generated_sql: str


@dataclass
class SQLQueryValidatorOutput:
    """Output schema for sql_query_validator tool."""
    is_correct: bool
    explanation: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)
    confidence_score: Optional[float] = None


@dataclass
class SQLGuardrailInput:
    """Input schema for sql_guardrail tool."""
    generated_sql: str
    user_type: UserType = UserType.USER


@dataclass
class SQLGuardrailOutput:
    """Output schema for sql_guardrail tool."""
    decision: DecisionType
    feedback: str
    risk_level: Optional[str] = None
    allowed_operations: List[str] = field(default_factory=list)
    blocked_operations: List[str] = field(default_factory=list)


@dataclass
class HumanQueryClarificationInput:
    """Input schema for human_query_clarification tool."""
    user_query: str
    db_schema: str
    context_data: str
    failed_sql: str
    validation_feedback: str
    attempts: int = 1


@dataclass
class HumanQueryClarificationOutput:
    """Output schema for human_query_clarification tool."""
    type: str = "human_verification"
    requires_clarification: bool = True
    original_query: str = ""
    sql: str = ""
    feedback: str = ""
    clarification_questions: List[str] = field(default_factory=list)


# ============================================================================
# SQL Execution Analysis Tool Schemas
# ============================================================================

@dataclass
class SQLExecutionAnalyzerInput:
    """Input schema for sql_execution_analyzer tool."""
    sql_query: str
    error_message: str
    user_query: str
    db_schema: str = ""


@dataclass
class SQLExecutionAnalyzerOutput:
    """Output schema for sql_execution_analyzer tool."""
    failure_type: str  # "sql_structure", "valid_execution", "unknown"
    should_regenerate: bool
    regeneration_feedback: str
    user_friendly_message: str
    technical_details: str
    suggested_fixes: List[str] = field(default_factory=list)


# SQL Regeneration Tool Schemas
@dataclass
class SQLRegenerationInput:
    """Input schema for sql_regeneration_tool."""
    original_query: str
    failed_sql: str
    failure_reason: str
    context_text: str = ""
    schema_text: str = ""
    user_type: str = "user"
    previous_chat: str = ""
    failure_type: str = "validation"  # "validation" or "execution"


@dataclass
class SQLRegenerationOutput:
    """Output schema for sql_regeneration_tool."""
    original_query: str
    failed_sql: str
    regenerated_sql: str
    decision: DecisionType
    feedback: str
    row_count: int = 0
    rows: List[Dict[str, Any]] = field(default_factory=list)
    validation_time: float = 0.0
    validation_strategy: ValidationStrategy = ValidationStrategy.SEQUENTIAL


# ============================================================================
# Conversation Command Schemas
# ============================================================================

@dataclass
class ConversationMessage:
    """Schema for conversation messages."""
    role: str
    content: str
    timestamp: Optional[str] = None


@dataclass
class ConversationCommandInput:
    """Input schema for ConversationCommand."""
    session_id: str
    incoming_messages: List[ConversationMessage] = field(default_factory=list)


@dataclass
class ConversationCommandOutput:
    """Output schema for ConversationCommand."""
    sql: Optional[str] = None
    decision: Optional[DecisionType] = None
    feedback: Optional[str] = None
    row_count: Optional[int] = None
    rows: Optional[List[Dict[str, Any]]] = None
    type: Optional[str] = None
    requires_clarification: Optional[bool] = None
    original_query: Optional[str] = None


# ============================================================================
# Utility Functions for Schema Conversion
# ============================================================================

def dict_to_text_to_sql_input(data: Dict[str, Any]) -> TextToSQLInput:
    """Convert dictionary to TextToSQLInput."""
    return TextToSQLInput(
        natural_language_query=data.get("natural_language_query", ""),
        context_text=data.get("context_text", ""),
        schema_text=data.get("schema_text", ""),
        user_type=UserType(data.get("user_type", "user")),
        previous_chat=data.get("previous_chat", "")
    )


def dict_to_sql_execution_input(data: Dict[str, Any]) -> SQLExecutionInput:
    """Convert dictionary to SQLExecutionInput."""
    return SQLExecutionInput(
        sql_query=data.get("sql_query", ""),
        user_response=data.get("user_response", ""),
        original_feedback=data.get("original_feedback", "")
    )


def sql_execution_output_to_dict(output: SQLExecutionOutput) -> Dict[str, Any]:
    """Convert SQLExecutionOutput to dictionary."""
    result = {
        "query": output.query,
        "decision": output.decision.value if isinstance(output.decision, DecisionType) else output.decision,
        "feedback": output.feedback,
        "user_response": output.user_response
    }
    
    if output.row_count is not None:
        result["row_count"] = output.row_count
    if output.rows is not None:
        result["rows"] = output.rows
    
    return result


def text_to_sql_output_to_dict(output: TextToSQLOutput) -> Dict[str, Any]:
    """Convert TextToSQLOutput to dictionary."""
    result = {
        "query": output.query,
        "decision": output.decision.value if isinstance(output.decision, DecisionType) else output.decision,
        "feedback": output.feedback
    }
    
    if output.row_count is not None:
        result["row_count"] = output.row_count
    if output.rows is not None:
        result["rows"] = output.rows
    
    return result


def dict_to_sql_regeneration_input(data: Dict[str, Any]) -> SQLRegenerationInput:
    """Convert dictionary to SQLRegenerationInput."""
    return SQLRegenerationInput(**data)


def sql_regeneration_output_to_dict(output: SQLRegenerationOutput) -> Dict[str, Any]:
    """Convert SQLRegenerationOutput to dictionary."""
    return {
        "original_query": output.original_query,
        "failed_sql": output.failed_sql,
        "regenerated_sql": output.regenerated_sql,
        "decision": output.decision.value,
        "feedback": output.feedback,
        "row_count": output.row_count,
        "rows": output.rows,
        "validation_time": output.validation_time,
        "validation_strategy": output.validation_strategy.value
    }
    if output.validation_time is not None:
        result["validation_time"] = output.validation_time
    if output.validation_strategy is not None:
        result["validation_strategy"] = output.validation_strategy.value
    if output.type is not None:
        result["type"] = output.type
    if output.requires_clarification is not None:
        result["requires_clarification"] = output.requires_clarification
    if output.original_query is not None:
        result["original_query"] = output.original_query
    if output.sql is not None:
        result["sql"] = output.sql
    
    return result


def dict_to_validation_orchestrator_input(data: Dict[str, Any]) -> ValidationOrchestratorInput:
    """Convert dictionary to ValidationOrchestratorInput."""
    return ValidationOrchestratorInput(
        user_query=data.get("user_query", ""),
        generated_sql=data.get("generated_sql", ""),
        db_schema=data.get("db_schema", ""),
        context_data=data.get("context_data", ""),
        user_type=UserType(data.get("user_type", "user"))
    )


def validation_orchestrator_output_to_dict(output: ValidationOrchestratorOutput) -> Dict[str, Any]:
    """Convert ValidationOrchestratorOutput to dictionary."""
    return {
        "is_valid": output.is_valid,
        "validation_results": {
            k: {
                "result": v.result,
                "parallel": v.parallel,
                "status": v.status.value,
                "error": v.error
            } for k, v in output.validation_results.items()
        },
        "total_validation_time": output.total_validation_time,
        "validation_steps": output.validation_steps,
        "errors": output.errors,
        "warnings": output.warnings,
        "recommendations": output.recommendations,
        "query_complexity": output.query_complexity.value,
        "validation_strategy": output.validation_strategy.value,
        "performance_metrics": {
            "total_time": output.performance_metrics.total_time,
            "steps_completed": output.performance_metrics.steps_completed,
            "parallel_steps": output.performance_metrics.parallel_steps
        }
    }
