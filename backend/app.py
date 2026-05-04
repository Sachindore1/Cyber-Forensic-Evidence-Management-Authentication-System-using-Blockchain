import os
import io
import sys
from pathlib import Path
import json
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, session
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from flask_cors import CORS
from PIL import Image
import logging
from dotenv import load_dotenv

load_dotenv()

# --------------------------
# Logging
# --------------------------
logging.basicConfig(level=logging.INFO)

# --------------------------
# Add project root to sys.path
# --------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# --------------------------
# Project imports
# --------------------------
try:
    from Blockchain.utils import (
        sha256_file,
        phash_image,
        dhash_image,
        hamming_distance,
        similarity_label,
        similarity_percent
    )
except ImportError:
    raise ImportError("Cannot import 'Blockchain.utils'. Ensure blockchain/ folder has __init__.py and is in PROJECT_ROOT.")

try:
    from backend.pinata_helper import upload_to_pinata as upload_file_to_pinata
except ImportError:
    def upload_file_to_pinata(path, name):
        return ""

# --------------------------
# Config
# --------------------------
# --------------------------
# Config
# --------------------------
NODE_URL = os.getenv("BLOCKCHAIN_NODE_URL", "http://127.0.0.1:5000")
UPLOAD_FOLDER = os.path.join(Path.home(), ".evidence_uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
USERS_JSON = os.path.join(PROJECT_ROOT, "backend", "users.json")

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Session Configuration - FIXED FOR AUTO-LOGOUT ISSUE
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-12345")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_SECURE"] = True  # Set to True in production with HTTPS
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.config["SESSION_REFRESH_EACH_REQUEST"] = True  # Keep session alive on each request

# Enhanced CORS Configuration
CORS(app, 
     supports_credentials=True, 
     origins=[
         "http://localhost:3000", "http://127.0.0.1:3000",
         "http://localhost:8000", "http://127.0.0.1:8000",
         "http://localhost:5500", "http://127.0.0.1:5500",  # Live Server
         "http://localhost:5501", "http://127.0.0.1:5501",  # Live Server alt port
         "file://"
     ],
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     expose_headers=["Content-Type"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     max_age=3600)


# --------------------------
# Load Users
# --------------------------
def load_users():
    try:
        with open(USERS_JSON, "r") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load users.json: {e}")
        return {}
    
def refresh_session():
    """Refresh session to prevent auto-logout"""
    if "user_id" in session:
        session.modified = True
        return True
    return False    

# --------------------------
# Node API Helpers
# --------------------------
def safe_post(url, data):
    try:
        res = requests.post(url, json=data, timeout=10)
        res.raise_for_status()
        return res.json(), res.status_code
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}, 500
    except json.JSONDecodeError:
        return {"error": f"Invalid JSON response from {url}"}, 500

def safe_get(url):
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json(), res.status_code
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {e}"}, 500
    except json.JSONDecodeError:
        return {"error": f"Invalid JSON response from {url}"}, 500

def register_evidence_on_node(evidence_data):
    return safe_post(f"{NODE_URL}/register", evidence_data)

def verify_evidence_on_node(sha256_hash, user_id):
    return safe_post(f"{NODE_URL}/verify/{sha256_hash}", {"user_id": user_id})

def get_chain_from_node():
    return safe_get(f"{NODE_URL}/chain")

def get_officers_from_node():
    return safe_get(f"{NODE_URL}/users")

def transfer_evidence_on_node(data):
    return safe_post(f"{NODE_URL}/transfer", data)

# --------------------------
# Auth Helpers
# --------------------------
def require_auth(f):
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            logging.warning("Unauthorized access attempt - no session found")
            return jsonify({"error": "Unauthorized. Please login first."}), 401
        
        # Refresh session to keep it alive
        refresh_session()
        
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# --------------------------
# Utilities
# --------------------------
def format_iso(ts):
    try:
        return datetime.utcfromtimestamp(float(ts)).isoformat() + "Z" if ts else None
    except Exception:
        return None
    
def get_evidence_by_sha256(sha256):
    """Get specific evidence by SHA256 hash"""
    chain_res, status = get_chain_from_node()
    if status != 200:
        return None
    
    chain = chain_res.get("chain", [])
    for block in chain[1:]:  # Skip genesis block
        ev = block.get("evidence", {})
        if ev.get("sha256") == sha256:
            return ev
    return None

# --------------------------
# Routes
# --------------------------
@app.route("/")
def index():
    return jsonify({"message": "Backend is running"}), 200

# Update the login route to set session properly:
@app.route("/api/login", methods=["POST", "OPTIONS"])
def login():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    data = request.get_json(force=True) or {}
    user_id = data.get("user_id", "").strip()
    password = data.get("password", "").strip()
    
    if not user_id or not password:
        return jsonify({"error": "User ID and password required"}), 400
    
    users = load_users()
    
    if user_id not in users:
        return jsonify({"error": "Invalid credentials"}), 401
    
    user = users[user_id]
    if not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid credentials"}), 401
    
    # Clear any existing session
    session.clear()
    
    # Set new session
    session.permanent = True
    session["user_id"] = user_id
    session["name"] = user["name"]
    session["role"] = user["role"]
    session.modified = True
    
    logging.info(f"User logged in: {user_id} ({user['name']})")
    
    return jsonify({
        "message": "Login successful",
        "user": {
            "user_id": user_id,
            "name": user["name"],
            "role": user["role"]
        }
    }), 200

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200

@app.route("/api/me", methods=["GET"])
@require_auth
def get_current_user():
    return jsonify({
        "user_id": session["user_id"],
        "name": session["name"],
        "role": session["role"]
    }), 200

@app.route("/api/register", methods=["POST", "OPTIONS"])
@require_auth
def register_evidence():
    # Handle OPTIONS request for CORS
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
    
    try:
        if "file" not in request.files:
            return jsonify({"error": "Missing file"}), 400

        file = request.files["file"]
        user_id = session.get("user_id")
        user_name = session.get("name")
        
        # Verify session is still valid
        if not user_id or not user_name:
            logging.error("Session data missing during registration")
            return jsonify({"error": "Session expired. Please login again."}), 401
        
        # Get metadata from form
        case_id = request.form.get("case_id", "").strip()
        evidence_id = request.form.get("evidence_id", "").strip()
        description = request.form.get("description", "").strip()
        
        if not case_id or not evidence_id:
            return jsonify({"error": "Case ID and Evidence ID are required"}), 400
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        
        # Save file
        file.save(filepath)
        logging.info(f"File saved: {filepath}")

        # Read file bytes
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        sha = sha256_file(file_bytes)
        logging.info(f"SHA256 computed: {sha[:16]}...")
        
        # Check for duplicate SHA256
        chain_res, _ = get_chain_from_node()
        if isinstance(chain_res, dict):
            chain = chain_res.get("chain", [])
            for block in chain[1:]:
                if block.get("evidence", {}).get("sha256") == sha:
                    # Clean up file
                    try:
                        os.remove(filepath)
                    except:
                        pass
                    return jsonify({
                        "error": "Evidence already exists in blockchain",
                        "existing_sha256": sha
                    }), 409
        
        # Compute perceptual hashes
        phash = dhash = ""
        try:
            Image.open(io.BytesIO(file_bytes))
            phash = phash_image(file_bytes)
            dhash = dhash_image(file_bytes)
            logging.info(f"Perceptual hashes computed - pHash: {phash[:16]}..., dHash: {dhash[:16]}...")
        except Exception as e:
            logging.warning(f"Could not compute perceptual hashes: {e}")

        # Upload to IPFS
        cid = ""
        try:
            cid_hash = upload_file_to_pinata(filepath, filename)
            if cid_hash:
                cid = f"ipfs://{cid_hash}"
                logging.info(f"✅ IPFS upload successful: {cid}")
            else:
                logging.warning("⚠️ IPFS upload returned empty CID")
        except Exception as e:
            logging.error(f"❌ IPFS upload failed: {e}")

        # Prepare evidence data
        evidence_data = {
            "sha256": sha,
            "phash": phash,
            "dhash": dhash,
            "ipfsCID": cid,
            "uploader": user_id,
            "uploader_name": user_name,
            "case_id": case_id,
            "evidence_id": evidence_id,
            "description": description,
            "filename": filename
        }

        # Register on blockchain
        logging.info(f"Registering evidence on blockchain...")
        response, status = register_evidence_on_node(evidence_data)
        
        # Clean up uploaded file
        try:
            os.remove(filepath)
            logging.info(f"Cleaned up temporary file: {filepath}")
        except Exception as e:
            logging.warning(f"Could not remove temp file: {e}")
        
        # Refresh session before returning
        refresh_session()
        
        logging.info(f"Registration complete with status {status}")
        
        # FIX: Return evidence details in the proper structure that frontend expects
        if status == 201:
            # Create the evidence object that matches frontend expectations
            evidence_obj = {
                "sha256": sha,
                "phash": phash,
                "dhash": dhash,
                "ipfsCID": cid,
                "case_id": case_id,
                "evidence_id": evidence_id,
                "description": description,
                "uploader": user_id,
                "uploader_name": user_name
            }
            
            return jsonify({
                "message": "Evidence registered successfully",
                "block": response,
                "evidence": evidence_obj,  # This is what the frontend is looking for
                "user": {
                    "name": user_name, 
                    "role": session.get("role", "Officer")
                },
                "evidence_details": {
                    "sha256": sha,
                    "phash": phash,
                    "dhash": dhash,
                    "ipfsCID": cid,
                    "case_id": case_id,
                    "evidence_id": evidence_id,
                    "description": description
                },
                "node_id": "backend"
            }), 201
        else:
            return jsonify(response), status
        
    except Exception as e:
        logging.error(f"Registration error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500

@app.route("/api/session-check", methods=["GET"])
def session_check():
    """Check if session is still valid"""
    if "user_id" in session:
        refresh_session()
        return jsonify({
            "valid": True,
            "user": {
                "user_id": session["user_id"],
                "name": session["name"],
                "role": session["role"]
            }
        }), 200
    return jsonify({"valid": False}), 401  

# Add this route to handle evidence search
@app.route("/api/evidence/search", methods=["GET"])
@require_auth
def search_evidence():
    """Search evidence by case ID or evidence ID"""
    case_id = request.args.get("case_id", "").strip().lower()
    evidence_id = request.args.get("evidence_id", "").strip().lower()
    
    if not case_id and not evidence_id:
        return jsonify({"error": "Please provide case_id or evidence_id"}), 400
    
    chain_res, status = get_chain_from_node()
    if status != 200:
        return jsonify({"error": "Failed to fetch chain"}), 500
    
    users_res, _ = get_officers_from_node()
    users_map = users_res or {}
    chain = chain_res.get("chain", [])
    
    results = []
    
    for block in chain[1:]:
        ev = block.get("evidence", {})
        ev_case_id = ev.get("case_id", "").lower()
        ev_evidence_id = ev.get("evidence_id", "").lower()
        
        match_case = case_id in ev_case_id if case_id else True
        match_evidence = evidence_id in ev_evidence_id if evidence_id else True
        
        if match_case and match_evidence:
            officer_name = users_map.get(block.get("officer_id"), {}).get("name", block.get("officer_id"))
            raw_ts = block.get("timestamp")
            iso_ts = format_iso(raw_ts)
            
            evidence_item = {
                "sha256": ev.get("sha256"),
                "cid": ev.get("ipfsCID", ""),
                "case_id": ev.get("case_id", "N/A"),
                "evidence_id": ev.get("evidence_id", "N/A"),
                "description": ev.get("description", ""),
                "filename": ev.get("filename", ""),
                "uploader": officer_name,
                "timestamp": iso_ts,
                "custody_count": len(ev.get("custody", []))
            }
            results.append(evidence_item)
    
    return jsonify({
        "results": results,
        "count": len(results)
    }), 200      


# NEW TRANSFER EVIDENCE ENDPOINT WITH ENHANCED FEATURES
@app.route("/api/transfer-evidence", methods=["POST"])
@require_auth
def transfer_evidence_to_officer():  # ← UNIQUE FUNCTION NAME
    """Transfer evidence to another officer with enhanced features"""
    data = request.get_json(force=True) or {}
    
    required_fields = ["sha256", "to_officer_id"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields: sha256 and to_officer_id"}), 400
    
    sha256 = data["sha256"]
    to_officer_id = data["to_officer_id"]
    from_officer_id = session["user_id"]
    from_officer_name = session["name"]
    
    # Check if target officer exists
    users = load_users()
    if to_officer_id not in users:
        return jsonify({"error": "Target officer not found"}), 404
    
    to_officer_name = users[to_officer_id]["name"]
    
    # Prevent self-transfer
    if from_officer_id == to_officer_id:
        return jsonify({"error": "Cannot transfer evidence to yourself"}), 400
    
    # Include transfer reason
    transfer_data = {
        "sha256": sha256,
        "from": from_officer_id,
        "from_name": from_officer_name,
        "to": to_officer_id,
        "to_name": to_officer_name,
        "reason": data.get("reason", "Case transfer")
    }
    
    response, status = transfer_evidence_on_node(transfer_data)
    return jsonify(response), status

# Add this function to get transfer history
@app.route("/api/transfer-history", methods=["GET"])
@require_auth
def get_transfer_history():
    """Get all transfers made by current officer"""
    officer_id = session["user_id"]
    
    chain_res, status = get_chain_from_node()
    if status != 200:
        return jsonify({"error": "Failed to fetch chain"}), 500
    
    users_res, _ = get_officers_from_node()
    users_map = users_res or {}
    chain = chain_res.get("chain", [])
    
    transfers_made = []
    
    for block in chain[1:]:
        ev = block.get("evidence", {})
        custody = ev.get("custody", [])
        
        for event in custody:
            if (event.get("action") == "Evidence custody transferred" and 
                event.get("from") == officer_id):
                
                officer_name = users_map.get(block.get("officer_id"), {}).get("name", block.get("officer_id"))
                raw_ts = block.get("timestamp")
                iso_ts = format_iso(raw_ts)
                
                transfer_item = {
                    "sha256": ev.get("sha256"),
                    "cid": ev.get("ipfsCID", ""),
                    "case_id": ev.get("case_id", "N/A"),
                    "evidence_id": ev.get("evidence_id", "N/A"),
                    "description": ev.get("description", ""),
                    "filename": ev.get("filename", ""),
                    "transferred_to": event.get("to_name") or event.get("to"),
                    "transferred_at": event.get("time"),
                    "transfer_reason": event.get("reason", "Not specified"),
                    "phash": ev.get("phash", ""),  # Add pHash
                    "dhash": ev.get("dhash", "")   # Add dHash
                }
                transfers_made.append(transfer_item)
    
    # Sort by transfer timestamp (newest first)
    transfers_made.sort(key=lambda x: x.get("transferred_at") or "", reverse=True)
    
    return jsonify(transfers_made), 200

@app.route("/api/my-evidence", methods=["GET"])
@require_auth
def get_my_evidence():
    """Get evidence owned by current officer (both uploaded and transferred)"""
    officer_id = session["user_id"]
    
    chain_res, status = get_chain_from_node()
    if status != 200:
        return jsonify({"error": "Failed to fetch chain"}), 500
    
    users_res, _ = get_officers_from_node()
    users_map = users_res or {}
    chain = chain_res.get("chain", [])
    
    my_evidence = []
    
    for block in chain[1:]:  # Skip genesis block
        ev = block.get("evidence", {})
        current_owner = None
        
        # Determine current owner from custody chain
        custody = ev.get("custody", [])
        if custody:
            # Last custody event determines current owner
            last_event = custody[-1]
            current_owner = last_event.get("to") or last_event.get("officer")
        
        # Include evidence if current user is the owner
        if current_owner == officer_id:
            officer_name = users_map.get(block.get("officer_id"), {}).get("name", block.get("officer_id"))
            raw_ts = block.get("timestamp")
            iso_ts = format_iso(raw_ts)
            
            evidence_item = {
                "sha256": ev.get("sha256"),
                "cid": ev.get("ipfsCID", ""),
                "phash": ev.get("phash", ""),
                "dhash": ev.get("dhash", ""),
                "uploader": ev.get("uploader") or block.get("officer_id"),
                "officer_id": block.get("officer_id"),
                "officer_name": officer_name,
                "timestamp": iso_ts,
                "raw_timestamp": raw_ts,
                "custody": ev.get("custody", []),
                "case_id": ev.get("case_id", "N/A"),
                "evidence_id": ev.get("evidence_id", "N/A"),
                "description": ev.get("description", ""),
                "filename": ev.get("filename", ""),
                "current_owner": current_owner,
                "is_transferred": ev.get("uploader") != officer_id  # True if transferred to current user
            }
            my_evidence.append(evidence_item)
    
    # Sort by timestamp (newest first)
    my_evidence.sort(key=lambda x: x.get("raw_timestamp") or 0, reverse=True)
    
    return jsonify(my_evidence), 200

@app.route("/api/transferred-evidence", methods=["GET"])
@require_auth
def get_transferred_evidence():
    """Get evidence that was transferred to current officer"""
    officer_id = session["user_id"]
    
    chain_res, status = get_chain_from_node()
    if status != 200:
        return jsonify({"error": "Failed to fetch chain"}), 500
    
    users_res, _ = get_officers_from_node()
    users_map = users_res or {}
    chain = chain_res.get("chain", [])
    
    transferred_evidence = []
    
    for block in chain[1:]:  # Skip genesis block
        ev = block.get("evidence", {})
        
        # Check if this evidence was transferred to current officer
        custody = ev.get("custody", [])
        for event in custody:
            if (event.get("action") == "Evidence custody transferred" and 
                event.get("to") == officer_id):
                
                officer_name = users_map.get(block.get("officer_id"), {}).get("name", block.get("officer_id"))
                raw_ts = block.get("timestamp")
                iso_ts = format_iso(raw_ts)
                
                evidence_item = {
                    "sha256": ev.get("sha256"),
                    "cid": ev.get("ipfsCID", ""),
                    "phash": ev.get("phash", ""),
                    "dhash": ev.get("dhash", ""),
                    "uploader": ev.get("uploader") or block.get("officer_id"),
                    "officer_id": block.get("officer_id"),
                    "officer_name": officer_name,
                    "timestamp": iso_ts,
                    "raw_timestamp": raw_ts,
                    "custody": ev.get("custody", []),
                    "case_id": ev.get("case_id", "N/A"),
                    "evidence_id": ev.get("evidence_id", "N/A"),
                    "description": ev.get("description", ""),
                    "filename": ev.get("filename", ""),
                    "transferred_by": event.get("from_name") or event.get("from"),
                    "transferred_at": event.get("time"),
                    "transfer_reason": event.get("reason", "Not specified")
                }
                transferred_evidence.append(evidence_item)
                break
    
    # Sort by transfer timestamp (newest first)
    transferred_evidence.sort(key=lambda x: x.get("transferred_at") or "", reverse=True)
    
    return jsonify(transferred_evidence), 200

@app.route("/api/officers", methods=["GET"])
@require_auth
def get_all_officers():
    """Get list of all officers for transfer dropdown"""
    users = load_users()
    officers_list = []
    
    for user_id, user_data in users.items():
        if user_id != session["user_id"]:  # Exclude current user
            officers_list.append({
                "user_id": user_id,
                "name": user_data["name"],
                "role": user_data["role"]
            })
    
    # Sort by name
    officers_list.sort(key=lambda x: x["name"])
    
    return jsonify(officers_list), 200

@app.route("/api/verify", methods=["POST"])
@require_auth
def verify_evidence():
    data = request.get_json(force=True) or {}
    sha_input = data.get("sha256")
    phash_input = data.get("phash")
    dhash_input = data.get("dhash")
    user_id = session["user_id"]

    # Get all evidence from chain
    users_res, _ = get_officers_from_node()
    users_map = users_res or {}
    chain_res, _ = get_chain_from_node()
    chain = chain_res.get("chain", []) if isinstance(chain_res, dict) else []
    
    exact_matches = []
    high_similarity_matches = []  # For matches > 90% similarity
    
    # Search through all blocks
    for block in chain[1:]:
        ev = block.get("evidence", {})
        stored_sha = ev.get("sha256")
        stored_ph = ev.get("phash")
        stored_dh = ev.get("dhash")
        
        # Calculate individual hash distances
        sha_match = (sha_input == stored_sha) if sha_input else False
        
        # For SHA256: Only consider exact matches as "Identical evidence"
        if sha_match:
            sim_pct = 100.0
            similarity_label = "Identical evidence"
            analysis_note = "SHA256 exact match"
            
            match_data = {
                "sha256": stored_sha,
                "cid": ev.get("ipfsCID", ""),
                "phash": stored_ph,
                "dhash": stored_dh,
                "distance": 0,
                "similarity_percent": sim_pct,
                "similarity": similarity_label,
                "uploader": users_map.get(block.get("officer_id"), {}).get("name", block.get("officer_id")),
                "officer_id": block.get("officer_id"),
                "timestamp": block.get("timestamp"),
                "custody": ev.get("custody", []),
                "case_id": ev.get("case_id", "N/A"),
                "evidence_id": ev.get("evidence_id", "N/A"),
                "description": ev.get("description", ""),
                "filename": ev.get("filename", ""),
                # Add detailed analysis
                "phash_similarity": 100.0,
                "dhash_similarity": 100.0,
                "analysis_note": analysis_note,
                "phash_distance": 0,
                "dhash_distance": 0
            }
            exact_matches.append(match_data)
        
        # For perceptual hashes: Only check if SHA256 doesn't match exactly
        elif phash_input and dhash_input and stored_ph and stored_dh:
            dist_ph = hamming_distance(phash_input, stored_ph)
            dist_dh = hamming_distance(dhash_input, stored_dh)
            
            # Calculate individual similarity percentages
            sim_ph = similarity_percent(dist_ph)
            sim_dh = similarity_percent(dist_dh)
            
            # Use the BEST similarity (highest percentage) among the hashes
            best_sim_pct = max(sim_ph, sim_dh)
            best_distance = min(dist_ph, dist_dh)
            
            # Only include matches with >90% similarity
            if best_sim_pct > 90:
                sim_pct = best_sim_pct
                if sim_pct >= 99:
                    similarity_label = "Nearly identical"
                    analysis_note = f"Very high perceptual match: {best_sim_pct:.2f}%"
                elif sim_pct >= 95:
                    similarity_label = "Highly similar"
                    analysis_note = f"Strong perceptual match: {best_sim_pct:.2f}%"
                else:  # 91-94%
                    similarity_label = "Similar"
                    analysis_note = f"Moderate perceptual match: {best_sim_pct:.2f}%"
                
                match_data = {
                    "sha256": stored_sha,
                    "cid": ev.get("ipfsCID", ""),
                    "phash": stored_ph,
                    "dhash": stored_dh,
                    "distance": best_distance,
                    "similarity_percent": sim_pct,
                    "similarity": similarity_label,
                    "uploader": users_map.get(block.get("officer_id"), {}).get("name", block.get("officer_id")),
                    "officer_id": block.get("officer_id"),
                    "timestamp": block.get("timestamp"),
                    "custody": ev.get("custody", []),
                    "case_id": ev.get("case_id", "N/A"),
                    "evidence_id": ev.get("evidence_id", "N/A"),
                    "description": ev.get("description", ""),
                    "filename": ev.get("filename", ""),
                    # Add detailed analysis
                    "phash_similarity": sim_ph,
                    "dhash_similarity": sim_dh,
                    "analysis_note": analysis_note,
                    "phash_distance": dist_ph,
                    "dhash_distance": dist_dh
                }
                high_similarity_matches.append(match_data)
    
    # Sort each category by similarity (highest first)
    exact_matches.sort(key=lambda x: x["similarity_percent"], reverse=True)
    high_similarity_matches.sort(key=lambda x: x["similarity_percent"], reverse=True)
    
    # Combine matches (exact first, then high similarity)
    all_matches = exact_matches + high_similarity_matches
    
    # Log verification on blockchain (only for best match if any)
    if exact_matches:
        verify_evidence_on_node(exact_matches[0]["sha256"], user_id)
    elif high_similarity_matches:
        verify_evidence_on_node(high_similarity_matches[0]["sha256"], user_id)
    
    logging.info(f"Verification complete: {len(exact_matches)} exact, {len(high_similarity_matches)} high similarity")
    
    return jsonify({
        "exists": bool(all_matches),
        "matches": all_matches,
        "total_matches": len(all_matches),
        "exact_count": len(exact_matches),
        "high_similarity_count": len(high_similarity_matches),
        "verified_by": session["name"],
        "verified_at": datetime.utcnow().isoformat() + "Z"
    })

@app.route("/api/chain", methods=["GET"])
@require_auth
def get_chain():
    res, status = get_chain_from_node()
    return jsonify(res), status

@app.route("/api/users", methods=["GET"])
@require_auth
def get_users():
    res, status = get_officers_from_node()
    return jsonify(res), status

@app.route("/api/all", methods=["GET"])
@require_auth
def get_all_evidence():
    chain_res, status = get_chain_from_node()
    if status != 200:
        return jsonify({"error": chain_res.get("error", "Failed to fetch chain"), "chain": []}), 500

    users_res, _ = get_officers_from_node()
    users_map = users_res or {}
    chain = chain_res.get("chain", [])
    evidence_list = []

    for block in chain[1:]:
        ev = block.get("evidence", {})
        officer_id = block.get("officer_id")
        user_name = users_map.get(officer_id, {}).get("name") if isinstance(users_map, dict) else None
        raw_ts = block.get("timestamp")
        iso_ts = format_iso(raw_ts)
        evidence_list.append({
            "sha256": ev.get("sha256"),
            "cid": ev.get("ipfsCID", ""),
            "phash": ev.get("phash", ""),
            "dhash": ev.get("dhash", ""),
            "uploader": ev.get("uploader") or officer_id,
            "officer_id": officer_id,
            "officer_name": user_name,
            "timestamp": iso_ts,
            "raw_timestamp": raw_ts,
            "custody": ev.get("custody", []),
            "case_id": ev.get("case_id", "N/A"),
            "evidence_id": ev.get("evidence_id", "N/A"),
            "description": ev.get("description", ""),
            "filename": ev.get("filename", "")
        })

    for ev in evidence_list:
        ev["custody"].sort(key=lambda x: x.get("time") or "", reverse=True)

    evidence_list.sort(key=lambda x: x.get("raw_timestamp") or 0, reverse=True)

    return jsonify(evidence_list), 200

@app.route("/api/compute-hashes", methods=["POST"])
@require_auth
def compute_hashes():
    """Compute SHA256, pHash, and dHash for uploaded file without registering it"""
    if "file" not in request.files:
        return jsonify({"error": "Missing file"}), 400

    file = request.files["file"]
    
    # Read file bytes
    file_bytes = file.read()
    
    # Compute SHA256
    sha = sha256_file(file_bytes)
    
    # Try to compute perceptual hashes (only for images)
    phash = dhash = ""
    try:
        Image.open(io.BytesIO(file_bytes))
        phash = phash_image(file_bytes)
        dhash = dhash_image(file_bytes)
    except Exception as e:
        logging.warning(f"Could not compute perceptual hashes: {e}")
    
    return jsonify({
        "sha256": sha,
        "phash": phash,
        "dhash": dhash
    }), 200

@app.route("/api/custody/<sha256>", methods=["GET"])
@require_auth
def get_custody_chain(sha256):
    """Get detailed chain of custody for specific evidence"""
    chain_res, status = get_chain_from_node()
    if status != 200:
        return jsonify({"error": "Failed to fetch chain"}), 500
    
    users_res, _ = get_officers_from_node()
    users_map = users_res or {}
    chain = chain_res.get("chain", [])
    
    for block in chain[1:]:
        ev = block.get("evidence", {})
        if ev.get("sha256") == sha256:
            custody = ev.get("custody", [])
            # Enrich custody with user names
            for entry in custody:
                if entry.get("from"):
                    entry["from_name"] = users_map.get(entry["from"], {}).get("name", entry["from"])
                if entry.get("to"):
                    entry["to_name"] = users_map.get(entry["to"], {}).get("name", entry["to"])
            
            return jsonify({
                "sha256": sha256,
                "cid": ev.get("ipfsCID"),
                "phash": ev.get("phash"),  # Add pHash
                "dhash": ev.get("dhash"),  # Add dHash
                "uploader": users_map.get(block.get("officer_id"), {}).get("name", block.get("officer_id")),
                "custody": custody,
                "case_id": ev.get("case_id", "N/A"),
                "evidence_id": ev.get("evidence_id", "N/A"),
                "description": ev.get("description", "")
            }), 200
    
    return jsonify({"error": "Evidence not found"}), 404

# --------------------------
# Run app
# --------------------------
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  🚀 Starting Blockchain Evidence Backend")
    print("  📡 Host: 0.0.0.0:8000")
    print("  🔗 Blockchain Node: " + NODE_URL)
    print("  📁 Upload Folder: " + UPLOAD_FOLDER)
    print("="*60 + "\n")
    
    # Use debug=False and use_reloader=False to prevent auto-reload issues
    app.run(
        host="0.0.0.0", 
        port=8000, 
        debug=False,           # Keep debug mode for error messages
        use_reloader=False,   # IMPORTANT: Disable auto-reloader to prevent session issues
        threaded=True         # Enable threading for better performance
    )
