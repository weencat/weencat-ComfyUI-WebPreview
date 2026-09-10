import os
import json
from server import PromptServer
from aiohttp import web

from .web_preview_node import WebPreviewNode
from .web_live_sampler_node import WebLiveSamplerNode

routes = PromptServer.instance.routes

@routes.get("/web_preview/channels")
async def get_channels(request):
    storage = getattr(PromptServer.instance, "web_preview_data", {})
    channels = list(storage.keys())
    return web.json_response({"channels": channels})

@routes.get("/web_preview/image")
@routes.get("/web_preview/image/{path_name:.*}")
async def get_latest_image(request):
    path_name = request.match_info.get("path_name", "").strip()
    storage = getattr(PromptServer.instance, "web_preview_data", {})
    
    if not storage:
        return web.Response(status=404, text="No image")
        
    entry = storage.get(path_name) if path_name else next(reversed(storage.values()), None)
    if entry is None or "image" not in entry:
        return web.Response(status=404, text="No image")
    return web.Response(body=entry["image"], content_type=entry.get("mime_type", "image/png"))

@routes.get("/web_preview/meta")
@routes.get("/web_preview/meta/{path_name:.*}")
async def get_latest_metadata(request):
    path_name = request.match_info.get("path_name", "").strip()
    storage = getattr(PromptServer.instance, "web_preview_data", {})
    
    if not storage:
        return web.Response(status=404, text="No metadata")
        
    entry = storage.get(path_name) if path_name else next(reversed(storage.values()), None)
    if entry is None or "metadata" not in entry:
        return web.Response(status=404, text="No metadata")
    return web.json_response(entry["metadata"])

@routes.get("/web_preview/locales/{lang}")
async def get_locale(request):
    lang = request.match_info.get("lang", "zh_cn").lower()
    current_dir = os.path.dirname(os.path.abspath(__file__))
    locale_path = os.path.join(current_dir, "web", "locales", f"{lang}.json")
    if not os.path.exists(locale_path):
        return web.Response(status=404, text="Locale not found")
    with open(locale_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return web.json_response(data)

@routes.get("/web_preview/viewer")
async def get_viewer(request):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(current_dir, "web", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return web.Response(text=html_content, content_type="text/html")


NODE_CLASS_MAPPINGS = {
    "WebPreviewNode": WebPreviewNode,
    "WebLiveSamplerNode": WebLiveSamplerNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "WebPreviewNode": "Web Live Preview",
    "WebLiveSamplerNode": "Web Live KSampler"
}

WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]