# Cyber Forensic Evidence Management & Authentication System using Blockchain

> A tamper-proof, decentralized digital evidence management platform built for law enforcement and investigative agencies — powered by a custom blockchain, perceptual hashing, and IPFS storage.

---

## 📖 Table of Contents

- [Overview](#overview)
- [Why This Exists](#why-this-exists)
- [Key Features](#key-features)
- [How It Works](#how-it-works)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Reference](#api-reference)
- [The Blockchain Explained](#the-blockchain-explained)
- [Perceptual Hashing & Fuzzy Matching](#perceptual-hashing--fuzzy-matching)
- [Officer Authentication](#officer-authentication)
- [IPFS Integration via Pinata](#ipfs-integration-via-pinata)
- [Frontend Usage Guide](#frontend-usage-guide)
- [Security Considerations](#security-considerations)
- [Limitations & Future Work](#limitations--future-work)
- [Contributing](#contributing)

---

## Overview

The **Blockchain Evidence Authentication System** is a full-stack application designed to solve one of the most persistent problems in digital forensics: *how do you prove that a piece of digital evidence hasn't been tampered with?*

This system lets verified law enforcement officers register digital evidence files (images, documents, media) onto an immutable blockchain ledger. Each piece of evidence is cryptographically fingerprinted using SHA-256 and perceptual hashing algorithms, then optionally stored on the InterPlanetary File System (IPFS) for decentralized, censorship-resistant persistence.

Anyone — a court, an auditor, a fellow investigator — can later upload the same (or a similar) file and instantly verify whether it matches what was originally registered, who registered it, when, and through whose hands it has passed.

---

## Why This Exists

In traditional evidence management systems, files live on centralized servers. A determined bad actor — or even a simple database mistake — can alter, delete, or fabricate records. Courts increasingly demand provable chain-of-custody documentation, and digital evidence is notoriously easy to manipulate without detection.

This project addresses that gap by:

- **Making tampering visible** — any change to a registered file produces a completely different hash, immediately exposing the modification.
- **Locking evidence metadata permanently** — once a block is added to the chain, it cannot be altered without breaking every subsequent block.
- **Creating an auditable chain of custody** — every handoff between officers is logged and timestamped directly in the blockchain block.
- **Enabling fuzzy matching** — even if a file is slightly compressed, re-exported, or subtly edited, perceptual hashing can flag it as suspicious and surface the original registration.

---

## Key Features

### 🛡️ Tamper-Proof Evidence Registration
Every file is hashed with SHA-256 before anything else happens. This hash acts as the file's unique digital fingerprint — if even a single byte changes, the hash changes completely. This hash is what gets written permanently to the blockchain.

### 🔍 Exact & Fuzzy Verification
- **Exact match**: Upload the same file and instantly know if it's registered, who registered it, and its full history.
- **Fuzzy match**: Using 256-bit perceptual hashing (pHash and dHash), the system can detect visually similar images even if they've been resized, re-compressed, or lightly edited — and report a similarity percentage.

### 📋 Chain of Custody Tracking
When evidence changes hands from one officer to another, the transfer is recorded directly inside the blockchain block for that piece of evidence. Every transfer includes who transferred it, to whom, and the exact timestamp.

### 🌐 Decentralized File Storage
Files are uploaded to IPFS via Pinata, meaning the actual file content is stored on a distributed network rather than a single server. The IPFS Content Identifier (CID) is stored in the blockchain, so you can always retrieve and verify the original file independently.

### 👮 Officer-Gated Access
Only pre-registered officers with valid wallet addresses can submit new evidence or perform transfers. Unauthorized attempts are rejected at the blockchain node level.

### 🌍 Peer-to-Peer Consensus
The blockchain node supports adding peers and running a consensus algorithm — the longest valid chain wins — enabling multi-node deployments where no single machine is a single point of failure.

---

## How It Works

Here's the full lifecycle of a piece of evidence through this system:

```
Officer uploads file via UI
         │
         ▼
Backend (app.py) receives the file
         │
         ├─► Computes SHA-256 hash of raw file bytes
         │
         ├─► Computes pHash (perceptual) + dHash (difference) for images
         │
         ├─► Uploads file to IPFS via Pinata → receives CID
         │
         └─► Sends all metadata to Blockchain Node (node.py)
                   │
                   ▼
          Node verifies officer's wallet address
                   │
                   ▼
          Node creates a new Block containing:
          - sha256, phash, dhash, ipfsCID, uploader
          - custody log (who collected it, when)
          - previous block's hash (linking the chain)
                   │
                   ▼
          Block is appended to the chain
                   │
                   ▼
         Evidence is now permanently registered
```

When someone wants to **verify** evidence later:

```
User uploads file for verification
         │
         ▼
Browser computes SHA-256 locally (no upload needed for exact match)
         │
         ▼
Backend queries blockchain node by SHA-256
         │
         ├─► Exact match found? → Return full block details
         │
         └─► No exact match? → Walk entire chain, compare pHash/dHash
                   │
                   ▼
         Return all fuzzy matches with similarity scores
```

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Browser / UI                      │
│              (index.html + Tailwind CSS)             │
│   Register │ Verify │ Dashboard                      │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP REST
                       ▼
┌─────────────────────────────────────────────────────┐
│              Backend API (app.py)                    │
│              Flask · Port 8000                       │
│                                                      │
│  /api/register   /api/verify   /api/transfer         │
│  /api/chain      /api/officers /api/all              │
│                                                      │
│  ┌──────────────┐   ┌──────────────────────────┐    │
│  │  utils.py    │   │    pinata_helper.py       │    │
│  │  SHA256      │   │    IPFS Upload via JWT    │    │
│  │  pHash/dHash │   └──────────────────────────┘    │
│  │  Hamming Dist│                                    │
│  └──────────────┘                                    │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP REST
                       ▼
┌─────────────────────────────────────────────────────┐
│           Blockchain Node (node.py)                  │
│           Flask · Port 5000                          │
│                                                      │
│  /register  /verify/<sha>  /transfer                 │
│  /chain     /officers      /consensus                │
│                                                      │
│  ┌──────────────┐   ┌──────────────────────────┐    │
│  │ blockchain.py│   │      block.py            │    │
│  │ Chain logic  │   │  Block structure + hash  │    │
│  │ Validation   │   └──────────────────────────┘    │
│  │ Consensus    │                                    │
│  └──────────────┘                                    │
│                                                      │
│  officers/officers.json  ← Wallet → Officer map      │
└─────────────────────────────────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────┐
         │    IPFS via Pinata      │
         │  (Decentralized storage)│
         └─────────────────────────┘
```

---

## Project Structure

```
project-root/
│
├── backend/
│   ├── app.py                  # Main Flask API server (port 8000)
│   ├── pinata_helper.py        # IPFS upload helper using Pinata JWT
│   └── officers.json           # Fallback officer registry
│
├── Blockchain/
│   ├── __init__.py
│   ├── node.py                 # Blockchain node Flask server (port 5000)
│   ├── blockchain.py           # Blockchain class (chain management)
│   ├── block.py                # Block class (structure + hashing)
│   └── utils.py                # Hashing utilities (SHA256, pHash, dHash)
│
├── officers/
│   └── officers.json           # Primary officer registry (wallet → name/role)
│
├── uploads/                    # Temporary local storage for uploaded files
│
└── frontend/
    └── index.html              # Single-page web interface
```

---

## Prerequisites

Make sure you have the following installed before proceeding:

- **Python 3.9+**
- **pip** (Python package manager)
- A **Pinata account** (free tier works) for IPFS uploads — or skip for local-only mode
- A modern web browser (Chrome, Firefox, Edge)

### Python Dependencies

```
flask
flask-cors
requests
Pillow
imagehash
werkzeug
```

Install them all at once:

```bash
pip install flask flask-cors requests Pillow imagehash werkzeug
```

---

## Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/blockchain-evidence-system.git
cd blockchain-evidence-system
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

If you don't have a `requirements.txt` yet, install manually:

```bash
pip install flask flask-cors requests Pillow imagehash werkzeug
```

### 3. Set Up Officers

Edit `officers/officers.json` to add your verified officers. Each entry maps a wallet address to a name and role:

```json
{
  "0xYourWalletAddressHere": {
    "name": "Officer Full Name",
    "role": "Investigator"
  }
}
```

> ⚠️ **Important**: Only wallet addresses listed in this file will be permitted to register or transfer evidence. All others will receive a `403 Unauthorized` response.

### 4. Configure Environment Variables (Optional)

```bash
# For IPFS uploads via Pinata
export PINATA_JWT="your_pinata_jwt_token_here"

# To point the backend at a different blockchain node
export BLOCKCHAIN_NODE_URL="http://127.0.0.1:5000"
```

If `PINATA_JWT` is not set, IPFS upload is silently skipped and evidence is stored on-chain only (no file content persistence).

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PINATA_JWT` | `""` | Pinata JWT for IPFS uploads. Leave blank to disable. |
| `BLOCKCHAIN_NODE_URL` | `http://127.0.0.1:8000` | URL of the blockchain node. |

> 📝 Note: The default `BLOCKCHAIN_NODE_URL` in `app.py` points to port `8000`, but the node itself runs on port `5000`. Make sure these are aligned in your deployment. Typically you'd set `BLOCKCHAIN_NODE_URL=http://127.0.0.1:5000`.

---

## Running the Application

You'll need **two separate terminal windows** — one for the blockchain node and one for the backend API.

### Terminal 1 — Start the Blockchain Node

```bash
cd Blockchain
python node.py
```

You should see:
```
 * Running on http://0.0.0.0:5000
```

### Terminal 2 — Start the Backend API

```bash
cd backend
python app.py
```

You should see:
```
 * Running on http://0.0.0.0:8000
```

### Open the Frontend

Open `frontend/index.html` directly in your browser. No build step or web server needed — it's a plain HTML file that talks to your local backend.

> If you see CORS errors, make sure `flask-cors` is installed and the backend is running. The backend already enables CORS for all origins via `CORS(app)`.

---

## API Reference

All endpoints are served by the **Backend API** (`app.py`) on port 8000, prefixed with `/api`.

---

### `POST /api/register`

Register a new piece of evidence onto the blockchain.

**Request**: `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | ✅ | The evidence file to register |
| `uploader` | String | ✅ | The officer's wallet address |

**Success Response** `201`:
```json
{
  "message": "Evidence registered successfully",
  "block": {
    "index": 1,
    "timestamp": 1718000000.0,
    "evidence": {
      "sha256": "abc123...",
      "phash": "f8e4...",
      "dhash": "3c1a...",
      "ipfsCID": "ipfs://QmXyz...",
      "uploader": "0xb51F60...",
      "custody": [...]
    },
    "previous_hash": "0000...",
    "officer_id": "0xb51F60...",
    "hash": "def456..."
  },
  "officer": { "name": "Sachin Dore", "role": "Investigator" }
}
```

**Error Responses**:
- `400` — Missing file or uploader field
- `403` — Wallet address not in officers registry

---

### `POST /api/verify`

Verify whether a file (or visual hash) exists in the blockchain.

**Request**: `application/json`

```json
{
  "sha256": "abc123...",
  "phash": "f8e4...",
  "dhash": "3c1a..."
}
```

All fields are optional, but at least one should be provided. If `sha256` is given, exact matching is attempted first. If `phash`/`dhash` are given, fuzzy matching is also run against the full chain.

**Success Response** `200`:
```json
{
  "mode": "sha",
  "exists": true,
  "matches": [
    {
      "sha256": "abc123...",
      "cid": "ipfs://QmXyz...",
      "similarity": "Identical evidence",
      "similarity_percent": 100.0,
      "uploader": "Sachin Dore",
      "timestamp": 1718000000.0,
      "custody": [...]
    }
  ]
}
```

---

### `POST /api/transfer`

Transfer custody of a piece of evidence from one officer to another.

**Request**: `application/json`

```json
{
  "sha256": "abc123...",
  "from": "0xb51F60...",
  "to": "0xA12F34..."
}
```

**Success Response** `200`:
```json
{
  "message": "Custody updated",
  "block": { ... }
}
```

---

### `GET /api/chain`

Fetch the entire raw blockchain, including all blocks and evidence.

**Response** `200`:
```json
{
  "length": 5,
  "chain": [ { ...block }, { ...block }, ... ]
}
```

---

### `GET /api/officers`

Fetch all registered officers.

**Response** `200`:
```json
{
  "0xb51F60...": { "name": "Sachin Dore", "role": "Investigator" },
  ...
}
```

---

### `GET /api/all`

Fetch all evidence records with officer names resolved and timestamps formatted — ideal for dashboards.

**Response** `200`: An array of evidence objects, sorted newest first.

---

## The Blockchain Explained

This project implements a **simplified but fully functional blockchain from scratch** — no Ethereum, no Solidity, no external blockchain dependency.

### How a Block is Structured

Each `Block` object contains:

| Field | Description |
|---|---|
| `index` | Sequential block number (0 = genesis) |
| `timestamp` | Unix timestamp of when the block was created |
| `evidence` | Dictionary containing all evidence metadata |
| `previous_hash` | SHA-256 hash of the previous block |
| `officer_id` | Wallet address of the officer who created this block |
| `hash` | SHA-256 hash of this block's contents |

The `hash` field is computed by serializing all other fields as sorted JSON and hashing the result. If anyone tries to change any field in any block — even the timestamp — the hash changes, which breaks the `previous_hash` reference in the next block, and so on in a cascade that makes tampering immediately visible.

### Genesis Block

The chain always starts with a special genesis block (index 0) that contains placeholder evidence (`"GENESIS"`) and whose `previous_hash` is simply `"0"`. This block cannot be altered without invalidating every block that follows it.

### Chain Validation

The `Blockchain.is_chain_valid()` method walks every block and checks:
1. The block's index is exactly one more than the previous block's index.
2. The block's `previous_hash` matches the actual computed hash of the previous block.
3. The block's own `hash` field matches a freshly computed hash of its content.

If any of these checks fail for any block, the entire chain is considered invalid.

---

## Perceptual Hashing & Fuzzy Matching

SHA-256 is perfect for detecting exact file changes, but it's brittle — re-saving a JPEG at slightly different quality produces a completely different SHA-256. That's where perceptual hashing comes in.

### pHash (Perceptual Hash)

pHash works by:
1. Resizing the image to a small fixed size (16×16 = 256 pixels in this implementation).
2. Converting to grayscale.
3. Applying a Discrete Cosine Transform (DCT).
4. Encoding whether each frequency component is above or below the average.

The result is a 256-bit fingerprint that's very stable across minor visual changes — compression artifacts, slight color shifts, small crops.

### dHash (Difference Hash)

dHash is simpler and faster:
1. Resize the image to 17×16.
2. For each row, compare adjacent pixels: is the left pixel brighter than the right?
3. Encode the result as a bitstring.

dHash is particularly good at catching gradual brightness changes and is more robust to horizontal transformations.

### Hamming Distance

To compare two hashes, the system counts how many bits differ between them. For two 256-bit hashes:
- **Distance 0** → Identical (100% similarity)
- **Distance ≤ 5** → Nearly identical (~98%+)
- **Distance ≤ 50** → Possibly similar (80%+)
- **Distance > 100** → Probably different content

The similarity percentage is calculated as: `(1 - distance / 256) * 100`

### Similarity Labels

| Similarity | Label |
|---|---|
| ≥ 99% | Identical evidence |
| ≥ 95% | Nearly identical |
| ≥ 80% | Similar |
| ≥ 60% | Somewhat similar |
| < 60% | Completely different |

Fuzzy search only surfaces matches with **90% similarity or higher** to reduce noise.

---

## Officer Authentication

The system uses a simple but effective wallet-address-based authentication model inspired by how blockchain wallets work in the real world.

Officers are pre-registered in `officers/officers.json` with their Ethereum-style wallet addresses as keys. When an officer submits a registration or transfer request, their wallet address is checked against this registry.

```json
{
  "0xb51F60b208BEDDcDFF87544364dFC78a4B0E5Fa3": {
    "name": "Sachin Dore",
    "role": "Investigator"
  }
}
```

**To add a new officer**, simply add their entry to this JSON file and restart the node. In a production deployment, this would be backed by a database and managed through an admin interface with cryptographic signature verification.

> 🔐 **Production Note**: In a real deployment, officers should cryptographically sign their requests using their private keys, and the node should verify the signature against the public address — not just check if the address appears in a list. The current implementation trusts that the caller knows the wallet address, which is suitable for controlled internal networks but not for public-facing deployments.

---

## IPFS Integration via Pinata

[Pinata](https://pinata.cloud) is a managed IPFS pinning service. When you upload a file through this system:

1. The backend sends the file to Pinata's API using your JWT token.
2. Pinata pins the file to IPFS and returns a **Content Identifier (CID)** — a hash of the file's content that is also its permanent address on IPFS.
3. The CID is stored in the blockchain block as `ipfsCID`.

The file can then be retrieved by anyone with the CID from any IPFS gateway:
```
https://ipfs.io/ipfs/<CID>
```

If `PINATA_JWT` is not configured, the IPFS upload step is silently skipped. All other functionality (blockchain registration, verification, fuzzy matching) continues to work normally — only decentralized file retrieval is unavailable.

---

## Frontend Usage Guide

The web interface (`index.html`) has three sections:

### Register Tab

1. Enter your officer wallet address in the text field (must match an entry in `officers.json`).
2. Select the evidence file from your computer.
3. Click **Register**.
4. On success, you'll see the CID, SHA-256 hash, and a thumbnail if the file is an image.

### Verify Tab

1. Select the file you want to verify (the original or a suspected copy).
2. Click **Verify**.
3. The browser computes the SHA-256 hash locally (the file is not uploaded to the server for verification).
4. Results show all matching evidence with similarity scores, uploader identity, timestamp, and custody history.

### Dashboard Tab

1. Click **Load Dashboard**.
2. See a table of all evidence currently registered on the blockchain, including thumbnails for image evidence.

---

## Security Considerations

- **No private key management**: This system does not handle private keys. Officers are identified solely by their public wallet address. In production, integrate a signing mechanism (e.g., MetaMask, ethers.js).
- **CORS is open**: `CORS(app)` allows requests from any origin. In production, restrict this to your specific frontend domain.
- **In-memory blockchain**: The current blockchain lives entirely in memory and resets when the node restarts. For production, add persistence (SQLite, PostgreSQL, or file-based serialization).
- **Single-node**: While peer discovery exists, a single-node deployment has no real decentralization. Run multiple nodes on different machines for genuine tamper resistance.
- **File uploads**: Uploaded files are saved locally in the `uploads/` folder. Add size limits, file type validation, and periodic cleanup in production.

---

## Limitations & Future Work

| Limitation | Suggested Improvement |
|---|---|
| In-memory chain (resets on restart) | Add SQLite or file-based persistence |
| No cryptographic request signing | Integrate wallet signature verification (ethers.js + secp256k1) |
| Single blockchain node | Deploy multiple nodes with proper peer sync |
| Officers managed via JSON file | Admin UI with database-backed officer management |
| No authentication on API endpoints | Add JWT or session-based auth for the backend API |
| IPFS CID stored but not re-verified | On verify, fetch file from IPFS and re-hash to confirm integrity |
| No support for non-image fuzzy matching | Extend pHash/dHash alternatives for video, audio, and documents |

---

## Contributing

Contributions are welcome! If you'd like to improve this project:

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature-name`.
3. Make your changes with clear commit messages.
4. Open a pull request describing what you've changed and why.

For major changes, please open an issue first to discuss the direction before investing time in implementation.

---

*Built with Flask, custom blockchain logic, PIL, imagehash, and Pinata IPFS — designed for digital forensics, evidence integrity, and chain-of-custody transparency.*
