import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class DifyDatasetClient:
    """
    Client for interacting with Dify Datasets (Knowledge Base) API.
    Enables uploading parsed CapCut templates directly into Dify vector databases.
    """
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        # Resolve config from Database or defaults
        self.base_url = base_url or "https://api.dify.ai/v1"
        self.api_key = api_key
        
        # Proactively load settings from PostgreSQL database if keys are not provided
        if not self.api_key:
            try:
                from shared_core.database import SessionLocal
                from shared_core.models import SystemSetting
                with SessionLocal() as db:
                    dify_settings = db.query(SystemSetting).filter(SystemSetting.key == "dify_settings").first()
                    if dify_settings and dify_settings.value:
                        self.base_url = dify_settings.value.get("base_url") or self.base_url
                        self.api_key = dify_settings.value.get("api_key")
                        logger.info("DifyDatasetClient: Loaded settings from PostgreSQL database successfully.")
            except Exception as e:
                logger.warning(f"DifyDatasetClient: Failed to fetch DB config: {e}. Falling back to default.")

    def upload_document_by_text(self, dataset_id: str, name: str, text: str) -> Dict[str, Any]:
        """
        Uploads a markdown template summary to a Dify Knowledge Base dataset.
        Using Dify API endpoint: POST /v1/datasets/{dataset_id}/document/create-by-text
        """
        if not self.api_key:
            raise ValueError("Dify Dataset API Key is not configured. Please set it in CapCut Settings.")
            
        url = f"{self.base_url.rstrip('/')}/datasets/{dataset_id}/document/create-by-text"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "name": name,
            "text": text,
            "indexing_technique": "high_quality",
            "process_rule": {
                "mode": "automatic"
            }
        }
        
        logger.info(f"DifyDatasetClient: Sending document '{name}' to Dify Dataset {dataset_id}...")
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        
        try:
            resp_json = resp.json()
        except Exception:
            raise ValueError(f"Dify returned invalid non-JSON response (HTTP {resp.status_code}): {resp.text[:200]}")
            
        if resp.status_code != 200:
            error_msg = resp_json.get("error_msg") or resp_json.get("message") or resp.text
            raise ValueError(f"Dify API error (HTTP {resp.status_code}): {error_msg}")
            
        logger.info(f"DifyDatasetClient: Successfully ingested document. Dify Document ID: {resp_json.get('document', {}).get('id')}")
        return resp_json
