from langfuse.decorators import observe
from vaul import tool_call
from typing import Dict
import re

from app import logger
from app.services.llm.session import LLMSession
from flask import current_app

import json


@tool_call
@observe
def sql_injection_detector(sql_query: str, user_type: str = "user") -> Dict[str, str]:
    """
    Simple LLM-based SQL injection detection that analyzes queries for malicious patterns.
    
    Args:
        sql_query: The SQL query to analyze for injection patterns
        user_type: User type ("user" or "admin") - admin users get more lenient detection
        
    Returns:
        {"is_injection": true|false, "reason": "explanation", "confidence": "high|medium|low"}
    """
    if not sql_query:
        return {"is_injection": False, "reason": "Empty query", "confidence": "high"}
    
    try:
        llm = LLMSession(
            chat_model=current_app.config.get("CHAT_MODEL"),
            embedding_model=current_app.config.get("EMBEDDING_MODEL"),
        )
        
        # Adjust detection sensitivity based on user type
        if user_type.lower() == "admin":
            system_message = (
                "You are a SQL security expert analyzing queries for an ADMIN user. "
                "Admin users have elevated privileges, so be more lenient with schema-related operations.\n\n"
                "Look for these specific injection patterns:\n"
                "1. Boolean-based injections: OR 1=1, OR TRUE, AND 1=1, etc.\n"
                "2. Comment-based injections: --, /* */, #\n"
                "3. Union-based injections: UNION SELECT, UNION ALL SELECT\n"
                "4. Stacked queries: multiple statements separated by semicolons\n"
                "5. Time-based injections: SLEEP(), WAITFOR DELAY, BENCHMARK()\n"
                "6. Privilege escalation: GRANT, REVOKE, EXEC, EXECUTE\n"
                "7. File operations: INTO OUTFILE, COPY TO, LOAD_FILE()\n"
                "8. Dangerous functions: xp_cmdshell, system(), eval()\n"
                "9. Authentication bypass attempts\n"
                "10. Data exfiltration attempts\n\n"
                "ADMIN-RELATED LENIENCY:\n"
                "- System table access (information_schema, sys.tables, pg_catalog) is acceptable for admin users\n"
                "- Schema discovery operations are acceptable for admin users\n"
                "- DDL operations (CREATE, ALTER, DROP) are acceptable for admin users\n"
                "- Table structure queries are acceptable for admin users\n\n"
                "IMPORTANT: Only flag as injection if you are confident the pattern is malicious.\n"
                "Legitimate SQL functions like CONCAT(), SUBSTRING(), etc. should NOT be flagged.\n"
                "Normal WHERE clauses with OR/AND conditions should NOT be flagged unless they appear to bypass security.\n\n"
                "Respond with JSON only:\n"
                "{\n"
                '  "is_injection": true/false,\n'
                '  "reason": "clear explanation of why this is or is not an injection",\n'
                '  "confidence": "high/medium/low"\n'
                "}"
            )
        else:
            system_message = (
                "You are a SQL security expert. Analyze the provided SQL query for potential SQL injection attacks.\n\n"
                "Look for these specific injection patterns:\n"
                "1. Boolean-based injections: OR 1=1, OR TRUE, AND 1=1, etc.\n"
                "2. Comment-based injections: --, /* */, #\n"
                "3. Union-based injections: UNION SELECT, UNION ALL SELECT\n"
                "4. Stacked queries: multiple statements separated by semicolons\n"
                "5. Time-based injections: SLEEP(), WAITFOR DELAY, BENCHMARK()\n"
                "6. System table access: information_schema, sys.tables, pg_catalog\n"
                "7. Privilege escalation: GRANT, REVOKE, EXEC, EXECUTE\n"
                "8. File operations: INTO OUTFILE, COPY TO, LOAD_FILE()\n"
                "9. Dangerous functions: xp_cmdshell, system(), eval()\n"
                "10. Authentication bypass attempts\n"
                "11. Data exfiltration attempts\n"
                "12. Schema discovery attempts\n\n"
                "IMPORTANT: Only flag as injection if you are confident the pattern is malicious.\n"
                "Legitimate SQL functions like CONCAT(), SUBSTRING(), etc. should NOT be flagged.\n"
                "Normal WHERE clauses with OR/AND conditions should NOT be flagged unless they appear to bypass security.\n\n"
                "Respond with JSON only:\n"
                "{\n"
                '  "is_injection": true/false,\n'
                '  "reason": "clear explanation of why this is or is not an injection",\n'
                '  "confidence": "high/medium/low"\n'
                "}"
            )
        
        user_message = f"Analyze this SQL query for SQL injection patterns:\n\n{sql_query}"
        
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
            is_injection = bool(parsed.get("is_injection", False))
            reason = str(parsed.get("reason", ""))
            confidence = str(parsed.get("confidence", "medium"))
            
            logger.info(f"SQL injection detection result: {is_injection} (confidence: {confidence}) - {reason}")
            
            return {
                "is_injection": is_injection,
                "reason": reason,
                "confidence": confidence
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Raw response: {content}")
            
            # Fallback: check if response contains clear injection indicators
            if any(keyword in content.lower() for keyword in ["injection", "malicious", "attack", "dangerous"]):
                return {
                    "is_injection": True,
                    "reason": f"LLM detected injection patterns: {content[:200]}",
                    "confidence": "medium"
                }
            elif any(keyword in content.lower() for keyword in ["safe", "legitimate", "normal", "ok"]):
                return {
                    "is_injection": False,
                    "reason": f"LLM determined query is safe: {content[:200]}",
                    "confidence": "medium"
                }
            else:
                return {
                    "is_injection": False,
                    "reason": "LLM analysis inconclusive - defaulting to safe",
                    "confidence": "low"
                }
            
    except Exception as e:
        logger.error(f"Error in LLM-based injection detection: {e}")
        return {
            "is_injection": False, 
            "reason": "LLM analysis failed - defaulting to safe", 
            "confidence": "low"
    }
