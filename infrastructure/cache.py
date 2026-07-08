from collections import OrderedDict

class LRUCache:
    """Cache LRU con límite de tamaño"""
    def __init__(self, maxsize=2000):
        self.cache = OrderedDict()
        self.maxsize = maxsize

    def get(self, key):
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.maxsize:
            self.cache.popitem(last=False)

    def __contains__(self, key):
        return key in self.cache

    def set_many(self, items):
        for key, value in items.items():
            self.set(key, value)