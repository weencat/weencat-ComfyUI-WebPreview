import torch
import numpy as np
from PIL import Image
import io
import time
import comfy.sample
import comfy.samplers
import comfy.model_management
import comfy.utils
from server import PromptServer


def latent_to_pil(latent_tensor, vae=None, previewer=None):
    """辅助函数：兼容 4D 图像与 5D 视频/时序 Latent 的解码转换"""
    if latent_tensor is None:
        return None

    # 核心增强 1：兼容 Anima/Cosmos/Wan 等 5 维视频潜空间 [B, C, T, H, W] -> 提取第 1 帧预览
    if len(latent_tensor.shape) == 5:
        latent_tensor = latent_tensor[:, :, 0, :, :]

    # 方式 1: VAE 解码
    if vae is not None:
        try:
            with torch.no_grad():
                decoded = vae.decode(latent_tensor)
                # 处理 VAE 解码可能产生的 5 维输出
                if len(decoded.shape) == 5:
                    decoded = decoded[:, 0, :, :, :]
                if len(decoded.shape) == 4:
                    i = 255. * decoded[0].cpu().numpy()
                    return Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
        except Exception:
            pass

    # 方式 2: 使用 ComfyUI 原生快速预览器
    if previewer is not None:
        try:
            img = previewer.decode_latent_to_preview(latent_tensor)
            if img is not None:
                return img
        except Exception:
            pass

    # 方式 3: 快速线性 RGB 投影兜底
    try:
        l = latent_tensor[0].detach().cpu()
        if l.shape[0] >= 4:
            weights = torch.tensor([
                [ 0.298,  0.207,  0.208],
                [ 0.187,  0.286,  0.173],
                [-0.158,  0.189,  0.264],
                [-0.184, -0.271, -0.473]
            ])
            rgb = torch.einsum("chw,ck->hwk", l[:4], weights)
            rgb = (rgb + 0.5).clamp(0, 1) * 255.0
            return Image.fromarray(rgb.numpy().astype(np.uint8))
    except Exception:
        pass

    return None


class WebLiveSamplerNode:
    """实时过程采样器：兼容 2D 图像与 3D/5D 视频扩散模型"""
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": ("MODEL",),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "cfg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS, ),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS, ),
                "positive": ("CONDITIONING", ),
                "negative": ("CONDITIONING", ),
                "latent_image": ("LATENT", ),
                "denoise": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "preview_rate": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1, "tooltip": "实时预览刷新步长。\n1=每步刷新（最流畅）\n2~3=每2~3步刷新（更省显卡算力且生图更快）。"}),
            },
            "optional": {
                "vae": ("VAE", ),
            }
        }

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent",)
    FUNCTION = "sample_live"
    CATEGORY = "📡WebPreview"

    def sample_live(self, model, seed, steps, cfg, sampler_name, scheduler, positive, negative, latent_image, denoise=1.0, preview_rate=1, vae=None):
        clean_path = "default"
        device = comfy.model_management.get_torch_device()
        
        # 核心修复 2：自动对齐 Latent 通道数与维度（将 4D 空潜空间扩展为 Anima/Cosmos 所需的 5D）
        latent = latent_image
        latent_tensor = latent["samples"]
        latent_tensor = comfy.sample.fix_empty_latent_channels(model, latent_tensor)

        # 核心修复 3：正确获取批次索引并生成对应维度的初始噪声
        batch_inds = latent.get("batch_index", None)
        noise = comfy.sample.prepare_noise(latent_tensor, seed, batch_inds)
        noise_mask = latent.get("noise_mask", None)

        # 获取原生预览回调，确保原生 ComfyUI 进度条同步更新
        preview_callback = None
        previewer = None
        try:
            import latent_preview
            preview_callback = latent_preview.prepare_callback(model, steps)
            previewer = latent_preview.get_previewer(device, model.model.latent_format)
        except Exception:
            pass

        def step_callback(step, x0, x, total_steps):
            # 执行原生 UI 回调
            if preview_callback is not None:
                try:
                    preview_callback(step, x0, x, total_steps)
                except Exception:
                    pass

            if step % preview_rate == 0 or step == total_steps - 1:
                pil_img = latent_to_pil(x0, vae=vae, previewer=previewer)
                if pil_img is not None:
                    buf = io.BytesIO()
                    pil_img.save(buf, format="JPEG", quality=80)
                    
                    if not hasattr(PromptServer.instance, "web_preview_data"):
                        PromptServer.instance.web_preview_data = {}
                        
                    meta = {
                        "seed": seed,
                        "steps": f"{step + 1}/{total_steps}",
                        "cfg": cfg,
                        "sampler_name": sampler_name,
                        "scheduler": scheduler,
                        "width": pil_img.width,
                        "height": pil_img.height,
                        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                        "status": f"Sampling: Step {step + 1}/{total_steps}"
                    }
                    
                    PromptServer.instance.web_preview_data[clean_path] = {
                        "image": buf.getvalue(),
                        "mime_type": "image/jpeg",
                        "metadata": meta
                    }

        disable_pbar = not comfy.utils.PROGRESS_BAR_ENABLED

        # 启动底层采样
        samples = comfy.sample.sample(
            model, noise, steps, cfg, sampler_name, scheduler,
            positive, negative, latent_tensor,
            denoise=denoise,
            disable_noise=False,
            start_step=0,
            last_step=steps,
            force_full_denoise=True,
            noise_mask=noise_mask,
            callback=step_callback,
            disable_pbar=disable_pbar,
            seed=seed
        )

        out_latent = latent.copy()
        out_latent["samples"] = samples
        return (out_latent,)