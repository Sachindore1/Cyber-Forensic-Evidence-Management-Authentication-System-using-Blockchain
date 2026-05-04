# blockchain/block.py
import time
import hashlib
import json

class Block:
    def __init__(self, index, timestamp, evidence, previous_hash, officer_id):
        """
        A single block in the blockchain.
        """
        self.index = index
        self.timestamp = timestamp or time.time()
        self.evidence = evidence   # dict {sha256, phash, dhash, ipfsCID, uploader}
        self.previous_hash = previous_hash
        self.officer_id = officer_id  # officer who uploaded
        self.hash = self.compute_hash()

    def compute_hash(self):
        """
        Creates SHA256 hash of block content.
        """
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "evidence": self.evidence,
            "previous_hash": self.previous_hash,
            "officer_id": self.officer_id
        }, sort_keys=True).encode()

        return hashlib.sha256(block_string).hexdigest()

    def to_dict(self):
        """
        Returns block data as dictionary (useful for API responses).
        """
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "evidence": self.evidence,
            "previous_hash": self.previous_hash,
            "officer_id": self.officer_id,
            "hash": self.hash
        }
