from typing import Dict, List, Optional

from pydantic import Field 
from vaul import StructuredOutput


class TableDoc(StructuredOutput):
    """LLM-generated documentation for a database table which contains the table name, display name, description, and columns."""

    table_name: str = Field(..., title="Fully qualified table name, e.g., schema.table or table")
    display_name: str = Field(..., title="Human-friendly display name for the table")
    description: str = Field(..., title="Short description of what the table contains and how it is used")
    columns: Dict[str, str] = Field(
        ..., title="Key-value mapping of column name to a short meaning or type"
    )
    synonyms: Optional[List[str]] = Field(
        default=None, title="Optional synonyms or tags to help retrieval"
    )


