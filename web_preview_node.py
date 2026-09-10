import torch
import numpy as np
from PIL import Image
import io
import time
from server import PromptServer

def parse_workflow_metadata(prompt_dict):
    meta = {
        "model_name": "",
        "seed": "Auto",
        "steps": "Auto",
        "cfg": "Auto",
        "sampler_name": "Auto",
        "scheduler": "",
        "positive": "",
        "negative": ""
    }
    if not isinstance(prompt_dict, dict):
        return meta

    ksampler_node = None
    for node_id, node in prompt_dict.items():
        class_type = node.get("class_type", "")
        if "KSampler" in class_type or "WebLiveSamplerNode" in class_type:
            ksampler_node = node
            break

    if ksampler_node:
        inputs = ksampler_node.get("inputs", {})
        meta["seed"] = inputs.get("seed", inputs.get("noise_seed", "Auto"))
        meta["steps"] = inputs.get("steps", "Auto")
        meta["cfg"] = inputs.get("cfg", "Auto")
        meta["sampler_name"] = inputs.get("sampler_name", "Auto")
        meta["scheduler"] = inputs.get("scheduler", "")

        pos_link = inputs.get("positive")
        if isinstance(pos_link, list) and len(pos_link) > 0:
            pos_node = prompt_dict.get(str(pos_link[0]), {})
            if "CLIPTextEncode" in pos_node.get("class_type", ""):
                meta["positive"] = pos_node.get("inputs", {}).get("text", "")

        neg_link = inputs.get("negative")
        if isinstance(neg_link, list) and len(neg_link) > 0:
            neg_node = prompt_dict.get(str(neg_link[0]), {})
            if "CLIPTextEncode" in neg_node.get("class_type", ""):
                meta["negative"] = neg_node.get("inputs", {}).get("text", "")

    for node_id, node in prompt_dict.items():
        class_type = node.get("class_type", "")
        if any(loader in class_type for loader in ["CheckpointLoader", "UNETLoader", "LoadCheckPoint"]):
            inputs = node.get("inputs", {})
            meta["model_name"] = inputs.get("ckpt_name", inputs.get("unet_name", ""))
            if meta["model_name"]:
                break

    return meta


class WebPreviewNode:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "image_name": ("STRING", {
                    "default": "最终成图",
                    "tooltip": "该成图在网页下拉菜单中的名字（例如：基础成图、高清放大、修脸结果等）。"
                }),
            },
            "optional": {
                "positive_override": ("STRING", {"multiline": True, "default": ""}),
                "negative_override": ("STRING", {"multiline": True, "default": ""}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "process_image"
    CATEGORY = "📡WebPreview"
    OUTPUT_NODE = True 

    @classmethod
    def IS_CHANGED(s, images, **kwargs):
        return float("NaN")

    def process_image(self, images, image_name="最终成图", positive_override="", negative_override="", prompt=None, extra_pnginfo=None):
        clean_name = str(image_name).strip() or "最终成图"
        
        image = images[0]
        i = 255. * image.cpu().numpy()
        img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
        
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", compress_level=4)
        
        metadata = parse_workflow_metadata(prompt)
        metadata["width"] = img.width
        metadata["height"] = img.height
        metadata["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        metadata["status"] = "Completed"
        
        if positive_override.strip(): metadata["positive"] = positive_override.strip()
        if negative_override.strip(): metadata["negative"] = negative_override.strip()
            
        if not hasattr(PromptServer.instance, "web_preview_data"):
            PromptServer.instance.web_preview_data = {}
            
        PromptServer.instance.web_preview_data[clean_name] = {
            "image": buffer.getvalue(),
            "mime_type": "image/png",
            "metadata": metadata
        }
        
        print(f"\033[92m[WebPreview] 成图 [{clean_name}] 已存入 ({img.width}x{img.height})\033[0m")
        return (images,)