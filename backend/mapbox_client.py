from __future__ import annotations

import httpx
import os
from typing import Optional, List

from dotenv import load_dotenv

load_dotenv()

class MapboxClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.getenv("MAPBOX_ACCESS_TOKEN")

        if not self.token:
            raise Exception("MAPBOX_ACCESS_TOKEN must be set")

    def geocode_best_match(self, query: str) -> Optional[str]:
        url = "https://api.mapbox.com/search/geocode/v6/forward"
        params = {
            "q": query,
            "access_token": self.token,
            "limit": 1
        }

        try:
            response = httpx.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if "features" in data and data["features"]:
                feature = data["features"][0]
                properties = feature.get("properties", {})
                return properties.get("full_address") or properties.get("place_formatted") or properties.get("name")

        except Exception as e:
            print(f"Error geocoding '{query}': {e}")
            
        return ""

    def geocode_batch(self, queries: List[str]) -> List[Optional[str]]:
        if not queries:
            return []
            
        url = "https://api.mapbox.com/search/geocode/v6/batch"
        params = {"access_token": self.token}

        body = [{"q": q, "limit": 1} for q in queries]
        
        results = [None] * len(queries)
        
        try:
            response = httpx.post(url, params=params, json=body, timeout=30.0)
            response.raise_for_status()
            batch_data = response.json()

            if isinstance(batch_data, dict) and "batch" in batch_data:
                 batch_results = batch_data["batch"]
            elif isinstance(batch_data, list):
                 batch_results = batch_data
            else:
                 print(f"Unexpected batch response format: {type(batch_data)}")
                 batch_results = []

            for i, data in enumerate(batch_results):
                if i < len(results) and "features" in data and data["features"]:
                    feature = data["features"][0]
                    properties = feature.get("properties", {})
                    match = properties.get("full_address") or properties.get("place_formatted") or properties.get("name")
                    results[i] = match

        except Exception as e:
            print(f"Error batch geocoding: {e}")
        return results
