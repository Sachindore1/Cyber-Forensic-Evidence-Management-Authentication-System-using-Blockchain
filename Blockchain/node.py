from flask import Flask, request, jsonify
from blockchain import Blockchain
from block import Block
import json
import requests
import time
import os
import sys
import threading

# --------------------------
# Configuration
# --------------------------
# Set these environment variables for each node
NODE_HOST = os.getenv("NODE_HOST", "0.0.0.0")
NODE_PORT = int(os.getenv("NODE_PORT", "5000"))
NODE_ID = os.getenv("NODE_ID", "node1")  # Unique ID for each node

# Peer nodes - UPDATE THIS FOR EACH VM
PEER_NODES = os.getenv("PEER_NODES", "").split(",") if os.getenv("PEER_NODES") else []
# Example: PEER_NODES=http://192.168.1.102:5000,http://192.168.1.103:5000

# --------------------------
# Load users (pre-registered)
# --------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USERS_FILE = os.path.join(PROJECT_ROOT, "backend", "users.json")

if os.path.exists(USERS_FILE):
    with open(USERS_FILE, "r") as f:
        USERS = json.load(f)
else:
    USERS = {}

# --------------------------
# Blockchain setup
# --------------------------
blockchain = Blockchain()
peers = set(PEER_NODES)  # Initialize with configured peers

app = Flask(__name__)

# --------------------------
# Auto-sync with peers periodically
# --------------------------
def periodic_sync():
    """Sync with peers every 30 seconds"""
    while True:
        time.sleep(30)
        try:
            print(f"[{NODE_ID}] Running periodic consensus check...")
            # Create application context for the consensus check
            with app.app_context():
                consensus()
        except Exception as e:
            print(f"[{NODE_ID}] Consensus error: {e}")

# Start background sync thread
sync_thread = threading.Thread(target=periodic_sync, daemon=True)
sync_thread.start()

# --------------------------
# Helpers
# --------------------------
def is_valid_user(user_id: str) -> bool:
    return user_id in USERS

def get_user_name(user_id: str) -> str:
    return USERS.get(user_id, {}).get("name", user_id)

def broadcast_to_peers(endpoint, data):
    """Broadcast a new block or transaction to all peers"""
    results = []
    for peer in peers:
        try:
            url = f"{peer}{endpoint}"
            response = requests.post(url, json=data, timeout=5)
            results.append({"peer": peer, "status": response.status_code})
            if response.status_code == 200:
                print(f"[{NODE_ID}] ✅ Broadcast to {peer}: SUCCESS")
            else:
                print(f"[{NODE_ID}] ❌ Broadcast to {peer}: FAILED ({response.status_code})")
                # Try to get error details
                try:
                    error_data = response.json()
                    print(f"[{NODE_ID}] Error details: {error_data.get('error', 'Unknown error')}")
                except:
                    pass
        except Exception as e:
            print(f"[{NODE_ID}] 💥 Failed to broadcast to {peer}: {e}")
            results.append({"peer": peer, "error": str(e)})
    return results

def create_block_from_dict(block_data):
    """Create a Block object from dictionary data with proper hash handling"""
    block = Block(
        index=block_data["index"],
        timestamp=block_data["timestamp"],
        evidence=block_data["evidence"],
        previous_hash=block_data["previous_hash"],
        officer_id=block_data["officer_id"]
    )
    # Use the original hash to ensure consistency
    block.hash = block_data["hash"]
    return block

# --------------------------
# Routes
# --------------------------
@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "message": f"Blockchain Node {NODE_ID} is running!",
        "peers": list(peers),
        "chain_length": len(blockchain.chain),
        "genesis_hash": blockchain.chain[0].hash[:16] + "..." if blockchain.chain else "None"
    }), 200

@app.route("/info", methods=["GET"])
def node_info():
    """Return node information"""
    return jsonify({
        "node_id": NODE_ID,
        "host": NODE_HOST,
        "port": NODE_PORT,
        "peers": list(peers),
        "chain_length": len(blockchain.chain),
        "genesis_hash": blockchain.chain[0].hash if blockchain.chain else "None",
        "users_count": len(USERS)
    }), 200

@app.route("/users", methods=["GET"])
def get_users():
    safe_users = {}
    for uid, data in USERS.items():
        safe_users[uid] = {
            "name": data.get("name"),
            "role": data.get("role")
        }
    return jsonify(safe_users), 200

@app.route("/register", methods=["POST"])
def register_evidence():
    data = request.json or {}
    required_fields = ["sha256", "uploader"]

    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing fields"}), 400

    uploader = data["uploader"].strip()
    if not is_valid_user(uploader):
        return jsonify({"error": "Unauthorized", "known_users": list(USERS.keys())}), 403

    uploader_name = data.get("uploader_name", get_user_name(uploader))

    # IMPROVED: Better custody message
    data["custody"] = [{
        "action": "Evidence registered in blockchain",
        "officer": uploader,
        "officer_name": uploader_name,
        "from": None,
        "to": uploader,
        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    }]

    try:
        new_block = blockchain.add_block(data, officer_id=uploader)
        print(f"[{NODE_ID}] ✅ New block created: #{new_block.index} with hash: {new_block.hash[:16]}...")
        
        # Wait a moment before broadcasting to ensure block is stable
        time.sleep(0.5)
        
        broadcast_data = {"block": new_block.to_dict()}
        print(f"[{NODE_ID}] 📤 Broadcasting block #{new_block.index} to {len(peers)} peers...")
        broadcast_results = broadcast_to_peers("/sync_block", broadcast_data)
        
        return jsonify({
            "message": "Evidence registered successfully",
            "block": new_block.to_dict(),
            "user": {"name": uploader_name, "role": USERS[uploader]["role"]},
            "broadcast_results": broadcast_results,
            "node_id": NODE_ID
        }), 201
    except Exception as e:
        print(f"[{NODE_ID}] 💥 Error registering evidence: {e}")
        return jsonify({"error": str(e)}), 400

@app.route("/sync_block", methods=["POST"])
def sync_block():
    """Receive and add a block from peer"""
    data = request.json or {}
    block_data = data.get("block")
    
    if not block_data:
        return jsonify({"error": "No block data"}), 400
    
    try:
        # Check if block already exists
        existing_block = next((block for block in blockchain.chain if block.index == block_data["index"]), None)
        if existing_block:
            print(f"[{NODE_ID}] ⏭️  Block #{block_data['index']} already exists, skipping")
            return jsonify({"message": "Block already exists", "node_id": NODE_ID}), 200
        
        # Create block object from data with original hash
        new_block = create_block_from_dict(block_data)
        
        # Get our last block
        last_block = blockchain.get_last_block()
        
        print(f"[{NODE_ID}] 🔄 Syncing block #{new_block.index} from peer")
        print(f"[{NODE_ID}]   Our last block: #{last_block.index} with hash: {last_block.hash[:16]}...")
        print(f"[{NODE_ID}]   New block prev_hash: {new_block.previous_hash[:16]}...")
        
        # Check if this is the next logical block
        if new_block.index == last_block.index + 1:
            # Verify the previous hash matches
            if new_block.previous_hash == last_block.hash:
                blockchain.chain.append(new_block)
                print(f"[{NODE_ID}] ✅ Successfully synced block #{new_block.index}")
                return jsonify({"message": "Block synced successfully", "node_id": NODE_ID}), 200
            else:
                print(f"[{NODE_ID}] ❌ Previous hash mismatch for block #{new_block.index}")
                print(f"[{NODE_ID}]   Expected: {last_block.hash[:16]}...")
                print(f"[{NODE_ID}]   Got: {new_block.previous_hash[:16]}...")
                
                # Force chain replacement in next consensus check
                return jsonify({"error": "Previous hash mismatch"}), 400
        else:
            print(f"[{NODE_ID}] ❌ Block index mismatch. Expected: {last_block.index + 1}, Got: {new_block.index}")
            return jsonify({"error": "Block index out of sequence"}), 400
            
    except Exception as e:
        print(f"[{NODE_ID}] 💥 Sync error: {e}")
        return jsonify({"error": f"Sync failed: {str(e)}"}), 400

# Replace the existing /transfer route in node.py with this enhanced version

@app.route("/transfer", methods=["POST"])
def transfer_evidence():
    data = request.json or {}
    sha256 = data.get("sha256")
    from_id = data.get("from")
    to_id = data.get("to")
    from_name = data.get("from_name", get_user_name(from_id))
    reason = data.get("reason", "Case transfer")  # New field for transfer reason
    
    if not sha256 or not from_id or not to_id:
        return jsonify({"error": "Missing fields"}), 400
    
    if not is_valid_user(from_id) or not is_valid_user(to_id):
        return jsonify({"error": "Invalid officer"}), 403
    
    # PREVENT SELF-TRANSFER
    if from_id == to_id:
        return jsonify({"error": "Cannot transfer evidence to yourself"}), 400
    
    to_name = get_user_name(to_id)
    
    for block in blockchain.chain:
        if block.evidence.get("sha256") == sha256:
            custody = block.evidence.setdefault("custody", [])
            custody.append({
                "action": "Evidence custody transferred",
                "officer": from_id,
                "officer_name": from_name,
                "from": from_id,
                "to": to_id,
                "from_name": from_name,
                "to_name": to_name,
                "reason": reason,  # Include transfer reason
                "time": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            })
            
            # Broadcast update to peers
            broadcast_to_peers("/sync_custody", {
                "sha256": sha256,
                "custody_event": custody[-1]
            })
            
            return jsonify({
                "message": "Custody transferred successfully", 
                "block": block.to_dict(),
                "node_id": NODE_ID
            }), 200
    
    return jsonify({"error": "Evidence not found"}), 404

@app.route("/sync_custody", methods=["POST"])
def sync_custody():
    """Sync custody updates from peers"""
    data = request.json or {}
    sha256 = data.get("sha256")
    custody_event = data.get("custody_event")
    
    if not sha256 or not custody_event:
        return jsonify({"error": "Missing data"}), 400
    
    for block in blockchain.chain:
        if block.evidence.get("sha256") == sha256:
            custody = block.evidence.setdefault("custody", [])
            # Avoid duplicates by checking time and officer
            is_duplicate = any(
                event.get("time") == custody_event.get("time") and 
                event.get("officer") == custody_event.get("officer")
                for event in custody
            )
            
            if not is_duplicate:
                custody.append(custody_event)
                print(f"[{NODE_ID}] ✅ Synced custody update for {sha256[:16]}...")
                return jsonify({"message": "Custody synced", "node_id": NODE_ID}), 200
            else:
                print(f"[{NODE_ID}] ⏭️  Custody event already exists, skipping")
                return jsonify({"message": "Custody event already exists", "node_id": NODE_ID}), 200
    
    return jsonify({"error": "Evidence not found"}), 404

@app.route("/verify/<sha256>", methods=["POST"])
def verify_evidence(sha256):
    data = request.json or {}
    user_id = data.get("user_id", "unknown")
    user_name = get_user_name(user_id) if is_valid_user(user_id) else "Unknown"

    for block in blockchain.chain:
        if block.evidence.get("sha256") == sha256:
            custody = block.evidence.setdefault("custody", [])
            custody.append({
                "action": "Evidence integrity verified",
                "officer": user_id,
                "officer_name": user_name,
                "from": None,
                "to": None,
                "time": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            })
            return jsonify({"exists": True, "block": block.to_dict(), "user": {"name": user_name}, "node_id": NODE_ID}), 200
    return jsonify({"exists": False, "message": "Evidence not found"}), 404

@app.route("/chain", methods=["GET"])
def get_chain():
    return jsonify({
        "length": len(blockchain.chain),
        "chain": blockchain.to_list(),
        "node_id": NODE_ID,
        "genesis_hash": blockchain.chain[0].hash if blockchain.chain else "None"
    }), 200

@app.route("/add_peer", methods=["POST"])
def add_peer():
    data = request.json or {}
    peer = data.get("peer")
    if not peer:
        return jsonify({"error": "Peer URL required"}), 400
    peers.add(peer)
    print(f"[{NODE_ID}] ✅ Added peer: {peer}")
    return jsonify({"message": "Peer added", "peers": list(peers), "node_id": NODE_ID}), 201

@app.route("/consensus", methods=["GET"])
def consensus():
    """Replace chain with longest valid chain from peers"""
    global blockchain
    replaced = False
    longest_chain = blockchain.chain
    max_length = len(blockchain.chain)

    for peer in peers:
        try:
            url = f"{peer}/chain"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                peer_data = response.json()
                peer_chain_data = peer_data["chain"]
                peer_length = peer_data["length"]
                
                if peer_length > max_length:
                    print(f"[{NODE_ID}] 🔍 Found longer chain at {peer}: {peer_length} vs our {max_length}")
                    # Rebuild the chain from peer data
                    peer_chain = []
                    for block_data in peer_chain_data:
                        block = create_block_from_dict(block_data)
                        peer_chain.append(block)
                    
                    # Validate the entire peer chain
                    if blockchain.is_chain_valid(peer_chain):
                        longest_chain = peer_chain
                        max_length = peer_length
                        replaced = True
                        print(f"[{NODE_ID}] ✅ Valid longer chain found at {peer}")
                    else:
                        print(f"[{NODE_ID}] ❌ Peer chain from {peer} is invalid")
        except Exception as e:
            print(f"[{NODE_ID}] 💥 Error contacting peer {peer}: {e}")

    if replaced:
        blockchain.chain = longest_chain
        print(f"[{NODE_ID}] 🔄 Chain replaced! New length: {max_length}")

    return jsonify({
        "replaced": replaced,
        "chain_length": len(blockchain.chain),
        "node_id": NODE_ID
    })

# --------------------------
# Run app
# --------------------------
if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  Starting Blockchain Node: {NODE_ID}")
    print(f"  Host: {NODE_HOST}:{NODE_PORT}")
    print(f"  Peers: {list(peers)}")
    print(f"  Genesis Hash: {blockchain.chain[0].hash[:16]}..." if blockchain.chain else "No chain")
    print(f"{'='*60}\n")
    app.run(host=NODE_HOST, port=NODE_PORT, debug=False)