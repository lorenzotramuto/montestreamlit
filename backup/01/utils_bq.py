from google.cloud import bigquery
from google.oauth2 import service_account
from google.api_core import retry
import pandas as pd
import json
from datetime import datetime
import re
from typing import Optional, Dict, List, Any

class ConfigurationManager:
    """Manages Monte Carlo simulation configurations in BigQuery."""
    
    def __init__(self, key_path: str):
        """
        Initialize the configuration manager.
        
        Args:
            key_path: Path to the service account key file
        """
        self.credentials = service_account.Credentials.from_service_account_file(
            key_path,
            scopes=["https://www.googleapis.com/auth/bigquery"]
        )
        self.client = bigquery.Client(
            credentials=self.credentials,
            project=self.credentials.project_id
        )
        self.table_id = "rikkanza.montecarlo.bbs"
        self._ensure_table_exists()
    
    def _ensure_table_exists(self) -> None:
        """Create the configurations table if it doesn't exist."""
        schema = [
            bigquery.SchemaField("id", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("description", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("config_data", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("version", "INTEGER", mode="REQUIRED")
        ]
        
        try:
            self.client.get_table(self.table_id)
        except Exception:
            table = bigquery.Table(self.table_id, schema=schema)
            self.client.create_table(table)

    @staticmethod
    def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize column names to be BigQuery compatible.
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with normalized column names
        """
        normalized_df = df.copy()
        for col_name in normalized_df.columns:
            # Remove special characters except letters at the beginning
            clean_start = re.sub(r"^[^a-zA-Z]+", "", col_name)
            # Replace remaining special characters with underscores
            clean_name = re.sub(r"[^0-9a-zA-Z]+", "_", clean_start)
            normalized_df.rename(columns={col_name: clean_name}, inplace=True)
        return normalized_df

    @retry.Retry(predicate=retry.if_exception_type(Exception))
    def save_configuration(self, name: str, description: str, config_data: Dict) -> int:
        """
        Save a new configuration.
        
        Args:
            name: Configuration name
            description: Configuration description
            config_data: Configuration data dictionary
            
        Returns:
            Configuration ID
            
        Raises:
            Exception: If save operation fails
        """
        try:
            # Generate timestamp for ID
            timestamp = int(datetime.now().timestamp())
            
            # Create DataFrame with configuration data
            config_df = pd.DataFrame({
                'id': [timestamp],
                'name': [name],
                'description': [description],
                'config_data': [json.dumps(config_data)],
                'created_at': [datetime.now()],
                'updated_at': [datetime.now()],
                'version': [1]
            })
            
            # Normalize column names
            config_df = self._normalize_column_names(config_df)
            
            # Configure load job
            job_config = bigquery.LoadJobConfig(
                write_disposition="WRITE_APPEND",
                schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
            )
            
            # Execute load job
            load_job = self.client.load_table_from_dataframe(
                config_df,
                self.table_id,
                job_config=job_config
            )
            load_job.result()  # Wait for job completion
            
            return timestamp
            
        except Exception as e:
            raise Exception(f"Failed to save configuration: {str(e)}")

    @retry.Retry(predicate=retry.if_exception_type(Exception))
    def update_configuration(self, config_id: int, config_data: Dict) -> None:
        """
        Update an existing configuration with optimistic locking.
        
        Args:
            config_id: Configuration ID to update
            config_data: New configuration data
            
        Raises:
            Exception: If update operation fails or version conflict occurs
        """
        try:
            # Get current version
            version_query = f"""
            SELECT version 
            FROM `{self.table_id}`
            WHERE id = {config_id}
            """
            version_job = self.client.query(version_query)
            version_result = version_job.result()
            current_version = next(version_result).version

            # Use query parameters instead of string formatting
            update_query = f"""
            UPDATE `{self.table_id}`
            SET config_data = @config_data,
                updated_at = CURRENT_TIMESTAMP(),
                version = {current_version + 1}
            WHERE id = {config_id}
            AND version = {current_version}
            """
            
            # Configure job with query parameters
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter(
                        "config_data",
                        "STRING",
                        json.dumps(config_data)
                    )
                ]
            )
            
            # Execute update with parameters
            update_job = self.client.query(update_query, job_config=job_config)
            update_job.result()
            
            # Check if update was successful
            if update_job.num_dml_affected_rows == 0:
                raise Exception("Configuration was modified by another process")
                
        except Exception as e:
            raise Exception(f"Failed to update configuration: {str(e)}")

    def load_configurations(self) -> List[Dict[str, Any]]:
        """
        Load all configurations ordered by creation date.
        
        Returns:
            List of configuration dictionaries
            
        Raises:
            Exception: If load operation fails
        """
        try:
            query = f"""
            SELECT id, name, description, created_at, updated_at, version
            FROM `{self.table_id}`
            ORDER BY created_at DESC
            """
            
            query_job = self.client.query(query)
            results = query_job.result()
            
            return [dict(row.items()) for row in results]
            
        except Exception as e:
            raise Exception(f"Failed to load configurations: {str(e)}")

    def get_configuration(self, config_id: int) -> Optional[Dict]:
        """
        Get a specific configuration by ID.
        
        Args:
            config_id: Configuration ID to retrieve
            
        Returns:
            Configuration dictionary or None if not found
            
        Raises:
            Exception: If get operation fails
        """
        try:
            query = f"""
            SELECT config_data
            FROM `{self.table_id}`
            WHERE id = {config_id}
            """
            
            query_job = self.client.query(query)
            results = query_job.result()
            row = next(results, None)
            
            return json.loads(row.config_data) if row else None
            
        except Exception as e:
            raise Exception(f"Failed to get configuration: {str(e)}")

    @retry.Retry(predicate=retry.if_exception_type(Exception))
    def delete_configuration(self, config_id: int) -> None:
        """
        Delete a configuration.
        
        Args:
            config_id: Configuration ID to delete
            
        Raises:
            Exception: If delete operation fails
        """
        try:
            query = f"""
            DELETE FROM `{self.table_id}`
            WHERE id = {config_id}
            """
            
            delete_job = self.client.query(query)
            delete_job.result()
            
        except Exception as e:
            raise Exception(f"Failed to delete configuration: {str(e)}")