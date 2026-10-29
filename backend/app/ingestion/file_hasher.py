import hashlib
from pathlib import Path
from typing import Union

def compute_file_hash(data_or_path: Union[bytes, Path, str]) -> str:
    sha256 = hashlib.sha256()
    if isinstance(data_or_path, bytes):
        sha256.update(data_or_path)
    else:
        p = Path(data_or_path)
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
    return sha256.hexdigest()

