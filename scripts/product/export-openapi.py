from pathlib import Path
import json
from app.main import create_app
from app.config import HttpSettings
from app.contracts.ports import Services
app=create_app(Services(*([None]*7)),HttpSettings())
Path("frontend/openapi.json").write_text(json.dumps(app.openapi(),indent=2)+"\n")
