from contextlib import contextmanager
import base64
from typing import List

import numpy as np

@contextmanager
def session_scope(sessionmaker):
    """Provide a transactional scope around a series of operations."""
    session = sessionmaker()
    try:
        yield session
        session.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def encode_embedding_for_redis(embedding: List[float]) -> str:
    """
    Encode a list of floats into a base64 string for storage in Redis.
    """
   
    # Convert the list to a numpy array
    embedding_vector = np.array(embedding, dtype=np.float64)
    
    # Convert the numpy array to bytes
    vector_bytes = embedding_vector.tobytes()
    
    # Encode the bytes to base64
    encoded_vector = base64.b64encode(vector_bytes)
    
    # Convert the base64 bytes to a string
    return encoded_vector.decode("utf-8")

def decode_embedding_from_redis(encoded_str: str) -> List[float]:
    """
    Decode a base64 string back into a list of floats.
    """

    # Decode the base64 string to bytes
    vector_bytes = base64.b64decode(encoded_str)
    
    # Convert the bytes back to a numpy array
    embedding_vector = np.frombuffer(vector_bytes, dtype=np.float64)
    
    # Convert the numpy array to a list
    return embedding_vector.tolist()