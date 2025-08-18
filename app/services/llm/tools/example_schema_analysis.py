#!/usr/bin/env python3
"""
Example usage of the schema description tool.

This script demonstrates how to use the describe_table_schema tool
to analyze table schemas and get comprehensive information for querying.
"""

import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from app.services.llm.tools.schema_description import describe_table_schema


def example_users_table():
    """Example analysis of a users table."""
    print("🔍 Analyzing Users Table Schema")
    print("=" * 50)
    
    # Column schemas
    column_schemas = [
        {"name": "id", "type": "integer", "primary_key": True, "nullable": False},
        {"name": "username", "type": "varchar", "nullable": False, "unique": True},
        {"name": "email", "type": "varchar", "nullable": False, "unique": True},
        {"name": "first_name", "type": "varchar", "nullable": True},
        {"name": "last_name", "type": "varchar", "nullable": True},
        {"name": "created_at", "type": "datetime", "nullable": False, "default": "CURRENT_TIMESTAMP"},
        {"name": "updated_at", "type": "datetime", "nullable": True},
        {"name": "is_active", "type": "boolean", "nullable": False, "default": "true"},
        {"name": "role_id", "type": "integer", "nullable": True}
    ]
    
    # Example rows
    example_rows = [
        {
            "id": 1,
            "username": "john_doe",
            "email": "john.doe@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "created_at": "2024-01-15 10:30:00",
            "updated_at": "2024-01-20 14:45:00",
            "is_active": True,
            "role_id": 2
        },
        {
            "id": 2,
            "username": "jane_smith",
            "email": "jane.smith@example.com",
            "first_name": "Jane",
            "last_name": "Smith",
            "created_at": "2024-01-16 09:15:00",
            "updated_at": None,
            "is_active": True,
            "role_id": 1
        },
        {
            "id": 3,
            "username": "bob_wilson",
            "email": "bob.wilson@example.com",
            "first_name": "Bob",
            "last_name": "Wilson",
            "created_at": "2024-01-17 16:20:00",
            "updated_at": "2024-01-18 11:30:00",
            "is_active": False,
            "role_id": 3
        }
    ]
    
    # Analyze schema
    result = describe_table_schema("users", column_schemas, example_rows)
    
    # Print results
    print(f"Table: {result.table_name}")
    print(f"Description: {result.table_description}")
    print(f"Rows: {result.total_rows}, Columns: {result.total_columns}")
    print(f"Business Context: {result.business_context}")
    
    print("\n📊 Column Analysis:")
    for col in result.columns:
        print(f"  {col.column_name} ({col.data_type})")
        print(f"    Primary Key: {col.is_primary_key}")
        print(f"    Unique: {col.is_unique}")
        print(f"    Nullable: {col.is_nullable}")
        if col.min_value and col.max_value:
            print(f"    Range: {col.min_value} to {col.max_value}")
        if col.common_values:
            print(f"    Common values: {col.common_values}")
        if col.pattern_description:
            print(f"    Patterns: {col.pattern_description}")
        print()
    
    print("🔑 Primary Keys:", result.primary_key_columns)
    
    print("\n🔗 Foreign Keys:")
    for fk in result.foreign_keys:
        print(f"  {fk.column_name} -> {fk.referenced_table}.{fk.referenced_column} ({fk.relationship_type})")
    
    print("\n💡 Query Recommendations:")
    for rec in result.query_recommendations:
        print(f"  • {rec}")
    
    print("\n🔗 Common Joins:")
    for join in result.common_joins:
        print(f"  • {join}")
    
    print("\n⚡ Performance Notes:")
    for note in result.performance_notes:
        print(f"  • {note}")
    
    print("\n📈 Data Quality:")
    for note in result.data_quality_notes:
        print(f"  • {note}")


def example_orders_table():
    """Example analysis of an orders table."""
    print("\n\n🛒 Analyzing Orders Table Schema")
    print("=" * 50)
    
    # Column schemas
    column_schemas = [
        {"name": "order_id", "type": "integer", "primary_key": True, "nullable": False},
        {"name": "customer_id", "type": "integer", "nullable": False},
        {"name": "order_date", "type": "datetime", "nullable": False},
        {"name": "total_amount", "type": "decimal", "nullable": False},
        {"name": "status", "type": "varchar", "nullable": False},
        {"name": "shipping_address", "type": "text", "nullable": True},
        {"name": "payment_method", "type": "varchar", "nullable": True},
        {"name": "notes", "type": "text", "nullable": True}
    ]
    
    # Example rows
    example_rows = [
        {
            "order_id": 1001,
            "customer_id": 1,
            "order_date": "2024-01-15 14:30:00",
            "total_amount": 299.99,
            "status": "completed",
            "shipping_address": "123 Main St, City, State 12345",
            "payment_method": "credit_card",
            "notes": "Gift wrapped"
        },
        {
            "order_id": 1002,
            "customer_id": 2,
            "order_date": "2024-01-16 09:15:00",
            "total_amount": 149.50,
            "status": "processing",
            "shipping_address": "456 Oak Ave, City, State 12345",
            "payment_method": "paypal",
            "notes": None
        },
        {
            "order_id": 1003,
            "customer_id": 1,
            "order_date": "2024-01-17 16:45:00",
            "total_amount": 89.99,
            "status": "shipped",
            "shipping_address": "123 Main St, City, State 12345",
            "payment_method": "credit_card",
            "notes": "Express shipping"
        },
        {
            "order_id": 1004,
            "customer_id": 3,
            "order_date": "2024-01-18 11:20:00",
            "total_amount": 599.99,
            "status": "pending",
            "shipping_address": "789 Pine Rd, City, State 12345",
            "payment_method": "bank_transfer",
            "notes": None
        }
    ]
    
    # Analyze schema
    result = describe_table_schema("orders", column_schemas, example_rows)
    
    # Print results
    print(f"Table: {result.table_name}")
    print(f"Description: {result.table_description}")
    print(f"Business Context: {result.business_context}")
    
    print("\n📊 Column Analysis:")
    for col in result.columns:
        print(f"  {col.column_name} ({col.data_type})")
        print(f"    Primary Key: {col.is_primary_key}")
        print(f"    Unique: {col.is_unique}")
        print(f"    Nullable: {col.is_nullable}")
        if col.min_value and col.max_value:
            print(f"    Range: {col.min_value} to {col.max_value}")
        if col.common_values:
            print(f"    Common values: {col.common_values}")
        print()
    
    print("🔑 Primary Keys:", result.primary_key_columns)
    
    print("\n🔗 Foreign Keys:")
    for fk in result.foreign_keys:
        print(f"  {fk.column_name} -> {fk.referenced_table}.{fk.referenced_column} ({fk.relationship_type})")
    
    print("\n💡 Query Recommendations:")
    for rec in result.query_recommendations:
        print(f"  • {rec}")
    
    print("\n📈 Data Quality:")
    for note in result.data_quality_notes:
        print(f"  • {note}")


def example_products_table():
    """Example analysis of a products table."""
    print("\n\n📦 Analyzing Products Table Schema")
    print("=" * 50)
    
    # Column schemas
    column_schemas = [
        {"name": "product_id", "type": "integer", "primary_key": True, "nullable": False},
        {"name": "name", "type": "varchar", "nullable": False},
        {"name": "description", "type": "text", "nullable": True},
        {"name": "price", "type": "decimal", "nullable": False},
        {"name": "category_id", "type": "integer", "nullable": True},
        {"name": "sku", "type": "varchar", "nullable": False, "unique": True},
        {"name": "stock_quantity", "type": "integer", "nullable": False, "default": "0"},
        {"name": "created_at", "type": "datetime", "nullable": False},
        {"name": "is_active", "type": "boolean", "nullable": False, "default": "true"}
    ]
    
    # Example rows
    example_rows = [
        {
            "product_id": 1,
            "name": "Laptop Pro",
            "description": "High-performance laptop for professionals",
            "price": 1299.99,
            "category_id": 1,
            "sku": "LAPTOP-PRO-001",
            "stock_quantity": 25,
            "created_at": "2024-01-01 10:00:00",
            "is_active": True
        },
        {
            "product_id": 2,
            "name": "Wireless Mouse",
            "description": "Ergonomic wireless mouse",
            "price": 49.99,
            "category_id": 2,
            "sku": "MOUSE-WIRELESS-001",
            "stock_quantity": 100,
            "created_at": "2024-01-02 11:00:00",
            "is_active": True
        },
        {
            "product_id": 3,
            "name": "USB Cable",
            "description": "High-speed USB-C cable",
            "price": 19.99,
            "category_id": 2,
            "sku": "CABLE-USB-001",
            "stock_quantity": 0,
            "created_at": "2024-01-03 12:00:00",
            "is_active": False
        }
    ]
    
    # Analyze schema
    result = describe_table_schema("products", column_schemas, example_rows)
    
    # Print results
    print(f"Table: {result.table_name}")
    print(f"Description: {result.table_description}")
    print(f"Business Context: {result.business_context}")
    
    print("\n📊 Column Analysis:")
    for col in result.columns:
        print(f"  {col.column_name} ({col.data_type})")
        print(f"    Primary Key: {col.is_primary_key}")
        print(f"    Unique: {col.is_unique}")
        print(f"    Nullable: {col.is_nullable}")
        if col.min_value and col.max_value:
            print(f"    Range: {col.min_value} to {col.max_value}")
        if col.common_values:
            print(f"    Common values: {col.common_values}")
        print()
    
    print("🔑 Primary Keys:", result.primary_key_columns)
    
    print("\n🔗 Foreign Keys:")
    for fk in result.foreign_keys:
        print(f"  {fk.column_name} -> {fk.referenced_table}.{fk.referenced_column} ({fk.relationship_type})")
    
    print("\n💡 Query Recommendations:")
    for rec in result.query_recommendations:
        print(f"  • {rec}")
    
    print("\n📈 Data Quality:")
    for note in result.data_quality_notes:
        print(f"  • {note}")


def main():
    """Run all examples."""
    print("🎯 Schema Description Tool Examples")
    print("=" * 70)
    
    try:
        example_users_table()
        example_orders_table()
        example_products_table()
        
        print("\n✅ All examples completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
