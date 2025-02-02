from google.cloud import bigquery
from google.oauth2 import service_account
from google.api_core import retry
import pandas as pd
import json
from datetime import datetime
import re
from typing import Optional, Dict, List, Any

class ConfigurationManager:
    def __init__(self, key_path=None, credentials=None):
        """Initialize with either a key file path or credentials dict"""
        if credentials:
            self.credentials = credentials
        elif key_path:
            with open(key_path) as f:
                self.credentials = json.load(f)
        else:
            raise ValueError("Either key_path or credentials must be provided")
            
        # Initialize BigQuery client with credentials
        self.client = bigquery.Client.from_service_account_info(self.credentials)
        # self.credentials = service_account.Credentials.from_service_account_file(
        #     key_path,
        #     scopes=["https://www.googleapis.com/auth/bigquery"]
        # )
        # self.client = bigquery.Client(
        #     credentials=self.credentials,
        #     project=self.credentials.project_id
        # )
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
            bigquery.SchemaField("version", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("user_email", "STRING", mode="REQUIRED")  # Added user_email field
        ]
        
        try:
            self.client.get_table(self.table_id)
        except Exception:
            table = bigquery.Table(self.table_id, schema=schema)
            self.client.create_table(table)

    @staticmethod
    def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names to be BigQuery compatible."""
        normalized_df = df.copy()
        for col_name in normalized_df.columns:
            clean_start = re.sub(r"^[^a-zA-Z]+", "", col_name)
            clean_name = re.sub(r"[^0-9a-zA-Z]+", "_", clean_start)
            normalized_df.rename(columns={col_name: clean_name}, inplace=True)
        return normalized_df

    @retry.Retry(predicate=retry.if_exception_type(Exception))
    def save_configuration(self, name: str, description: str, config_data: Dict, user_email: str) -> int:
        """Save a new configuration with user information."""
        try:
            timestamp = int(datetime.now().timestamp())
            
            config_df = pd.DataFrame({
                'id': [timestamp],
                'name': [name],
                'description': [description],
                'config_data': [json.dumps(config_data)],
                'created_at': [datetime.now()],
                'updated_at': [datetime.now()],
                'version': [1],
                'user_email': [user_email]  # Add user email
            })
            
            config_df = self._normalize_column_names(config_df)
            
            job_config = bigquery.LoadJobConfig(
                write_disposition="WRITE_APPEND",
                schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION]
            )
            
            load_job = self.client.load_table_from_dataframe(
                config_df,
                self.table_id,
                job_config=job_config
            )
            load_job.result()
            
            return timestamp
            
        except Exception as e:
            raise Exception(f"Failed to save configuration: {str(e)}")

    @retry.Retry(predicate=retry.if_exception_type(Exception))
    def update_configuration(self, config_id: int, config_data: Dict, user_email: str) -> None:
        """Update an existing configuration with user verification."""
        try:
            # Get current version and verify user ownership
            version_query = f"""
            SELECT version 
            FROM `{self.table_id}`
            WHERE id = {config_id}
            AND user_email = @user_email
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("user_email", "STRING", user_email)
                ]
            )
            
            version_job = self.client.query(version_query, job_config=job_config)
            version_result = version_job.result()
            row = next(version_result, None)
            
            if not row:
                raise Exception("Configuration not found or access denied")
                
            current_version = row.version

            update_query = f"""
            UPDATE `{self.table_id}`
            SET config_data = @config_data,
                updated_at = CURRENT_TIMESTAMP(),
                version = {current_version + 1}
            WHERE id = {config_id}
            AND version = {current_version}
            AND user_email = @user_email
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("config_data", "STRING", json.dumps(config_data)),
                    bigquery.ScalarQueryParameter("user_email", "STRING", user_email)
                ]
            )
            
            update_job = self.client.query(update_query, job_config=job_config)
            update_job.result()
            
            if update_job.num_dml_affected_rows == 0:
                raise Exception("Configuration was modified by another process or access denied")
                
        except Exception as e:
            raise Exception(f"Failed to update configuration: {str(e)}")

    def load_configurations(self, user_email: str) -> List[Dict[str, Any]]:
        """Load all configurations for a specific user."""
        try:
            query = f"""
            SELECT id, name, description, created_at, updated_at, version
            FROM `{self.table_id}`
            WHERE user_email = @user_email
            ORDER BY created_at DESC
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("user_email", "STRING", user_email)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            
            return [dict(row.items()) for row in results]
            
        except Exception as e:
            raise Exception(f"Failed to load configurations: {str(e)}")

    def get_configuration(self, config_id: int, user_email: str) -> Optional[Dict]:
        """Get a specific configuration for a user."""
        try:
            query = f"""
            SELECT config_data
            FROM `{self.table_id}`
            WHERE id = {config_id}
            AND user_email = @user_email
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("user_email", "STRING", user_email)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            row = next(results, None)
            
            return json.loads(row.config_data) if row else None
            
        except Exception as e:
            raise Exception(f"Failed to get configuration: {str(e)}")

    @retry.Retry(predicate=retry.if_exception_type(Exception))
    def delete_configuration(self, config_id: int, user_email: str) -> None:
        """Delete a configuration with user verification."""
        try:
            query = f"""
            DELETE FROM `{self.table_id}`
            WHERE id = {config_id}
            AND user_email = @user_email
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("user_email", "STRING", user_email)
                ]
            )
            
            delete_job = self.client.query(query, job_config=job_config)
            delete_job.result()
            
        except Exception as e:
            raise Exception(f"Failed to delete configuration: {str(e)}")