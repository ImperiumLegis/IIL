from pathlib import Path


def resource_dir(name):
    """Resolve wheel resources beside the module or the source checkout's data."""
    package = Path(__file__).resolve().parent
    installed = package / name
    return installed if installed.is_dir() else package.parent / name
