import hashlib
from PIL import Image
import imagehash
import io
from datetime import datetime

# --------------------------
# Hashing helpers
# --------------------------

def sha256_file(file_bytes):
    """
    Compute SHA256 hash of a file given in bytes.
    """
    sha = hashlib.sha256()
    sha.update(file_bytes)
    return sha.hexdigest()


def sha256_string(s):
    """
    Compute SHA256 hash of a string.
    """
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


# --------------------------
# Perceptual / Difference Hashing (256-bit)
# --------------------------

def phash_image(file_bytes):
    """
    Compute 256-bit perceptual hash of an image.
    """
    img = Image.open(io.BytesIO(file_bytes))
    return str(imagehash.phash(img, hash_size=16))  # 16x16 = 256-bit


def dhash_image(file_bytes):
    """
    Compute 256-bit difference hash of an image.
    """
    img = Image.open(io.BytesIO(file_bytes))
    return str(imagehash.dhash(img, hash_size=16))  # 16x16 = 256-bit


# --------------------------
# Hamming distance / similarity
# --------------------------

def hamming_distance(hash1, hash2):
    """
    Compute Hamming distance between two 256-bit hash strings (hex format).
    Converts hex strings to binary and compares bit by bit.
    Returns 256 if either hash is None or lengths mismatch.
    """
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 256
    
    try:
        # Convert hex strings to integers, then XOR them
        # Bits that differ will be 1 in the XOR result
        xor_result = int(hash1, 16) ^ int(hash2, 16)
        # Count the number of 1 bits (different bits)
        return bin(xor_result).count('1')
    except (ValueError, AttributeError):
        # Fallback to character comparison if hex conversion fails
        return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))


def similarity_percent(distance, hash_bits=256):
    """
    Convert Hamming distance to similarity percentage.
    """
    return round((1 - distance / hash_bits) * 100, 2)


def similarity_label(distance, hash_bits=256):
    """
    Returns a human-readable similarity label based on Hamming distance.
    Uses percentage thresholds for 256-bit hashes.
    """
    pct = (1 - distance / hash_bits) * 100
    if pct >= 99:
        return "Identical evidence"
    elif pct >= 95:
        return "Nearly identical"
    elif pct >= 80:
        return "Similar"
    elif pct >= 60:
        return "Somewhat similar"
    return "Completely different"


# --------------------------
# Timestamp formatting
# --------------------------

def format_timestamp(ts):
    """
    Convert a Unix timestamp (int/float) into human-readable format.
    """
    try:
        return datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)
