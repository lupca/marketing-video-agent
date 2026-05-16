import time
import requests
import json
import sys

API_URL = "http://localhost:9100"

def test_full_flow():
    # 1. Check API health
    try:
        health = requests.get(f"{API_URL}/api/health").json()
        print("[+] API Health:", health)
    except Exception as e:
        print("[-] API is not running correctly:", e)
        sys.exit(1)

    # 2. Submit a Video Review job (using fake data for light load since we just want to test pipeline)
    payload = {
        "job_type": "review",
        "config_data": {
            "metadata": { "project_id": "test_e2e" },
            "assets": {},
            "timeline_script": [], # empty timeline to test if it routes and executes without heavy processing
            "render_settings": {
                "resolution": [1080, 1920],
                "auto_subtitle": False
            }
        }
    }
    
    print("[+] Submitting new video job to API...")
    res = requests.post(f"{API_URL}/api/jobs", json=payload)
    if res.status_code != 200:
        print("[-] Failed to create job:", res.text)
        sys.exit(1)
        
    job_id = res.json()["id"]
    print(f"[+] Job {job_id} created successfully! Status: {res.json()['status']}")

    # 3. Poll for status
    max_retries = 30
    for i in range(max_retries):
        status_res = requests.get(f"{API_URL}/api/jobs/{job_id}").json()
        status = status_res["status"]
        print(f"    [{i+1}/{max_retries}] Job {job_id} status: {status}")
        
        if status in ["SUCCESS", "FAILED"]:
            print(f"\n[!] Job finished with status {status}")
            if status == "SUCCESS":
                print("    Output URL:", status_res.get("result_url"))
            else:
                print("    Error:", status_res.get("error_message"))
            sys.exit(0 if status == "SUCCESS" else 1)
            
        time.sleep(2)
        
    print("[-] Timeout waiting for job to complete.")
    sys.exit(1)

if __name__ == "__main__":
    test_full_flow()
