from langfuse.decorators import observe
from vaul import tool_call
from typing import Dict, Any, List, Optional
import time
from concurrent.futures import ThreadPoolExecutor
import threading

from app import logger
from app.services.llm.tools.strict_schema_validator import strict_schema_validator
from app.services.llm.tools.sql_injection_detector import sql_injection_detector
from app.services.llm.tools.sql_query_validator import sql_query_validator
from app.services.llm.tools.sql_guardrail import sql_guardrail
from app.schemas.tool_schemas import (
    ValidationOrchestratorInput, ValidationOrchestratorOutput, ValidationTaskResult,
    ComplexityAnalysis, PerformanceMetrics, QueryComplexity, ValidationStrategy, ValidationStatus,
    dict_to_validation_orchestrator_input, validation_orchestrator_output_to_dict
)
from flask import current_app


@tool_call
@observe
def validation_orchestrator(
    user_query: str,
    generated_sql: str,
    db_schema: str,
    context_data: str,
    user_type: str = "user"
) -> Dict[str, Any]:
    """
    Orchestrate the validation chain with intelligent routing and parallel processing.
    
    Args:
        user_query: The original natural language query
        generated_sql: The SQL query to validate
        db_schema: Database schema information
        context_data: Context data from RAG
        user_type: User type (user/admin) for permission checks
        
    Returns:
        {
            "is_valid": bool,
            "validation_results": Dict[str, Any],
            "total_validation_time": float,
            "validation_steps": List[str],
            "errors": List[str],
            "warnings": List[str],
            "recommendations": List[str]
        }
    """
    # Convert input to structured format
    input_data = ValidationOrchestratorInput(
        user_query=user_query,
        generated_sql=generated_sql,
        db_schema=db_schema,
        context_data=context_data,
        user_type=user_type
    )
    
    start_time = time.time()
    validation_results = {}
    errors = []
    warnings = []
    recommendations = []
    validation_steps = []
    
    try:
        # Step 1: Analyze query complexity to determine validation strategy
        complexity_analysis = _analyze_query_complexity(input_data.user_query, input_data.generated_sql)
        query_complexity = complexity_analysis["complexity"]
        validation_strategy = complexity_analysis["strategy"]
        
        logger.info(f"Validation orchestrator: Query complexity: {query_complexity}, Strategy: {validation_strategy}")
        
        # Step 2: Execute validation based on strategy
        if validation_strategy == "parallel":
            validation_results = _execute_parallel_validation(
                input_data.user_query, input_data.generated_sql, input_data.db_schema, input_data.context_data, input_data.user_type
            )
        elif validation_strategy == "sequential":
            validation_results = _execute_sequential_validation(
                input_data.user_query, input_data.generated_sql, input_data.db_schema, input_data.context_data, input_data.user_type
            )
        elif validation_strategy == "minimal":
            validation_results = _execute_minimal_validation(
                input_data.user_query, input_data.generated_sql, input_data.db_schema, input_data.context_data, input_data.user_type
            )
        else:
            # Default to sequential for unknown strategies
            validation_results = _execute_sequential_validation(
                input_data.user_query, input_data.generated_sql, input_data.db_schema, input_data.context_data, input_data.user_type
            )
        
        # Step 3: Analyze validation results
        analysis_result = _analyze_validation_results(validation_results)
        
        # Step 4: Generate final response
        total_time = time.time() - start_time
        
        # Convert validation results to structured format
        structured_validation_results = {}
        for key, value in validation_results.items():
            structured_validation_results[key] = ValidationTaskResult(
                result=value.get("result"),
                parallel=value.get("parallel", False),
                status=ValidationStatus(value.get("status", "pending")),
                error=value.get("error")
            )
        
        output = ValidationOrchestratorOutput(
            is_valid=analysis_result["is_valid"],
            validation_results=structured_validation_results,
            total_validation_time=total_time,
            validation_steps=validation_steps,
            errors=analysis_result["errors"],
            warnings=analysis_result["warnings"],
            recommendations=analysis_result["recommendations"],
            query_complexity=QueryComplexity(query_complexity),
            validation_strategy=ValidationStrategy(validation_strategy),
            performance_metrics=PerformanceMetrics(
                total_time=total_time,
                steps_completed=len(validation_results),
                parallel_steps=len([r for r in validation_results.values() if r.get("parallel", False)])
            )
        )
        
        return validation_orchestrator_output_to_dict(output)
        
    except Exception as e:
        logger.error(f"Error in validation orchestrator: {e}")
        total_time = time.time() - start_time
        
        output = ValidationOrchestratorOutput(
            is_valid=False,
            validation_results=validation_results,
            total_validation_time=total_time,
            validation_steps=validation_steps,
            errors=[f"Validation orchestrator error: {str(e)}"],
            warnings=warnings,
            recommendations=["Check system configuration and try again"],
            query_complexity=QueryComplexity.UNKNOWN,
            validation_strategy=ValidationStrategy.SEQUENTIAL,
            performance_metrics=PerformanceMetrics(
                total_time=total_time,
                steps_completed=len(validation_results),
                parallel_steps=0
            )
        )
        
        return validation_orchestrator_output_to_dict(output)


def _analyze_query_complexity(user_query: str, generated_sql: str) -> Dict[str, Any]:
    """
    Analyze query complexity to determine optimal validation strategy.
    """
    complexity_score = 0
    complexity_factors = []
    
    # Factor 1: SQL complexity
    sql_lower = generated_sql.lower()
    if "join" in sql_lower:
        complexity_score += 2
        complexity_factors.append("JOIN operations")
    
    # More precise subquery detection - look for SELECT within parentheses
    if "(" in sql_lower and "select" in sql_lower:
        # Check if it's actually a subquery pattern
        import re
        subquery_patterns = [
            r"\(.*\bselect\b.*\)",  # SELECT within parentheses
            r"\bwhere\b.*\b\(.*\bselect\b",  # WHERE with subquery
            r"\bfrom\b.*\b\(.*\bselect\b",   # FROM with subquery
            r"\bin\b.*\b\(.*\bselect\b"      # IN with subquery
        ]
        if any(re.search(pattern, sql_lower, re.IGNORECASE) for pattern in subquery_patterns):
            complexity_score += 2
            complexity_factors.append("Subqueries")
    
    if "union" in sql_lower or "intersect" in sql_lower:
        complexity_score += 3
        complexity_factors.append("Set operations")
    
    if "group by" in sql_lower or "having" in sql_lower:
        complexity_score += 1
        complexity_factors.append("Aggregations")
    
    if "order by" in sql_lower:
        complexity_score += 1
        complexity_factors.append("Sorting")
    
    # Factor 2: Query length and structure
    sql_words = len(generated_sql.split())
    if sql_words > 50:
        complexity_score += 2
        complexity_factors.append("Long query")
    elif sql_words > 20:
        complexity_score += 1
        complexity_factors.append("Medium query")
    
    # Factor 3: User query complexity
    user_words = len(user_query.split())
    if user_words > 20:
        complexity_score += 1
        complexity_factors.append("Complex user request")
    
    # Factor 4: Operation type
    if sql_lower.startswith("update") or sql_lower.startswith("delete"):
        complexity_score += 2
        complexity_factors.append("Modification operation")
    elif sql_lower.startswith("insert"):
        complexity_score += 1
        complexity_factors.append("Insert operation")
    
    # Determine complexity level and strategy
    if complexity_score >= 6:
        complexity_level = "high"
        strategy = "parallel"  # Use parallel validation for complex queries
    elif complexity_score >= 3:
        complexity_level = "medium"
        strategy = "sequential"  # Use sequential validation for medium complexity
    else:
        complexity_level = "low"
        strategy = "minimal"  # Use minimal validation for simple queries
    
    return {
        "complexity": complexity_level,
        "complexity_score": complexity_score,
        "complexity_factors": complexity_factors,
        "strategy": strategy
    }


def _execute_validation_task(task_name: str, task_func, parallel: bool = False) -> Dict[str, Any]:
    """
    Execute a single validation task with error handling.
    """
    try:
        result = task_func()
        return {
            "result": result,
            "parallel": parallel,
            "status": "completed"
        }
    except Exception as e:
        logger.error(f"Validation {task_name} failed: {e}")
        return {
            "result": None,
            "parallel": parallel,
            "status": "failed",
            "error": str(e)
        }


def _execute_parallel_validation(
    user_query: str,
    generated_sql: str,
    db_schema: str,
    context_data: str,
    user_type: str
) -> Dict[str, Any]:
    """
    Execute validations in parallel for complex queries.
    """
    validation_results = {}
    
    # Define validation tasks that can run in parallel
    validation_tasks = [
        ("schema_validation", lambda: strict_schema_validator(generated_sql, db_schema, user_query)),
        ("injection_detection", lambda: sql_injection_detector(generated_sql)),
        ("query_validation", lambda: sql_query_validator(user_query, db_schema, context_data, generated_sql))
    ]
    
    # Execute validations in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(task[1]): task[0] for task in validation_tasks
        }
        
        # Collect results as they complete
        for future in future_to_task:
            task_name = future_to_task[future]
            try:
                result = future.result(timeout=30)  # 30 second timeout per validation
                validation_results[task_name] = {
                    "result": result,
                    "parallel": True,
                    "status": "completed"
                }
                logger.info(f"Parallel validation {task_name} completed")
            except Exception as e:
                logger.error(f"Parallel validation {task_name} failed: {e}")
                validation_results[task_name] = {
                    "result": None,
                    "parallel": True,
                    "status": "failed",
                    "error": str(e)
                }
    
    # Execute guardrail validation sequentially (depends on other results)
    validation_results["guardrail"] = _execute_validation_task(
        "guardrail", 
        lambda: sql_guardrail(generated_sql, user_type), 
        parallel=False
    )
    
    return validation_results


def _execute_sequential_validation(
    user_query: str,
    generated_sql: str,
    db_schema: str,
    context_data: str,
    user_type: str
) -> Dict[str, Any]:
    """
    Execute validations sequentially for medium complexity queries.
    """
    validation_results = {}
    
    # Step 1: Schema validation
    validation_results["schema_validation"] = _execute_validation_task(
        "schema_validation",
        lambda: strict_schema_validator(generated_sql, db_schema, user_query),
        parallel=False
    )
    
    # Early exit if schema validation fails
    if validation_results["schema_validation"]["status"] == "failed":
        return validation_results
    
    schema_result = validation_results["schema_validation"]["result"]
    if schema_result and not schema_result.get("is_valid", True):
        logger.info("Schema validation failed, skipping remaining validations")
        return validation_results
    
    # Step 2: SQL injection detection
    validation_results["injection_detection"] = _execute_validation_task(
        "injection_detection",
        lambda: sql_injection_detector(generated_sql),
        parallel=False
    )
    
    # Early exit if injection detected
    if validation_results["injection_detection"]["status"] == "failed":
        return validation_results
    
    injection_result = validation_results["injection_detection"]["result"]
    if injection_result and injection_result.get("is_injection", False):
        logger.info("SQL injection detected, skipping remaining validations")
        return validation_results
    
    # Step 3: Query validation
    validation_results["query_validation"] = _execute_validation_task(
        "query_validation",
        lambda: sql_query_validator(user_query, db_schema, context_data, generated_sql),
        parallel=False
    )
    
    # Step 4: Guardrail validation
    validation_results["guardrail"] = _execute_validation_task(
        "guardrail",
        lambda: sql_guardrail(generated_sql, user_type),
        parallel=False
    )
    
    return validation_results


def _execute_minimal_validation(
    user_query: str,
    generated_sql: str,
    db_schema: str,
    context_data: str,
    user_type: str
) -> Dict[str, Any]:
    """
    Execute minimal validation for simple queries.
    """
    validation_results = {}
    
    # For simple queries, only run essential validations
    validation_results["injection_detection"] = _execute_validation_task(
        "injection_detection",
        lambda: sql_injection_detector(generated_sql),
        parallel=False
    )
    
    # Early exit for critical failures
    injection_result = validation_results["injection_detection"]["result"]
    if injection_result and injection_result.get("is_injection", False):
        logger.info("SQL injection detected in minimal validation")
        return validation_results
    
    validation_results["guardrail"] = _execute_validation_task(
        "guardrail",
        lambda: sql_guardrail(generated_sql, user_type),
        parallel=False
    )
    
    return validation_results


def _analyze_validation_results(validation_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze validation results and determine overall validity.
    """
    errors = []
    warnings = []
    recommendations = []
    is_valid = True
    
    for validation_name, validation_data in validation_results.items():
        if validation_data.get("status") == "failed":
            errors.append(f"{validation_name}: {validation_data.get('error', 'Unknown error')}")
            is_valid = False
            continue
        
        result = validation_data.get("result")
        if not result:
            continue
        
        # Analyze specific validation results
        if validation_name == "schema_validation":
            if not result.get("is_valid", True):
                errors.extend(result.get("errors", []))
                is_valid = False
            else:
                warnings.extend(result.get("warnings", []))
                recommendations.extend(result.get("suggestions", []))
        
        elif validation_name == "injection_detection":
            if result.get("is_injection", False):
                errors.append(f"SQL injection detected: {result.get('reason', 'Unknown pattern')}")
                is_valid = False
            else:
                confidence = result.get("confidence", "unknown")
                if confidence == "low":
                    warnings.append("Low confidence in SQL injection detection")
        
        elif validation_name == "query_validation":
            if not result.get("is_correct", True):
                errors.append(f"Query validation failed: {result.get('explanation', 'Unknown issue')}")
                is_valid = False
            else:
                suggestions = result.get("suggestions", [])
                if suggestions:
                    recommendations.extend(suggestions)
        
        elif validation_name == "guardrail":
            if result.get("decision") == "reject":
                errors.append(f"Guardrail rejected: {result.get('feedback', 'Unknown reason')}")
                is_valid = False
            elif result.get("decision") == "review":
                warnings.append(f"Guardrail review required: {result.get('feedback', 'Unknown reason')}")
    
    return {
        "is_valid": is_valid,
        "errors": errors,
        "warnings": warnings,
        "recommendations": recommendations
    }
