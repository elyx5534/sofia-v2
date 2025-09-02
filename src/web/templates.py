from typing import Dict

from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, select_autoescape

env = Environment(
    loader=FileSystemLoader(["sofia_ui/templates", "templates", "src/templates", "ui/templates"]),
    autoescape=select_autoescape(["html", "xml"]),
)


def format_currency(v, symbol="$"):
    try:
        return f"{symbol}{float(v):,.2f}"
    except:
        return f"{symbol}0.00"


env.filters["format_currency"] = format_currency
env.filters["currency"] = format_currency  # alias

templates = Jinja2Templates(env=env)


def render(request, name: str, ctx: Dict):
    return templates.TemplateResponse(name, {"request": request, **ctx})


def get_templates_instance():
    """Get templates instance for compatibility"""
    return templates


def get_resolution_report():
    """Template resolution report for debugging"""
    return {"status": "active", "theme": "glass_dark", "filters": ["format_currency", "currency"]}
