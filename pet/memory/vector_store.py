import faiss
import numpy as np
from pathlib import Path

INDEX_PATH = Path("data/faiss.index")

class VectorMemory:
    def __init__(self, size=1024):
        self.size = size
        if INDEX_PATH.exists():
            self.index = faiss.read_index(str(INDEX_PATH))
        else:
            self.index = faiss.IndexFlatL2(size)

    def add(self, vector):
        vector = np.array([vector], dtype="float32")
        self.index.add(vector)
        INDEX_PATH.parent.mkdir(exist_ok=True)
        faiss.write_index(self.index, str(INDEX_PATH))

    def search(self, vector, limit=5):
        vector = np.array([vector], dtype="float32")
        return self.index.search(vector, limit)