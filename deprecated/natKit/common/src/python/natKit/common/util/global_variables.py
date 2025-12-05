__globals = {}

def register(key, value):
    __globals[key] = value

def lookup(key):
    return __globals[key]
