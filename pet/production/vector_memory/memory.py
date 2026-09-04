class VectorMemory:
    def __init__(self, provider="pgvector"):
        self.provider = provider

    def embed(self, text):
        return {"text": text, "provider": self.provider}

    def retrieve(self, query):
        return []
