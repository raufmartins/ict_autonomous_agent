_ASSET_TABLE = [
    ("NQ",  {"tick_size": 0.25, "min_fvg_ticks": 2}),
    ("ES",  {"tick_size": 0.25, "min_fvg_ticks": 2}),
    ("ETH", {"tick_size": 0.01, "min_fvg_ticks": 4}),
    ("BTC", {"tick_size": 0.10, "min_fvg_ticks": 3}),
    ("SOL", {"tick_size": 0.01, "min_fvg_ticks": 4}),
]

_DEFAULT = {"tick_size": 0.01, "min_fvg_ticks": 2}


def get_asset_params(asset: str) -> dict:
    upper = asset.upper()
    for prefix, params in _ASSET_TABLE:
        if upper.startswith(prefix):
            return dict(params)
    return dict(_DEFAULT)
