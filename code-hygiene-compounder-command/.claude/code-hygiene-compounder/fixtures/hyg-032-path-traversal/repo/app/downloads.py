from pathlib import Path


def resolve_download_path(root, requested):
    return (Path(root) / requested).resolve()
