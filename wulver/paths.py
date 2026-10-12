from pathlib import Path
import apps

APPS_DIR = Path(apps.__file__).resolve().parent
RESOURCES_DIR = Path(__file__).resolve().parent / 'resources'
