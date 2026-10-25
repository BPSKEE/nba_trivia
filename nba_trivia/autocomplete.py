"""Player-name suggestions independent of the answer roster."""
from .modes import normalized


class NameIndex:
    def __init__(self, names):
        self.names = sorted(set(names), key=lambda name: (normalized(name), name))
        self.entries = [(name, normalized(name)) for name in self.names]

    def matches(self, text):
        query = normalized(text)
        if not query:
            return []
        return [name for name, key in self.entries
                if key.startswith(query) or any(word.startswith(query) for word in key.split())]
