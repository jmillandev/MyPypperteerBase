import unicodedata

def UnicodeFilter(data):  # para quitar caracteres que no permite mysql
    return (
        "".join(c for c in unicodedata.normalize("NFC", str(data)) if c <= "\uFFFF")
        if isinstance(data, str)
        else data
    )