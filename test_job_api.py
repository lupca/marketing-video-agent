import json
import requests

with open("worker_review/input.json", "r") as f:
    config_data = json.load(f)

payload = {
    "job_type": "review",
    "priority": 1,
    "config_data": config_data
}

response = requests.post("http://localhost:8000/api/jobs", json=payload)
print("Status Code:", response.status_code)
try:
    print("Response:", json.dumps(response.json(), indent=2))
except:
    print("Response Text:", response.text)
