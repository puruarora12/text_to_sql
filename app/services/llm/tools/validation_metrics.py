from typing import Dict, Any, List, Optional
import time
import json
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import threading

from app import logger
from flask import current_app


class ValidationMetrics:
    """
    Track validation performance and success rates for analysis and optimization.
    """
    
    def __init__(self, db_path: str = "app/data/validation_metrics.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize the metrics database with required tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create validation_results table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS validation_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        query_type TEXT,
                        query_complexity TEXT,
                        validation_strategy TEXT,
                        total_validation_time REAL,
                        steps_completed INTEGER,
                        parallel_steps INTEGER,
                        is_valid BOOLEAN,
                        error_types TEXT,
                        warning_count INTEGER,
                        recommendation_count INTEGER,
                        user_query TEXT,
                        generated_sql TEXT,
                        validation_results TEXT
                    )
                """)
                
                # Create performance_metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS performance_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        metric_type TEXT,
                        metric_name TEXT,
                        metric_value REAL,
                        metadata TEXT
                    )
                """)
                
                # Create validation_step_metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS validation_step_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        step_name TEXT,
                        execution_time REAL,
                        success BOOLEAN,
                        error_message TEXT,
                        parallel BOOLEAN
                    )
                """)
                
                conn.commit()
                logger.info("Validation metrics database initialized")
                
        except Exception as e:
            logger.error(f"Failed to initialize validation metrics database: {e}")
    
    def record_validation_result(
        self,
        query_type: str,
        query_complexity: str,
        validation_strategy: str,
        total_validation_time: float,
        steps_completed: int,
        parallel_steps: int,
        is_valid: bool,
        errors: List[str],
        warnings: List[str],
        recommendations: List[str],
        user_query: str,
        generated_sql: str,
        validation_results: Dict[str, Any]
    ):
        """
        Record a complete validation result for analysis.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO validation_results (
                        query_type, query_complexity, validation_strategy,
                        total_validation_time, steps_completed, parallel_steps,
                        is_valid, error_types, warning_count, recommendation_count,
                        user_query, generated_sql, validation_results
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    query_type,
                    query_complexity,
                    validation_strategy,
                    total_validation_time,
                    steps_completed,
                    parallel_steps,
                    is_valid,
                    json.dumps(errors),
                    len(warnings),
                    len(recommendations),
                    user_query[:500],  # Limit query length
                    generated_sql[:1000],  # Limit SQL length
                    json.dumps(validation_results)
                ))
                
                conn.commit()
                logger.debug(f"Recorded validation result: {query_type}, complexity: {query_complexity}, valid: {is_valid}")
                
        except Exception as e:
            logger.error(f"Failed to record validation result: {e}")
    
    def record_validation_step(
        self,
        step_name: str,
        execution_time: float,
        success: bool,
        error_message: Optional[str] = None,
        parallel: bool = False
    ):
        """
        Record individual validation step performance.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO validation_step_metrics (
                        step_name, execution_time, success, error_message, parallel
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    step_name,
                    execution_time,
                    success,
                    error_message,
                    parallel
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to record validation step: {e}")
    
    def record_performance_metric(
        self,
        metric_type: str,
        metric_name: str,
        metric_value: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record a performance metric for monitoring.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO performance_metrics (
                        metric_type, metric_name, metric_value, metadata
                    ) VALUES (?, ?, ?, ?)
                """, (
                    metric_type,
                    metric_name,
                    metric_value,
                    json.dumps(metadata) if metadata else None
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to record performance metric: {e}")
    
    def get_validation_success_rate(self, days: int = 7) -> Dict[str, Any]:
        """
        Get validation success rate over the specified period.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get overall success rate
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN is_valid THEN 1 ELSE 0 END) as successful,
                        AVG(total_validation_time) as avg_time
                    FROM validation_results 
                    WHERE timestamp >= datetime('now', '-{} days')
                """.format(days))
                
                result = cursor.fetchone()
                total, successful, avg_time = result
                
                success_rate = (successful / total * 100) if total > 0 else 0
                
                # Get success rate by complexity
                cursor.execute("""
                    SELECT 
                        query_complexity,
                        COUNT(*) as total,
                        SUM(CASE WHEN is_valid THEN 1 ELSE 0 END) as successful
                    FROM validation_results 
                    WHERE timestamp >= datetime('now', '-{} days')
                    GROUP BY query_complexity
                """.format(days))
                
                complexity_rates = {}
                for row in cursor.fetchall():
                    complexity, total, successful = row
                    rate = (successful / total * 100) if total > 0 else 0
                    complexity_rates[complexity] = {
                        "total": total,
                        "successful": successful,
                        "success_rate": rate
                    }
                
                # Get success rate by strategy
                cursor.execute("""
                    SELECT 
                        validation_strategy,
                        COUNT(*) as total,
                        SUM(CASE WHEN is_valid THEN 1 ELSE 0 END) as successful,
                        AVG(total_validation_time) as avg_time
                    FROM validation_results 
                    WHERE timestamp >= datetime('now', '-{} days')
                    GROUP BY validation_strategy
                """.format(days))
                
                strategy_rates = {}
                for row in cursor.fetchall():
                    strategy, total, successful, avg_time = row
                    rate = (successful / total * 100) if total > 0 else 0
                    strategy_rates[strategy] = {
                        "total": total,
                        "successful": successful,
                        "success_rate": rate,
                        "avg_time": avg_time
                    }
                
                return {
                    "overall": {
                        "total": total,
                        "successful": successful,
                        "success_rate": success_rate,
                        "avg_validation_time": avg_time
                    },
                    "by_complexity": complexity_rates,
                    "by_strategy": strategy_rates,
                    "period_days": days
                }
                
        except Exception as e:
            logger.error(f"Failed to get validation success rate: {e}")
            return {
                "overall": {"total": 0, "successful": 0, "success_rate": 0, "avg_validation_time": 0},
                "by_complexity": {},
                "by_strategy": {},
                "period_days": days
            }
    
    def get_performance_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get performance metrics over the specified period.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get validation step performance
                cursor.execute("""
                    SELECT 
                        step_name,
                        COUNT(*) as total_executions,
                        AVG(execution_time) as avg_time,
                        SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
                        SUM(CASE WHEN parallel THEN 1 ELSE 0 END) as parallel_executions
                    FROM validation_step_metrics 
                    WHERE timestamp >= datetime('now', '-{} days')
                    GROUP BY step_name
                """.format(days))
                
                step_metrics = {}
                for row in cursor.fetchall():
                    step_name, total, avg_time, successful, parallel = row
                    success_rate = (successful / total * 100) if total > 0 else 0
                    step_metrics[step_name] = {
                        "total_executions": total,
                        "avg_execution_time": avg_time,
                        "success_rate": success_rate,
                        "parallel_executions": parallel
                    }
                
                # Get overall performance metrics
                cursor.execute("""
                    SELECT 
                        metric_name,
                        AVG(metric_value) as avg_value,
                        MIN(metric_value) as min_value,
                        MAX(metric_value) as max_value,
                        COUNT(*) as count
                    FROM performance_metrics 
                    WHERE timestamp >= datetime('now', '-{} days')
                    GROUP BY metric_name
                """.format(days))
                
                performance_metrics = {}
                for row in cursor.fetchall():
                    metric_name, avg_value, min_value, max_value, count = row
                    performance_metrics[metric_name] = {
                        "avg_value": avg_value,
                        "min_value": min_value,
                        "max_value": max_value,
                        "count": count
                    }
                
                return {
                    "step_metrics": step_metrics,
                    "performance_metrics": performance_metrics,
                    "period_days": days
                }
                
        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}")
            return {
                "step_metrics": {},
                "performance_metrics": {},
                "period_days": days
            }
    
    def get_error_analysis(self, days: int = 7) -> Dict[str, Any]:
        """
        Analyze validation errors and their patterns.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get error frequency by type
                cursor.execute("""
                    SELECT error_types, COUNT(*) as count
                    FROM validation_results 
                    WHERE timestamp >= datetime('now', '-{} days') AND is_valid = 0
                    GROUP BY error_types
                    ORDER BY count DESC
                    LIMIT 10
                """.format(days))
                
                error_frequency = {}
                for row in cursor.fetchall():
                    error_types, count = row
                    try:
                        errors = json.loads(error_types)
                        for error in errors:
                            error_frequency[error] = error_frequency.get(error, 0) + count
                    except:
                        error_frequency[error_types] = count
                
                # Get step failure analysis
                cursor.execute("""
                    SELECT 
                        step_name,
                        COUNT(*) as total_failures,
                        GROUP_CONCAT(DISTINCT error_message) as error_messages
                    FROM validation_step_metrics 
                    WHERE timestamp >= datetime('now', '-{} days') AND success = 0
                    GROUP BY step_name
                    ORDER BY total_failures DESC
                """.format(days))
                
                step_failures = {}
                for row in cursor.fetchall():
                    step_name, total_failures, error_messages = row
                    step_failures[step_name] = {
                        "total_failures": total_failures,
                        "error_messages": error_messages.split(',') if error_messages else []
                    }
                
                return {
                    "error_frequency": error_frequency,
                    "step_failures": step_failures,
                    "period_days": days
                }
                
        except Exception as e:
            logger.error(f"Failed to get error analysis: {e}")
            return {
                "error_frequency": {},
                "step_failures": {},
                "period_days": days
            }
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """
        Clean up old metrics data to prevent database bloat.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cutoff_date = datetime.now() - timedelta(days=days_to_keep)
                
                # Clean up old validation results
                cursor.execute("""
                    DELETE FROM validation_results 
                    WHERE timestamp < ?
                """, (cutoff_date,))
                
                # Clean up old step metrics
                cursor.execute("""
                    DELETE FROM validation_step_metrics 
                    WHERE timestamp < ?
                """, (cutoff_date,))
                
                # Clean up old performance metrics
                cursor.execute("""
                    DELETE FROM performance_metrics 
                    WHERE timestamp < ?
                """, (cutoff_date,))
                
                conn.commit()
                logger.info(f"Cleaned up metrics data older than {days_to_keep} days")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")


# Global metrics instance
_metrics_instance = None
_metrics_lock = threading.Lock()

def get_validation_metrics() -> ValidationMetrics:
    """Get the global validation metrics instance."""
    global _metrics_instance
    if _metrics_instance is None:
        with _metrics_lock:
            if _metrics_instance is None:
                db_path = current_app.config.get("VALIDATION_METRICS_DB", "app/data/validation_metrics.db")
                _metrics_instance = ValidationMetrics(db_path)
    return _metrics_instance


# Convenience functions for easy metric recording
def record_validation_result_metric(**kwargs):
    """Record a validation result metric."""
    metrics = get_validation_metrics()
    metrics.record_validation_result(**kwargs)

def record_performance_metric(**kwargs):
    """Record a performance metric."""
    metrics = get_validation_metrics()
    metrics.record_performance_metric(**kwargs)
