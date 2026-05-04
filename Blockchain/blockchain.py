# blockchain/blockchain.py
import time
from block import Block

class Blockchain:
    def __init__(self):
        """
        Blockchain initialization with a consistent genesis block.
        """
        self.chain = []
        self.create_genesis_block()

    def create_genesis_block(self):
        """
        Creates the first block in the chain (genesis) with fixed data.
        """
        # Fixed genesis data for consistency across all nodes
        genesis_data = {
            "sha256": "GENESIS",
            "phash": None, 
            "dhash": None,
            "ipfsCID": None,
            "uploader": "system",
            "custody": []
        }
        
        # Use fixed timestamp and hash for consistency
        genesis_block = Block(
            index=0,
            timestamp=0,  # Fixed timestamp
            evidence=genesis_data,
            previous_hash="0",  # Fixed previous hash
            officer_id="system"
        )
        
        # Force a consistent hash calculation
        self.chain.append(genesis_block)

    def get_last_block(self):
        """
        Returns the most recent block in the chain.
        """
        return self.chain[-1]

    def add_block(self, evidence, officer_id):
        """
        Adds a new block with evidence to the chain.
        """
        last_block = self.get_last_block()
        new_block = Block(
            index=last_block.index + 1,
            timestamp=time.time(),  # Use current time for new blocks
            evidence=evidence,
            previous_hash=last_block.hash,
            officer_id=officer_id
        )
        
        if self.is_valid_new_block(new_block, last_block):
            self.chain.append(new_block)
            return new_block
        else:
            raise ValueError("Invalid block, cannot add to chain.")

    def is_valid_new_block(self, new_block, prev_block):
        """
        Checks if a new block is valid before adding.
        """
        if prev_block.index + 1 != new_block.index:
            return False
        if prev_block.hash != new_block.previous_hash:
            return False
        if new_block.hash != new_block.compute_hash():
            return False
        return True

    def is_chain_valid(self, chain=None):
        """
        Validates the entire blockchain.
        """
        if chain is None:
            chain = self.chain
        
        # Check genesis block
        genesis = chain[0]
        if genesis.index != 0 or genesis.previous_hash != "0":
            return False
            
        for i in range(1, len(chain)):
            prev = chain[i - 1]
            curr = chain[i]
            if not self.is_valid_new_block(curr, prev):
                return False
        return True

    def replace_chain(self, new_chain):
        """
        Replaces chain with a longer valid one (consensus).
        """
        if len(new_chain) > len(self.chain) and self.is_chain_valid(new_chain):
            self.chain = new_chain
            return True
        return False

    def to_list(self):
        """
        Returns the blockchain as a list of dicts (for JSON APIs).
        """
        return [block.to_dict() for block in self.chain]