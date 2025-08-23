# Conversation Response Types

This document outlines all the response types that the conversation command can handle and return to users.

## Response Type Categories

### 1. Human Verification Requests

#### Clarification Request
**When**: Query is too vague or lacks specific details
**Response Structure**:
```json
{
  "type": "human_verification",
  "sql": "",
  "feedback": "Query is too vague to generate accurate SQL. Please provide more specific details.",
  "requires_clarification": true,
  "original_query": "show me private label customers, list 100 of them",
  "message": "I need clarification because your query appears to be too vague or lacks specific details.\n\nYour request: \"show me private label customers, list 100 of them\"\n\nClarity score: 0.3/1.0\nIssues identified: unspecific table, no filters\n\nTo help me generate the correct query, please provide more specific details about what you want to show.\n\nPlease provide additional details to help me understand your request better.",
  "clarification_questions": ["What specific customer data do you want to see?", "Which tables should I look at?"],
  "suggested_tables": ["customers", "orders"],
  "query_type": "read",
  "action_word": "show",
  "clarity_score": 0.3,
  "vague_aspects": ["unspecific table", "no filters"]
}
```
**User Response**: Should provide additional details, NOT yes/no

#### Execution Confirmation Request
**When**: Query is valid but needs human approval (e.g., DDL operations)
**Response Structure**:
```json
{
  "type": "human_verification",
  "sql": "DROP TABLE customers",
  "feedback": "This is a DDL operation that could impact data integrity",
  "requires_clarification": false,
  "original_query": "delete the customers table",
  "message": "I've generated a SQL query for you. Would you like me to execute it?\n\nSQL Query:\nDROP TABLE customers\n\n**Reasoning:** This is a DDL operation that could impact data integrity\n\nPlease respond with \"yes\" to execute or \"no\" to cancel."
}
```
**User Response**: Should respond with "yes" or "no"

### 2. Successful Query Execution

**When**: Query is accepted and executed successfully
**Response Structure**:
```json
{
  "sql": "SELECT * FROM main.customer WHERE Channel = 'private label' LIMIT 100",
  "decision": "accept",
  "feedback": "Query executed successfully",
  "rows": [
    {"CustomerID": 1, "CustomerName": "Private Label Customer 1", "Channel": "private label"},
    {"CustomerID": 2, "CustomerName": "Private Label Customer 2", "Channel": "private label"}
  ],
  "row_count": 2,
  "validation_time": 0.5,
  "validation_strategy": "sequential",
  "query_complexity": "low"
}
```

### 3. Query Rejections and Errors

#### Security Rejection
**When**: Query is rejected due to security concerns
**Response Structure**:
```json
{
  "sql": "DROP TABLE customers",
  "decision": "reject",
  "feedback": "Dangerous operation detected",
  "validation_time": 0.3,
  "validation_strategy": "sequential",
  "query_complexity": "high",
  "performance_metrics": {
    "total_time": 0.3,
    "steps_completed": 3
  }
}
```

#### Execution Error
**When**: Query is valid but fails during execution
**Response Structure**:
```json
{
  "sql": "SELECT * FROM nonexistent_table",
  "decision": "execution_failed",
  "feedback": "Table 'nonexistent_table' does not exist",
  "validation_time": 0.2
}
```

#### Validation Error
**When**: Query fails validation checks
**Response Structure**:
```json
{
  "sql": "SELECT * FROM customers",
  "decision": "reject",
  "feedback": "Validation failed: Schema mismatch detected",
  "validation_time": 0.5,
  "validation_strategy": "sequential"
}
```

### 4. Human Verification Responses

#### Clarification Needed (User said yes/no to clarification request)
**When**: User responds with yes/no to a clarification request
**Response Structure**:
```json
{
  "type": "clarification_needed",
  "message": "Please provide more specific details about your request instead of yes/no.",
  "original_query": "show me data",
  "clarification_questions": ["What specific data do you want to see?"]
}
```

#### Execution Cancelled
**When**: User responds "no" to execution confirmation
**Response Structure**:
```json
{
  "sql": "DROP TABLE customers",
  "decision": "cancelled_by_user",
  "feedback": "Query execution cancelled by user."
}
```

#### Execution Failed After Confirmation
**When**: User confirms execution but it fails
**Response Structure**:
```json
{
  "sql": "SELECT * FROM nonexistent_table",
  "decision": "execution_failed",
  "feedback": "Execution failed after confirmation: Table 'nonexistent_table' does not exist"
}
```

### 5. Error Responses

#### Tool Error
**When**: Text-to-SQL tool encounters an exception
**Response Structure**:
```json
{
  "type": "error",
  "message": "Error generating SQL: Database connection failed",
  "sql": "",
  "decision": "error",
  "feedback": "Exception occurred: Database connection failed"
}
```

#### Invalid Response
**When**: Text-to-SQL tool returns invalid data
**Response Structure**:
```json
{
  "type": "error",
  "message": "Failed to generate a valid response. Please try again.",
  "sql": "",
  "decision": "error",
  "feedback": "Invalid response from text-to-SQL tool"
}
```

#### Unknown Decision Type
**When**: Text-to-SQL tool returns an unknown decision type
**Response Structure**:
```json
{
  "type": "unknown_response",
  "sql": "SELECT * FROM customers",
  "decision": "unknown_decision",
  "feedback": "Some feedback",
  "message": "Received unknown decision type: unknown_decision",
  "original_response": {...}
}
```

## Response Processing Logic

The conversation command uses a comprehensive response processing method (`_process_text_to_sql_response`) that:

1. **Validates Input**: Checks if the response is valid and properly structured
2. **Categorizes Responses**: Identifies the type of response based on content
3. **Normalizes Output**: Ensures consistent response structure
4. **Handles Edge Cases**: Manages unexpected or invalid responses gracefully
5. **Preserves Context**: Maintains relevant information for debugging and user feedback

## Key Features

### Error Handling
- **Exception Catching**: Wraps text-to-SQL calls in try-catch blocks
- **Graceful Degradation**: Returns meaningful error messages instead of crashing
- **Type Safety**: Validates response structure before processing

### Response Consistency
- **Standardized Format**: All responses follow consistent structure
- **Required Fields**: Ensures essential fields are always present
- **Optional Fields**: Preserves additional context when available

### User Experience
- **Clear Messages**: Provides understandable feedback to users
- **Actionable Guidance**: Offers specific next steps when needed
- **Context Preservation**: Maintains conversation history and context

## Testing

All response types are tested to ensure:
- ✅ Proper handling of each response type
- ✅ Consistent output structure
- ✅ Error cases are managed gracefully
- ✅ No undefined values in responses
- ✅ User-friendly error messages
