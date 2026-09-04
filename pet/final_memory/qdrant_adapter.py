class QdrantMemoryAdapter:
    def __init__(self, client=None, collection="pixel_memory"):
        self.client=client
        self.collection=collection