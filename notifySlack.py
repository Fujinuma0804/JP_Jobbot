# notifySlack.py
import os
import logging
import requests
import time
from dotenv import load_dotenv

load_dotenv()

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
if not SLACK_WEBHOOK_URL:
    raise ValueError("SLACK_WEBHOOK_URL is not set in environment variables")

# Optionally adjust log level via environment or default
logging.basicConfig(level=logging.INFO)

def notify_slack(dtype: str, price: str, title: str, url: str) -> bool:
    """
    Send a Slack alert for a new job.
    Returns True if HTTP 200, otherwise False.
    """
    message = (
        f"{time.strftime('%Y-%m-%d %H:%M:%S')} : <!channel>\n"
        f"*New [{dtype}] job found!* 🎉\n"
        f"*Price:* {price}\n"
        f"*Title:* {title}\n"
        f"*Link:* {url}\n"
        f"----------------------------------------------------------"
    )
    
    print(f" Attempting to send Slack notification:")
    print(f"   Webhook URL: {SLACK_WEBHOOK_URL[:50]}..." if SLACK_WEBHOOK_URL else "   Webhook URL: NOT SET")
    print(f"   Message: {message}")
    
    payload = {"text": message}
    try:
        resp = requests.post(
            SLACK_WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=10
        )
        print(f"   Response status: {resp.status_code}")
        print(f"   Response text: {resp.text}")
        
        if resp.status_code == 200:
            print("✅ Slack notification sent successfully")
            logging.info("✅ Slack notification sent successfully")
            return True
        else:
            print(f"❌ Slack notification failed: {resp.status_code}, {resp.text}")
            logging.error(f"❌ Slack notification failed: {resp.status_code}, {resp.text}")
            return False
    except requests.RequestException as e:
        print(f"❌ Slack notification error: {e}")
        logging.error(f"❌ Slack notification error: {e}")
        return False
