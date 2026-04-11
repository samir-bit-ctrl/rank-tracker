import os
import json


def setup_credentials():
    creds_json = os.environ.get("GSC_CREDENTIALS")
    if creds_json:
        with open("credentials.json", "w") as f:
            json.dump(json.loads(creds_json), f)
        print("✅ credentials.json written from environment")
    else:
        print("ℹ️  Using local credentials.json")