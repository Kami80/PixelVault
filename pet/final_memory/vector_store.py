class VectorMemoryStore:
    def __init__(self, backend="pgvector"):
        self.backend=backend

    def add(self, text, embedding, metadata=None):
        return {"stored":True,"backend":self.backend}

    def search(self, embedding, limit=5):
        return []