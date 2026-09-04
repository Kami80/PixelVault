class PetScene:
    def __init__(self):
        self.layers = {"background": [], "objects": [], "pet": [], "effects": [], "ui": []}

    def add(self, layer, obj):
        self.layers.setdefault(layer, []).append(obj)

    def event(self, event):
        return {"event": event, "layers": self.layers}
