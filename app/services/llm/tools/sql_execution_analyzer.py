from langfuse.decorators import observe
from vaul import tool_call
from typing import Dict, Any
import re

from app import logger
from app.services.llm.session import LLMSession
from flask import current_app

import json


@tool_call
@observe
def sql_execution_analyzer(
    sql_query: str,
    error_message: str,
    user_query: str,
    db_schema: str = ""
) -> Dict[str, Any]:
    """
    Analyze SQL execution failures to determine if they're due to SQL structure issues or valid execution reasons.
    
    Args:
        sql_query: The SQL query that failed
        error_message: The error message from the database
        user_query: The original user query for context
        db_schema: Database schema information for validation
        
    Returns:
        {
            "failure_type": "sql_structure|valid_execution|unknown",
            "should_regenerate": bool,
            "regeneration_feedback": str,
            "user_friendly_message": str,
            "technical_details": str,
            "suggested_fixes": list[str]
        }
    """
    if not sql_query or not error_message:
        return {
            "failure_type": "unknown",
            "should_regenerate": False,
            "regeneration_feedback": "Missing SQL query or error message",
            "user_friendly_message": "Unable to analyze the error. Please try again.",
            "technical_details": "Missing required input for analysis",
            "suggested_fixes": []
        }
    
    try:
        llm = LLMSession(
            chat_model=current_app.config.get("CHAT_MODEL"),
            embedding_model=current_app.config.get("EMBEDDING_MODEL"),
        )
        
        system_message = (
            "You are a SQL execution failure analyzer. Your job is to determine if a SQL execution failure "
            "is due to SQL structure issues (that should be fixed by regenerating the query) or valid execution reasons "
            "(like missing data, permissions, etc.).\n\n"
            "ANALYSIS CATEGORIES:\n\n"
            "SQL_STRUCTURE (should_regenerate = true):\n"
            "- Syntax errors (missing semicolons, invalid keywords, etc.)\n"
            "- Table/column name errors (non-existent tables/columns)\n"
            "- Data type mismatches in WHERE clauses\n"
            "- Invalid JOIN syntax or conditions\n"
            "- Missing or incorrect GROUP BY clauses\n"
            "- Invalid function usage or parameters\n"
            "- Incorrect ORDER BY syntax\n"
            "- Invalid LIMIT/OFFSET usage\n"
            "- Missing required clauses (e.g., HAVING without GROUP BY)\n"
            "- Incorrect subquery syntax\n"
            "- Invalid aliases or table references\n\n"
            "VALID_EXECUTION (should_regenerate = false):\n"
            "- No data found (empty result sets)\n"
            "- Permission denied errors\n"
            "- Database connection issues\n"
            "- Lock/contention issues\n"
            "- Resource exhaustion (timeout, memory)\n"
            "- Constraint violations (foreign key, unique, etc.)\n"
            "- Data integrity issues\n"
            "- Business logic errors (e.g., trying to delete non-existent records)\n"
            "- Valid but complex queries that exceed limits\n\n"
            "ANALYSIS GUIDELINES:\n"
            "- If the error suggests the SQL structure is fundamentally wrong, classify as SQL_STRUCTURE\n"
            "- If the error suggests the SQL is correct but execution failed for valid reasons, classify as VALID_EXECUTION\n"
            "- Provide specific, actionable feedback for regeneration\n"
            "- Give user-friendly explanations that non-technical users can understand\n"
            "- Include technical details for debugging\n"
            "- Suggest specific fixes when possible\n\n"
            "Respond with JSON only:\n"
            "{\n"
            '  "failure_type": "sql_structure|valid_execution|unknown",\n'
            '  "should_regenerate": true/false,\n'
            '  "regeneration_feedback": "specific feedback for text_to_sql tool",\n'
            '  "user_friendly_message": "message for end user",\n'
            '  "technical_details": "detailed technical explanation",\n'
            '  "suggested_fixes": ["fix1", "fix2", ...]\n'
            "}"
        )
        
        user_message = (
            f"SQL Query:\n{sql_query}\n\n"
            f"Error Message:\n{error_message}\n\n"
            f"User Query:\n{user_query}\n\n"
            f"Database Schema:\n{db_schema}\n\n"
            f"Analyze this SQL execution failure and determine if it's a SQL structure issue or a valid execution failure."
        )
        
        response = llm.chat(
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ]
        )
        content = response.choices[0].message.content or ""
        
        # Try to parse JSON response
        try:
            # Extract JSON from response if it's wrapped in code blocks
            json_match = re.search(r"```json\s*([\s\S]*?)\s*```", content, re.IGNORECASE)
            if json_match:
                content = json_match.group(1)
            
            # Also try to extract JSON if it's just wrapped in ```
            if not json_match:
                json_match = re.search(r"```\s*([\s\S]*?)\s*```", content)
            if json_match:
                content = json_match.group(1)
            
            parsed = json.loads(content)
            
            failure_type = str(parsed.get("failure_type", "unknown")).lower()
            should_regenerate = bool(parsed.get("should_regenerate", False))
            regeneration_feedback = str(parsed.get("regeneration_feedback", ""))
            user_friendly_message = str(parsed.get("user_friendly_message", ""))
            technical_details = str(parsed.get("technical_details", ""))
            suggested_fixes = parsed.get("suggested_fixes", [])
            
            # Validate failure_type
            if failure_type not in ["sql_structure", "valid_execution", "unknown"]:
                failure_type = "unknown"
            
            logger.info(f"SQL execution analysis: {failure_type} (should_regenerate: {should_regenerate})")
            
            return {
                "failure_type": failure_type,
                "should_regenerate": should_regenerate,
                "regeneration_feedback": regeneration_feedback,
                "user_friendly_message": user_friendly_message,
                "technical_details": technical_details,
                "suggested_fixes": suggested_fixes
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Raw response: {content}")
            
            # Fallback: use regex patterns to determine failure type
            return _fallback_analysis(sql_query, error_message, content)
            
    except Exception as e:
        logger.error(f"Error in SQL execution analysis: {e}")
        return {
            "failure_type": "unknown",
            "should_regenerate": False,
            "regeneration_feedback": f"Analysis failed: {str(e)}",
            "user_friendly_message": "Unable to analyze the error. Please try again.",
            "technical_details": f"Analysis error: {str(e)}",
            "suggested_fixes": []
        }


def _fallback_analysis(sql_query: str, error_message: str, llm_response: str) -> Dict[str, Any]:
    """
    Fallback analysis using regex patterns when LLM parsing fails.
    """
    # Handle None or empty error messages
    if not error_message:
        return {
            "failure_type": "unknown",
            "should_regenerate": False,
            "regeneration_feedback": "No error message provided",
            "user_friendly_message": "Unable to analyze the error. Please try again.",
            "technical_details": "No error message provided for analysis",
            "suggested_fixes": []
        }
    
    error_lower = error_message.lower()
    sql_lower = sql_query.lower()
    
    # Common SQL structure error patterns
    sql_structure_patterns = [
        r"table.*not found",
        r"column.*not found",
        r"syntax error",
        r"invalid.*syntax",
        r"missing.*semicolon",
        r"unexpected.*token",
        r"invalid.*identifier",
        r"unknown.*column",
        r"unknown.*table",
        r"ambiguous.*column",
        r"group.*by.*error",
        r"order.*by.*error",
        r"having.*without.*group.*by",
        r"must appear in the group by clause",
        r"group by clause",
        r"can only drop one object at a time",
        r"can only.*one.*at a time",
        r"can.*only.*drop.*one",
        r"cannot drop multiple",
        r"multiple.*drop.*not.*supported",
        r"not implemented",
        r"invalid.*function",
        r"wrong.*number.*of.*arguments",
        r"data.*type.*mismatch",
        r"cannot.*convert",
        r"invalid.*alias",
        r"duplicate.*column",
        r"missing.*right.*parenthesis"
    ]
    
    # Common valid execution error patterns
    valid_execution_patterns = [
        r"no.*data.*found",
        r"empty.*result",
        r"no.*rows.*affected",
        r"permission.*denied",
        r"access.*denied",
        r"insufficient.*privileges",
        r"connection.*failed",
        r"timeout",
        r"lock.*timeout",
        r"deadlock",
        r"constraint.*violation",
        r"foreign.*key.*violation",
        r"unique.*constraint",
        r"check.*constraint",
        r"resource.*exhausted",
        r"memory.*limit",
        r"disk.*space",
        r"too.*many.*rows",
        r"result.*too.*large"
    ]
    
    # Check for SQL structure errors
    for pattern in sql_structure_patterns:
        if re.search(pattern, error_lower):
            return {
                "failure_type": "sql_structure",
                "should_regenerate": True,
                "regeneration_feedback": f"SQL structure error detected: {error_message}",
                "user_friendly_message": "There's an issue with the SQL query structure. I'll try to fix it.",
                "technical_details": f"Detected SQL structure error: {error_message}",
                "suggested_fixes": ["Check table and column names", "Verify SQL syntax", "Ensure proper clause usage"]
            }
    
    # Check for valid execution errors
    for pattern in valid_execution_patterns:
        if re.search(pattern, error_lower):
            return {
                "failure_type": "valid_execution",
                "should_regenerate": False,
                "regeneration_feedback": f"Valid execution error: {error_message}",
                "user_friendly_message": "The query is correct but couldn't be executed due to data or permission issues.",
                "technical_details": f"Valid execution error: {error_message}",
                "suggested_fixes": ["Check data availability", "Verify permissions", "Try with different criteria"]
            }
    
    # Default to unknown if no patterns match
    return {
        "failure_type": "unknown",
        "should_regenerate": False,
        "regeneration_feedback": f"Unknown error: {error_message}",
        "user_friendly_message": "An unexpected error occurred. Please try again.",
        "technical_details": f"Unknown error: {error_message}",
        "suggested_fixes": ["Try rephrasing your request", "Check if the data exists", "Contact support if the issue persists"]
    }
