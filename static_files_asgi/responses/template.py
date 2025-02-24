from pathlib import Path

from jinja2 import Environment
from jinja2 import FileSystemLoader
from starlette.templating import Jinja2Templates


def do__filesizeformat(value: int) -> str:
    base = 1024
    if value < base:
        return str(value)

    for suffix in "KMGTPEZY":
        value /= base
        if value < base:
            return f"{round(value)}{suffix}"
    return f"{round(value)}Y"


env = Environment(autoescape=True, loader=FileSystemLoader(Path(__file__).parent.parent / "templates"))
env.filters["_filesizeformat"] = do__filesizeformat

TemplateResponse = Jinja2Templates(env=env).TemplateResponse
