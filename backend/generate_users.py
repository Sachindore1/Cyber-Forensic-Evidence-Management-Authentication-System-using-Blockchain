"""
Script to generate users.json with hashed passwords.
Run this script to create/update user accounts.
"""

import json
from werkzeug.security import generate_password_hash

# Define users with plain text passwords (change these!)
users_data = {
    "OFF1234567": {
        "name": "Sachin Dore",
        "role": "Investigator",
        "password": "password123"  # Change this!
    },
    "OFF2345678": {
        "name": "Priya Sharma",
        "role": "Investigator",
        "password": "password123"  # Change this!
    },
    "OFF3456789": {
        "name": "Rohit Kumar",
        "role": "Officer",
        "password": "password123"  # Change this!
    },
    "OFF4567890": {
        "name": "Anjali Mehta",
        "role": "Officer",
        "password": "password123"  # Change this!
    }
}

# Generate hashed passwords
hashed_users = {}
for user_id, data in users_data.items():
    hashed_users[user_id] = {
        "name": data["name"],
        "role": data["role"],
        "password_hash": generate_password_hash(data["password"])
    }

# Save to users.json
with open("users.json", "w") as f:
    json.dump(hashed_users, f, indent=2)

print("✅ users.json created successfully!")
print("\n📋 User Accounts:")
for user_id, data in users_data.items():
    print(f"  User ID: {user_id}")
    print(f"  Name: {data['name']}")
    print(f"  Role: {data['role']}")
    print(f"  Password: {data['password']}")
    print()