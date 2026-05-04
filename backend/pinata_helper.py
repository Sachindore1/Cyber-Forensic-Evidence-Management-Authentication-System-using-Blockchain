# backend/pinata_helper.py
import os
import requests
import logging

# --------------------------
# Config
# --------------------------
PINATA_JWT = os.getenv("PINATA_JWT", "")

# --------------------------
# IPFS Upload Helper
# --------------------------
def upload_to_pinata(filepath, filename=None):
    """
    Upload a file to Pinata IPFS.

    Args:
        filepath (str): Path to the file to upload.
        filename (str, optional): Custom filename for IPFS. Defaults to basename of filepath.

    Returns:
        str: IPFS CID (just the hash, not the full URI) or empty string if PINATA_JWT not set.

    Raises:
        Exception: If upload fails.
    """
    if not PINATA_JWT:
        logging.warning("PINATA_JWT not set, skipping IPFS upload")
        return ""

    if filename is None:
        filename = os.path.basename(filepath)

    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"

    try:
        with open(filepath, "rb") as f:
            files = {"file": (filename, f)}
            headers = {
                "Authorization": f"Bearer {PINATA_JWT}",
                "pinata_options": '{"cidVersion": 1}'
            }

            logging.info(f"📤 Uploading {filename} to Pinata IPFS...")
            res = requests.post(url, headers=headers, files=files, timeout=60)

        logging.info(f"📥 Pinata response status: {res.status_code}")

        if res.status_code in (200, 201):
            ipfs_hash = res.json().get("IpfsHash")
            if ipfs_hash:
                logging.info(f"✅ Successfully uploaded to IPFS: {ipfs_hash}")
                return ipfs_hash  # Return just the hash, not ipfs:// prefix
            else:
                logging.error("❌ Pinata response missing IpfsHash")
                return ""
        else:
            error_msg = f"❌ Pinata upload failed: {res.status_code} {res.text}"
            logging.error(error_msg)
            # Don't raise exception, just return empty string
            return ""
    except Exception as e:
        logging.error(f"💥 Exception during Pinata upload: {str(e)}")
        # Don't raise exception, just return empty string
        return ""