import re
import statistics
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
from collections import Counter, defaultdict

from langfuse.decorators import observe
from vaul import tool_call

from app import logger
from app.services.llm.structured_outputs.schema_description import (
    TableSchemaDescription, 
    ColumnConstraint, 
    ForeignKeyInfo
)


@tool_call
@observe
def describe_table_schema(
    table_name: str,
    column_schemas: List[Dict[str, Any]],
    example_rows: List[Dict[str, Any]]
) -> TableSchemaDescription:
    """
    Analyze a table's schema and example data to provide comprehensive information
    for querying the table effectively.
    
    Args:
        table_name: Name of the table
        column_schemas: List of column definitions with name, type, constraints, etc.
        example_rows: Sample data rows to analyze patterns and relationships
        
    Returns:
        Comprehensive table schema description with querying recommendations
    """
    
    logger.info(f"Analyzing schema for table: {table_name}")
    
    # Analyze column constraints and patterns
    columns = _analyze_columns(column_schemas, example_rows)
    
    # Identify primary keys
    primary_key_columns = _identify_primary_keys(columns, example_rows)
    
    # Detect foreign key relationships
    foreign_keys = _detect_foreign_keys(table_name, columns, example_rows)
    
    # Analyze data characteristics
    data_characteristics = _analyze_data_characteristics(example_rows, columns)
    
    # Generate query recommendations
    query_recommendations = _generate_query_recommendations(columns, primary_key_columns, foreign_keys)
    
    # Identify common join patterns
    common_joins = _identify_common_joins(foreign_keys, columns)
    
    # Performance considerations
    performance_notes = _generate_performance_notes(columns, example_rows, primary_key_columns)
    
    # Business context
    business_context = _infer_business_context(table_name, columns, example_rows)
    
    # Data quality assessment
    data_quality_notes = _assess_data_quality(columns, example_rows)
    
    # Create table description
    table_description = _generate_table_description(table_name, columns, business_context)
    
    return TableSchemaDescription(
        table_name=table_name,
        table_description=table_description,
        total_rows=len(example_rows),
        total_columns=len(columns),
        columns=columns,
        primary_key_columns=primary_key_columns,
        foreign_keys=foreign_keys,
        data_characteristics=data_characteristics,
        query_recommendations=query_recommendations,
        common_joins=common_joins,
        performance_notes=performance_notes,
        business_context=business_context,
        data_quality_notes=data_quality_notes
    )


def _analyze_columns(column_schemas: List[Dict[str, Any]], example_rows: List[Dict[str, Any]]) -> List[ColumnConstraint]:
    """Analyze each column for constraints, patterns, and data characteristics."""
    columns = []
    
    for col_schema in column_schemas:
        col_name = col_schema.get('name', '')
        data_type = col_schema.get('type', 'unknown')
        
        # Extract column values
        col_values = [row.get(col_name) for row in example_rows if col_name in row]
        
        # Basic constraints
        is_nullable = _check_nullable(col_values, col_schema)
        is_primary_key = _check_primary_key(col_name, col_schema, col_values)
        is_unique = _check_unique(col_values)
        default_value = col_schema.get('default')
        
        # Data analysis
        min_value, max_value = _get_value_range(col_values, data_type)
        distinct_count = len(set(col_values)) if col_values else 0
        common_values = _get_common_values(col_values)
        pattern_description = _analyze_patterns(col_values, data_type)
        
        columns.append(ColumnConstraint(
            column_name=col_name,
            data_type=data_type,
            is_nullable=is_nullable,
            is_primary_key=is_primary_key,
            is_unique=is_unique,
            default_value=default_value,
            min_value=min_value,
            max_value=max_value,
            distinct_count=distinct_count,
            common_values=common_values,
            pattern_description=pattern_description
        ))
    
    return columns


def _check_nullable(values: List[Any], schema: Dict[str, Any]) -> bool:
    """Check if column allows NULL values."""
    if 'nullable' in schema:
        return schema['nullable']
    
    # Check if any values are None/null
    return any(v is None or v == '' for v in values)


def _check_primary_key(col_name: str, schema: Dict[str, Any], values: List[Any]) -> bool:
    """Check if column is likely a primary key."""
    if 'primary_key' in schema:
        return schema['primary_key']
    
    # Heuristic: unique, not null, and looks like an ID
    is_unique = len(set(values)) == len(values) and all(v is not None for v in values)
    looks_like_id = any([
        'id' in col_name.lower(),
        'key' in col_name.lower(),
        'pk' in col_name.lower(),
        col_name.lower().endswith('_id')
    ])
    
    return is_unique and looks_like_id


def _check_unique(values: List[Any]) -> bool:
    """Check if column has unique values."""
    non_null_values = [v for v in values if v is not None]
    return len(set(non_null_values)) == len(non_null_values)


def _get_value_range(values: List[Any], data_type: str) -> Tuple[Optional[str], Optional[str]]:
    """Get min and max values for the column."""
    non_null_values = [v for v in values if v is not None]
    
    if not non_null_values:
        return None, None
    
    try:
        if data_type.lower() in ['int', 'integer', 'bigint', 'smallint']:
            numeric_values = [int(v) for v in non_null_values if str(v).isdigit()]
            if numeric_values:
                return str(min(numeric_values)), str(max(numeric_values))
        elif data_type.lower() in ['float', 'double', 'decimal', 'numeric']:
            numeric_values = [float(v) for v in non_null_values if _is_numeric(v)]
            if numeric_values:
                return str(min(numeric_values)), str(max(numeric_values))
        elif data_type.lower() in ['date', 'datetime', 'timestamp']:
            date_values = [v for v in non_null_values if _is_date_like(v)]
            if date_values:
                return str(min(date_values)), str(max(date_values))
        else:
            # For strings, use lexicographic order
            return str(min(non_null_values)), str(max(non_null_values))
    except (ValueError, TypeError):
        pass
    
    return None, None


def _is_numeric(value: Any) -> bool:
    """Check if value can be converted to numeric."""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def _is_date_like(value: Any) -> bool:
    """Check if value looks like a date."""
    if isinstance(value, (datetime, date)):
        return True
    
    if isinstance(value, str):
        # Common date patterns
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',  # YYYY-MM-DD HH:MM:SS
        ]
        return any(re.match(pattern, value) for pattern in date_patterns)
    
    return False


def _get_common_values(values: List[Any], max_common: int = 5) -> Optional[List[str]]:
    """Get most common values in the column."""
    non_null_values = [v for v in values if v is not None]
    
    if not non_null_values:
        return None
    
    counter = Counter(non_null_values)
    common = counter.most_common(max_common)
    
    # Only return if there are meaningful patterns (not all unique)
    if len(common) < len(non_null_values) * 0.8:
        return [str(value) for value, count in common]
    
    return None


def _analyze_patterns(values: List[Any], data_type: str) -> Optional[str]:
    """Analyze patterns in the data."""
    non_null_values = [v for v in values if v is not None]
    
    if not non_null_values:
        return None
    
    patterns = []
    
    # Check for sequential patterns
    if data_type.lower() in ['int', 'integer', 'bigint']:
        numeric_values = [int(v) for v in non_null_values if str(v).isdigit()]
        if numeric_values and len(numeric_values) > 1:
            sorted_values = sorted(numeric_values)
            differences = [sorted_values[i+1] - sorted_values[i] for i in range(len(sorted_values)-1)]
            if len(set(differences)) == 1:
                patterns.append(f"Sequential with step {differences[0]}")
    
    # Check for date patterns
    if data_type.lower() in ['date', 'datetime']:
        date_values = [v for v in non_null_values if _is_date_like(v)]
        if date_values:
            patterns.append("Contains date/time values")
    
    # Check for string patterns
    if data_type.lower() in ['varchar', 'text', 'string']:
        string_values = [str(v) for v in non_null_values]
        
        # Check for email patterns
        email_count = sum(1 for v in string_values if '@' in v and '.' in v)
        if email_count > len(string_values) * 0.5:
            patterns.append("Contains email addresses")
        
        # Check for URL patterns
        url_count = sum(1 for v in string_values if v.startswith(('http://', 'https://')))
        if url_count > len(string_values) * 0.3:
            patterns.append("Contains URLs")
        
        # Check for phone patterns
        phone_count = sum(1 for v in string_values if re.match(r'[\d\-\+\(\)\s]{10,}', v))
        if phone_count > len(string_values) * 0.3:
            patterns.append("Contains phone numbers")
    
    return "; ".join(patterns) if patterns else None


def _identify_primary_keys(columns: List[ColumnConstraint], example_rows: List[Dict[str, Any]]) -> List[str]:
    """Identify primary key columns."""
    primary_keys = []
    
    for col in columns:
        if col.is_primary_key:
            primary_keys.append(col.column_name)
    
    # If no explicit primary keys found, look for composite keys
    if not primary_keys and len(example_rows) > 1:
        # Check combinations of unique columns
        unique_columns = [col.column_name for col in columns if col.is_unique]
        
        for i, col1 in enumerate(unique_columns):
            for col2 in unique_columns[i+1:]:
                # Check if combination is unique
                combinations = set()
                for row in example_rows:
                    combo = (row.get(col1), row.get(col2))
                    combinations.add(combo)
                
                if len(combinations) == len(example_rows):
                    primary_keys.extend([col1, col2])
                    break
    
    return list(set(primary_keys))


def _detect_foreign_keys(table_name: str, columns: List[ColumnConstraint], example_rows: List[Dict[str, Any]]) -> List[ForeignKeyInfo]:
    """Detect potential foreign key relationships."""
    foreign_keys = []
    
    for col in columns:
        # Look for columns that might be foreign keys
        if any([
            col.column_name.lower().endswith('_id'),
            'id' in col.column_name.lower() and col.column_name.lower() != 'id',
            'key' in col.column_name.lower(),
            'ref' in col.column_name.lower()
        ]):
            # Try to infer referenced table
            referenced_table = _infer_referenced_table(col.column_name, table_name)
            referenced_column = 'id'  # Assume primary key is 'id'
            
            # Determine relationship type
            relationship_type = _determine_relationship_type(col, example_rows)
            
            foreign_keys.append(ForeignKeyInfo(
                column_name=col.column_name,
                referenced_table=referenced_table,
                referenced_column=referenced_column,
                relationship_type=relationship_type
            ))
    
    return foreign_keys


def _infer_referenced_table(column_name: str, current_table: str) -> str:
    """Infer the referenced table name from the foreign key column name."""
    # Remove common suffixes
    base_name = column_name.lower()
    for suffix in ['_id', '_key', '_ref', 'id', 'key']:
        if base_name.endswith(suffix):
            base_name = base_name[:-len(suffix)]
            break
    
    # Handle common patterns
    if base_name.endswith('_'):
        base_name = base_name[:-1]
    
    # Convert to singular if plural
    if base_name.endswith('s'):
        base_name = base_name[:-1]
    
    return base_name


def _determine_relationship_type(column: ColumnConstraint, example_rows: List[Dict[str, Any]]) -> str:
    """Determine the type of relationship."""
    values = [row.get(column.column_name) for row in example_rows if column.column_name in row]
    unique_values = set(values)
    
    if column.is_unique:
        return "one-to-one"
    elif len(unique_values) < len(values) * 0.8:
        return "many-to-one"
    else:
        return "one-to-many"


def _analyze_data_characteristics(example_rows: List[Dict[str, Any]], columns: List[ColumnConstraint]) -> Dict[str, Any]:
    """Analyze general characteristics of the data."""
    characteristics = {
        "row_count": len(example_rows),
        "column_count": len(columns),
        "data_types": {},
        "null_percentage": {},
        "unique_percentage": {}
    }
    
    for col in columns:
        col_values = [row.get(col.column_name) for row in example_rows if col.column_name in row]
        non_null_count = sum(1 for v in col_values if v is not None)
        
        characteristics["data_types"][col.column_name] = col.data_type
        characteristics["null_percentage"][col.column_name] = (len(col_values) - non_null_count) / len(col_values) if col_values else 0
        characteristics["unique_percentage"][col.column_name] = col.distinct_count / len(col_values) if col_values else 0
    
    return characteristics


def _generate_query_recommendations(columns: List[ColumnConstraint], primary_keys: List[str], foreign_keys: List[ForeignKeyInfo]) -> List[str]:
    """Generate recommendations for querying the table."""
    recommendations = []
    
    # Primary key recommendations
    if primary_keys:
        recommendations.append(f"Use primary key columns ({', '.join(primary_keys)}) for efficient lookups")
    
    # Foreign key recommendations
    if foreign_keys:
        fk_columns = [fk.column_name for fk in foreign_keys]
        recommendations.append(f"Join with related tables using foreign key columns: {', '.join(fk_columns)}")
    
    # Index recommendations
    unique_columns = [col.column_name for col in columns if col.is_unique]
    if unique_columns:
        recommendations.append(f"Consider indexing unique columns: {', '.join(unique_columns)}")
    
    # Data type specific recommendations
    for col in columns:
        if col.data_type.lower() in ['date', 'datetime']:
            recommendations.append(f"Use date functions for filtering {col.column_name}")
        elif col.data_type.lower() in ['varchar', 'text']:
            recommendations.append(f"Use LIKE or pattern matching for {col.column_name} searches")
    
    # General recommendations
    recommendations.append("Use LIMIT clause for large result sets")
    recommendations.append("Consider using DISTINCT for duplicate removal")
    
    return recommendations


def _identify_common_joins(foreign_keys: List[ForeignKeyInfo], columns: List[ColumnConstraint]) -> List[str]:
    """Identify common join patterns."""
    joins = []
    
    for fk in foreign_keys:
        join_sql = f"JOIN {fk.referenced_table} ON {fk.column_name} = {fk.referenced_table}.{fk.referenced_column}"
        joins.append(join_sql)
    
    return joins


def _generate_performance_notes(columns: List[ColumnConstraint], example_rows: List[Dict[str, Any]], primary_keys: List[str]) -> List[str]:
    """Generate performance considerations."""
    notes = []
    
    # Row count considerations
    row_count = len(example_rows)
    if row_count > 10000:
        notes.append("Large table - consider pagination and indexing strategies")
    elif row_count < 100:
        notes.append("Small table - full table scans may be acceptable")
    
    # Primary key performance
    if primary_keys:
        notes.append("Primary key lookups will be very fast")
    else:
        notes.append("No primary key identified - consider adding one for performance")
    
    # Data type performance
    for col in columns:
        if col.data_type.lower() in ['text', 'varchar'] and col.max_value and len(col.max_value) > 100:
            notes.append(f"Large text in {col.column_name} - consider indexing strategies")
    
    return notes


def _infer_business_context(table_name: str, columns: List[ColumnConstraint], example_rows: List[Dict[str, Any]]) -> str:
    """Infer the business context of the table."""
    # Analyze table name
    table_lower = table_name.lower()
    
    # Common business entities
    if any(word in table_lower for word in ['user', 'customer', 'client', 'person']):
        return "User/Customer management - stores information about users or customers"
    elif any(word in table_lower for word in ['order', 'purchase', 'transaction', 'sale']):
        return "Order/Transaction management - stores business transactions and orders"
    elif any(word in table_lower for word in ['product', 'item', 'goods', 'inventory']):
        return "Product/Inventory management - stores product information and inventory"
    elif any(word in table_lower for word in ['log', 'audit', 'history', 'event']):
        return "Logging/Audit - stores system events, logs, or audit trails"
    elif any(word in table_lower for word in ['config', 'setting', 'parameter']):
        return "Configuration - stores system settings and configuration data"
    else:
        return "General data storage - purpose inferred from column structure"


def _assess_data_quality(columns: List[ColumnConstraint], example_rows: List[Dict[str, Any]]) -> List[str]:
    """Assess data quality and identify potential issues."""
    issues = []
    
    for col in columns:
        col_values = [row.get(col.column_name) for row in example_rows if col.column_name in row]
        non_null_count = sum(1 for v in col_values if v is not None)
        
        # Check for high null percentage
        null_percentage = (len(col_values) - non_null_count) / len(col_values) if col_values else 0
        if null_percentage > 0.5:
            issues.append(f"High null percentage ({null_percentage:.1%}) in {col.column_name}")
        
        # Check for data type consistency
        if col.data_type.lower() in ['int', 'integer']:
            non_numeric = sum(1 for v in col_values if v is not None and not str(v).isdigit())
            if non_numeric > 0:
                issues.append(f"Non-numeric values found in integer column {col.column_name}")
        
        # Check for empty strings
        empty_strings = sum(1 for v in col_values if v == '')
        if empty_strings > len(col_values) * 0.3:
            issues.append(f"Many empty strings in {col.column_name}")
    
    if not issues:
        issues.append("Data quality appears good - no major issues detected")
    
    return issues


def _generate_table_description(table_name: str, columns: List[ColumnConstraint], business_context: str) -> str:
    """Generate a comprehensive table description."""
    description_parts = [
        f"Table '{table_name}' contains {len(columns)} columns and appears to be used for {business_context.lower()}.",
        f"Key columns include: {', '.join([col.column_name for col in columns if col.is_primary_key or col.is_unique])}",
        f"Data types range from {', '.join(set(col.data_type for col in columns))}",
    ]
    
    return " ".join(description_parts)
