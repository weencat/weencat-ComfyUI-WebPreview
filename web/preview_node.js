import { app } from "../../scripts/app.js";

// 辅助复制函数
function copyToClipboard(text, btn) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    document.body.appendChild(textArea);
    textArea.select();
    try {
        document.execCommand('copy');
        // 点击后按钮文字变为绿色反馈，2秒后恢复
        if (btn) {
            const originalText = btn.innerText;
            btn.innerText = "✅ 复制成功！";
            btn.style.backgroundColor = "#059669";
            setTimeout(() => {
                btn.innerText = originalText;
                btn.style.backgroundColor = "#2563eb";
            }, 2000);
        } else {
            alert("✅ Web 预览完整地址已复制到剪贴板：\n" + text);
        }
    } catch (err) {
        prompt("请手动复制以下地址：", text);
    }
    document.body.removeChild(textArea);
}

// 动态拼接完整预览地址
function getFullPreviewUrl() {
    const customHost = (app.ui.settings.getSettingValue("WebPreview.CustomHost", "") || "").trim();
    const host = customHost ? customHost : window.location.host;
    const protocol = window.location.protocol;
    const cleanHost = host.replace(/^https?:\/\//, "");
    return `${protocol}//${cleanHost}/web_preview/viewer`;
}

app.registerExtension({
    name: "ComfyUI.WebPreviewNode",
    
    async setup(app) {
        // 设置 1: 自定义 IP/域名输入框
        app.ui.settings.addSetting({
            id: "WebPreview.CustomHost",
            name: "Web Live Preview: 自定义 IP/域名 (留空则自动识别)",
            type: "text",
            defaultValue: "",
            tooltip: "例如填写 192.168.1.100:8188。电脑本地使用 127.0.0.1 时，填入电脑局域网 IP 即可将正确的地址复制给手机。",
        });

        // 设置 2: 使用原生 DOM 渲染独立按钮，彻底杜绝页面刷新时自动触发
        app.ui.settings.addSetting({
            id: "WebPreview.CopyUrlAction",
            name: "Web Live Preview: 复制网页看板地址",
            defaultValue: "",
            // 使用函数式自定义渲染，将事件纯粹绑定在 onclick 上
            type: (name, setter, value) => {
                const btn = document.createElement("button");
                btn.innerText = "📋 点击复制完整访问链接";
                btn.style.cursor = "pointer";
                btn.style.padding = "5px 12px";
                btn.style.borderRadius = "4px";
                btn.style.border = "none";
                btn.style.backgroundColor = "#2563eb";
                btn.style.color = "#ffffff";
                btn.style.fontSize = "12px";
                btn.style.fontWeight = "bold";
                btn.style.transition = "background-color 0.2s";

                btn.onclick = (e) => {
                    e.preventDefault();
                    const url = getFullPreviewUrl();
                    copyToClipboard(url, btn);
                };

                return btn;
            }
        });
    }
});