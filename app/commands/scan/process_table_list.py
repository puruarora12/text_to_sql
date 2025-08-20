from typing import Dict, List
from flask import current_app

from app import logger
from app.core.commands import ReadCommand
from app.errors import ValidationException
from app.services.datastore.duckdb_datastore import DuckDBDatastore
from app.services.vector_store.vector_store_service import VectorStoreService
from app.services.llm.tools.schema_description import describe_table_schema
from app.utils.formatters import get_timestamp

from langfuse.decorators import observe
from uuid import uuid4


class ProcessTableListCommand(ReadCommand):
    """
    Process table list and fetch schema information.
    """
    def __init__(self, database: str = None) -> None:
        self.database = database
        self.datastore = DuckDBDatastore(database=database)

    def validate(self) -> None:
        """
        Validate the command.
        """
        if not self.datastore:
            raise ValidationException("Datastore is required.")
        
        return True
    
    def execute(self) -> Dict[str, Dict]:
        """
        Execute the command.
        """
        logger.debug(
            f'Command {self.__class__.__name__} started for database: {self.database or "in-memory"}.'
        )

        self.validate()

        try:
            # Fetch all tables with their schemas
            tables = self.datastore.get_list_of_tables()
            
            # Create result dictionary
            result = {}
            descriptions = []
            
            for table_info in tables:
                table_name = table_info['table_name']
                schema_name = table_info['table_schema']
                
                # Fetch column details for each table
                columns = self.datastore.get_list_of_columns(
                    table_name=table_name,
                    schema_name=schema_name
                )
                
                # Get sample data for each table
                sample_data = self.datastore.get_sample_data(
                    table_name=table_name, 
                    schema_name=schema_name,
                    limit = 200
                )
                
                # Convert sample data to list of dictionaries
                sample_rows = sample_data.to_dict(orient="records") if not sample_data.empty else []
                
                # Create table entry with schema and column information
                result[table_name] = {
                    'schema': schema_name,
                    'columns': columns,
                    'sample_rows': sample_rows
                }

                # Generate schema description using the tool
                try:
                    # Convert column format to match schema description tool expectations
                    column_schemas = []
                    for col in columns:
                        column_schemas.append({
                            'name': col['column_name'],
                            'type': col['data_type'].lower(),
                            'nullable': col['is_nullable'] == 'YES',
                            'primary_key': False,  # Will be detected by the tool
                            'unique': False,  # Will be detected by the tool
                            'default': None
                        })
                    
                    # Generate schema description
                    schema_description = describe_table_schema(
                        table_name=table_name,
                        column_schemas=column_schemas,
                        example_rows=sample_rows
                    )
                    
                    # Convert schema description to string for vector storage
                    description_text = self._format_schema_description(schema_description)
                    descriptions.append(description_text)
                    
                    logger.debug(f'Generated schema description for table: {table_name}')
                    
                except Exception as e:
                    logger.error(f"Failed to generate schema description for table {table_name}: {e}")
                    # Continue with other tables even if one fails

                logger.debug(f'Processed table: {schema_name}.{table_name} with {len(columns)} columns')
                
            # Save all descriptions to vector database
            if descriptions:
                try:
                    vector_store = VectorStoreService(
                        collection_name="dbschema",
                        index_name="dbschema"
                    )

                    # Generate unique IDs for each description
                    doc_ids = [str(uuid4()) for _ in descriptions]
                    
                    # Add metadata for each description
                    metadata = []
                    for i, table_info in enumerate(tables):
                        if i < len(descriptions):
                            metadata.append({
                                'table_name': table_info['table_name'],
                                'schema_name': table_info['table_schema'],
                                'timestamp': get_timestamp(),
                                'source': 'schema_scan'
                            })
                    logger.info(f'Generated {len(metadata)} metadata for descriptions')
                    vector_store.add_documents(
                        documents=descriptions,
                        metadata=metadata,
                        ids=doc_ids
                    )
                    
                    logger.info(f'Successfully saved {len(descriptions)} schema descriptions to Pinecone vector database')
                    
                except Exception as e:
                    logger.error(f"Failed to save schema descriptions to Pinecone vector database: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch table list: {e}")
            raise ValidationException("Error in fetching table list.")

    def _format_schema_description(self, schema_description) -> str:
        """
        Format the schema description object into a readable text format.
        """
        lines = []
        lines.append(f"Table: {schema_description.table_name}")
        lines.append(f"Description: {schema_description.table_description}")
        lines.append(f"Business Context: {schema_description.business_context}")
        lines.append(f"Total Rows: {schema_description.total_rows}")
        lines.append(f"Total Columns: {schema_description.total_columns}")
        
        lines.append("\nColumns:")
        for col in schema_description.columns:
            lines.append(f"  - {col.column_name} ({col.data_type})")
            if col.is_primary_key:
                lines.append(f"    Primary Key: Yes")
            if col.is_unique:
                lines.append(f"    Unique: Yes")
            if col.is_nullable:
                lines.append(f"    Nullable: Yes")
            if col.min_value and col.max_value:
                lines.append(f"    Range: {col.min_value} to {col.max_value}")
            if col.common_values:
                lines.append(f"    Common values: {', '.join(col.common_values)}")
            if col.pattern_description:
                lines.append(f"    Patterns: {col.pattern_description}")
        
        if schema_description.primary_key_columns:
            lines.append(f"\nPrimary Keys: {', '.join(schema_description.primary_key_columns)}")
        
        if schema_description.foreign_keys:
            lines.append("\nForeign Keys:")
            for fk in schema_description.foreign_keys:
                lines.append(f"  - {fk.column_name} -> {fk.referenced_table}.{fk.referenced_column} ({fk.relationship_type})")
        
        if schema_description.query_recommendations:
            lines.append("\nQuery Recommendations:")
            for rec in schema_description.query_recommendations:
                lines.append(f"  - {rec}")
        
        if schema_description.performance_notes:
            lines.append("\nPerformance Notes:")
            for note in schema_description.performance_notes:
                lines.append(f"  - {note}")
        
        if schema_description.data_quality_notes:
            lines.append("\nData Quality:")
            for note in schema_description.data_quality_notes:
                lines.append(f"  - {note}")
        
        return "\n".join(lines)

    @observe()
    def get_table_count(self) -> int:
        """
        Get the total number of tables in the database.
        """
        try:
            tables = self.datastore.get_list_of_tables()
            return len(tables)
        except Exception as e:
            logger.error(f"Failed to get table count: {e}")
            return 0

    @observe()
    def get_schema_summary(self) -> Dict[str, int]:
        """
        Get a summary of tables per schema.
        """
        try:
            tables = self.datastore.get_list_of_tables()
            schema_summary = {}
            
            for table_info in tables:
                schema_name = table_info['table_schema']
                schema_summary[schema_name] = schema_summary.get(schema_name, 0) + 1
            
            return schema_summary
        except Exception as e:
            logger.error(f"Failed to get schema summary: {e}")
            return {}
