from pathlib import Path

from fastapi.templating import Jinja2Templates

# Objeto compartido por todos los routers que renderizan HTML.
templates = Jinja2Templates(directory=Path(__file__).parent / "plantillas")
