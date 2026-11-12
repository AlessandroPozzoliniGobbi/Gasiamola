"""Client dei dataset. Contratto comune (vedi cache.py):

    fetch(lat, lon, ..., force=False) -> Path   scarica nella cache data/raw/, scrive il .meta.json
    load(lat, lon, ...)  -> pandas.DataFrame    legge SOLO dalla cache (funziona senza rete)
"""
