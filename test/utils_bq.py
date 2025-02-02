from google.oauth2 import service_account
from google.cloud import bigquery
import requests
import pandas as pd
import json
import re

key_path = "rikkanza.json"
credentials = service_account.Credentials.from_service_account_file(key_path,scopes=["https://www.googleapis.com/auth/bigquery"])
bq_client = bigquery.Client(credentials=credentials,project=credentials.project_id)

project_id = "rikkanza"
database = "montecarlo"
table = "testxxx"
table_id = f"{project_id}.{database}.{table}"  # Full table path

def column_names_normalize(df):
    for col_name in df:
        all_except_letters = re.sub(r"([?!^a-zA-Z]+)", "_", col_name)
        remove_chars_at_beginning = col_name.lstrip(all_except_letters)
        new_col_name = re.sub(r"[^0-9a-zA-Z]+", "_", remove_chars_at_beginning)
        df.rename(columns={col_name: new_col_name}, inplace=True)
    return df




def write_dataframe_to_bigquery(df,how="WRITE_APPEND"):
    """
    how= WRITE_APPEND: Append to existing data
         WRITE_TRUNCATE: Delete existing data
         WRITE_EMPTY: Fail if table exists   
    """
    try:
        job_config = bigquery.LoadJobConfig(
                                            write_disposition= how
                                            # Other options:
                                            # WRITE_TRUNCATE: Delete existing data
                                            # WRITE_EMPTY: Fail if table exists
                                            )
        df_final = column_names_normalize(df)
        # Start the load job with full table path
        job = bq_client.load_table_from_dataframe(
                                                df, 
                                                table_id,  # Use full table path
                                                job_config=job_config
                                                )
        # Wait for job to complete
        job.result()
        print(f"Successfully loaded {len(df)} rows to {table_id}")
        
    except Exception as e:
        print(f"Error writing to BigQuery: {str(e)}")



query = f"""
        SELECT *
        FROM {project_id}.{database}.`{table}`
        
"""

def execute_bigquery_and_get_dataframe():
    request_body = {"query": query, "useLegacySql": False}
    url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{project_id}/queries"

    headers = {"Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
                }

    response = requests.post(url, headers=headers, data=json.dumps(request_body))

    if response.status_code == 200:
        result = response.json()
        schema = result['schema']['fields']
        headers = [field['name'] for field in schema]
        rows = result['rows']
        data = [[cell['v'] for cell in row['f']] for row in rows]
        df = pd.DataFrame(data, columns=headers)
        return df
    else:
        print(f"Errore nella richiesta: {response.status_code}")
        print(response.text)
        return None