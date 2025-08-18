from typing import List, Dict, Any, Optional
from pydantic import Field
from vaul import StructuredOutput


class ColumnConstraint(StructuredOutput):
    """Information about column constraints and data patterns."""
    column_name: str = Field(..., title="Name of the column")
    data_type: str = Field(..., title="Data type of the column")
    is_nullable: bool = Field(..., title="Whether the column can contain NULL values")
    is_primary_key: bool = Field(..., title="Whether the column is part of the primary key")
    is_unique: bool = Field(..., title="Whether the column has unique constraints")
    default_value: Optional[str] = Field(None, title="Default value for the column")
    min_value: Optional[str] = Field(None, title="Minimum value observed in the data")
    max_value: Optional[str] = Field(None, title="Maximum value observed in the data")
    distinct_count: Optional[int] = Field(None, title="Number of distinct values")
    common_values: Optional[List[str]] = Field(None, title="Most common values in the column")
    pattern_description: Optional[str] = Field(None, title="Description of data patterns observed")


class ForeignKeyInfo(StructuredOutput):
    """Information about foreign key relationships."""
    column_name: str = Field(..., title="Name of the foreign key column")
    referenced_table: str = Field(..., title="Name of the referenced table")
    referenced_column: str = Field(..., title="Name of the referenced column")
    relationship_type: str = Field(..., title="Type of relationship (one-to-one, one-to-many, etc.)")


class TableSchemaDescription(StructuredOutput):
    """Comprehensive description of a database table schema."""
    table_name: str = Field(..., title="Name of the table")
    table_description: str = Field(..., title="Detailed description of the table's purpose and content")
    total_rows: int = Field(..., title="Total number of rows in the table")
    total_columns: int = Field(..., title="Total number of columns in the table")
    
    # Column information
    columns: List[ColumnConstraint] = Field(..., title="Detailed information about each column")
    
    # Relationships
    primary_key_columns: List[str] = Field(..., title="List of columns that form the primary key")
    foreign_keys: List[ForeignKeyInfo] = Field(..., title="Information about foreign key relationships")
    
    # Data characteristics
    data_characteristics: Dict[str, Any] = Field(..., title="General characteristics of the data")
    
    # Query recommendations
    query_recommendations: List[str] = Field(..., title="Recommended approaches for querying this table")
    common_joins: List[str] = Field(..., title="Common join patterns with other tables")
    performance_notes: List[str] = Field(..., title="Performance considerations for querying this table")
    
    # Business context
    business_context: str = Field(..., title="Business context and typical use cases for this table")
    data_quality_notes: List[str] = Field(..., title="Notes about data quality and potential issues")
