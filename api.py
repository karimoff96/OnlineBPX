import requests
from config import AUTH_URL, AUTH_KEY, HISTORY_URL, logger

class OnlinePBXAPI:
    """
    API client for OnlinePBX
    """
    def __init__(self):
        self.key = None
        self.key_id = None
        self.headers = None
    
    def authenticate(self):
        """
        Authenticate with OnlinePBX API
        Returns:
            bool: Authentication success
        """
        try:
            logger.debug(f"Authenticating with {AUTH_URL}")
            response = requests.post(
                AUTH_URL,
                json={"auth_key": AUTH_KEY},
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"Authentication response status: {data.get('status')}")
            
            if data["status"] == "1":
                self.key = data["data"]["key"]
                self.key_id = data["data"]["key_id"]
                self.headers = {
                    "x-pbx-authentication": f"{self.key_id}:{self.key}"
                }
                logger.info(f"Authentication successful with key_id: {self.key_id[:8]}...")
                return True
            else:
                logger.error(f"Authentication failed: {data}")
                return False
        except Exception as e:
            logger.error(f"Authentication error: {e}", exc_info=True)
            return False
    
    def get_call_details(self, start_time, end_time):
        """
        Get call details for a specific time period
        
        Args:
            start_time (int): Start timestamp
            end_time (int): End timestamp
            
        Returns:
            list: Call details or None on error
        """
        if not self.headers:
            if not self.authenticate():
                return None
        
        try:
            logger.debug(f"Getting call details from {start_time} to {end_time}")
            response = requests.post(
                HISTORY_URL,
                headers=self.headers,
                json={
                    "start_stamp_from": start_time,
                    "start_stamp_to": end_time
                },
                timeout=60
            )
            response.raise_for_status()
            
            data = response.json()
            if data["status"] == "1":
                logger.info(f"Retrieved {len(data['data'])} call records")
                return data["data"]
            else:
                logger.error(f"Failed to get call details: {data}")
                return None
        except Exception as e:
            logger.error(f"Error getting call details: {e}", exc_info=True)
            return None
    
    def download_call_records(self, start_time, end_time):
        """
        Download call records for a specific time period
        
        Args:
            start_time (int): Start timestamp
            end_time (int): End timestamp
            
        Returns:
            str: Download URL or None on error
        """
        if not self.headers:
            if not self.authenticate():
                return None
        
        try:
            logger.debug(f"Requesting download URL for period {start_time} to {end_time}")
            response = requests.post(
                HISTORY_URL,
                headers=self.headers,
                json={
                    "start_stamp_from": start_time,
                    "start_stamp_to": end_time,
                    "download": "1"
                },
                timeout=60
            )
            response.raise_for_status()
            
            data = response.json()
            if data["status"] == "1":
                download_url = data["data"]
                logger.info(f"Got download URL: {download_url}")
                return download_url
            else:
                logger.error(f"Failed to get download URL: {data}")
                return None
        except Exception as e:
            logger.error(f"Error getting download URL: {e}", exc_info=True)
            return None