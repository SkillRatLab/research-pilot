#!/usr/bin/env python3
"""
ResearchAssistant Agent Receiver v8.2 — DIAGNOSTIC VERSION
==========================================================

与正式版的区别：
- 使用 tkinter 显示 GUI 对话框（不会闪退）
- 每一步都显示在窗口里，用户能看清楚
- 详细的错误信息展示
- 完整日志保存到文件

用法：
  python ra-agent-receiver-diag.py "ra://capture?data=..."
"""

import sys
import os
import json
import time
import urllib.parse
import subprocess
import threading
from pathlib import Path
from datetime import datetime

# ============================================================
# 配置
# ============================================================
SAVE_DIR = Path.home() / "research-assistant-captures"
LOG_FILE = SAVE_DIR / "ra-agent-diag.log"
TOKEN = "ra-mvp-2025-secure-token"

# ============================================================
# 日志系统（同时写控制台和文件）
# ============================================================
log_lines = []

def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"[{ts}] [{level}] {msg}"
    log_lines.append(line)
    print(line, flush=True)
    try:
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ============================================================
# 剪贴板读取
# ============================================================
def read_clipboard():
    """尝试从剪贴板读取文本"""
    # 方法 1：Tkinter
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.update()
        text = root.clipboard_get()
        root.destroy()
        if text and len(text) > 50:
            log(f"✅ 剪贴板读取成功 (Tkinter): {len(text)} 字符")
            return text
        else:
            log(f"⚠️ 剪贴板内容太短 ({len(text)} 字符)，可能无效", "WARN")
            return text or ""
    except Exception as e:
        log(f"❌ Tkinter 剪贴板失败: {e}", "ERROR")

    # 方法 2：PowerShell (Windows)
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["powershell", "-command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout:
                log(f"✅ 剪贴板读取成功 (PowerShell): {len(result.stdout)} 字符")
                return result.stdout
            else:
                log(f"⚠️ PowerShell 剪贴板返回空或错误: {result.stderr[:200]}", "WARN")
        except Exception as e:
            log(f"❌ PowerShell 失败: {e}", "ERROR")

    return ""

# ============================================================
# GUI 反馈（tkinter 对话框）
# ============================================================
def show_gui_result(title: str, message: str, success: bool):
    """显示结果对话框，5秒后自动关闭"""
    try:
        import tkinter as tk
        from tkinter import messagebox, scrolledtext
        
        root = tk.Tk()
        root.title(title)
        root.geometry("600x500")
        root.attributes("-topmost", True)
        
        # 颜色主题
        bg_color = "#f0fdf4" if success else "#fef2f2"
        title_bg = "#22c55e" if success else "#ef4444"
        
        root.configure(bg=bg_color)
        
        # 标题栏
        title_frame = tk.Frame(root, bg=title_bg, height=40)
        title_frame.pack(fill="x")
        title_label = tk.Label(
            title_frame,
            text="✅ 成功！" if success else "❌ 失败",
            font=("Microsoft YaHei", 14, "bold"),
            bg=title_bg,
            fg="white"
        )
        title_label.pack(pady=10)
        
        # 内容区域
        content = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Consolas", 10))
        content.pack(fill="both", expand=True, padx=10, pady=5)
        content.insert("1.0", message)
        content.config(state="disabled")
        
        # 底部状态栏
        status = tk.Label(
            root,
            text=f"日志已保存到: {LOG_FILE}",
            font=("Microsoft YaHei", 9),
            bg=bg_color,
            fg="#666666"
        )
        status.pack(side="bottom", pady=5)
        
        # 自动关闭计时
        def auto_close():
            time.sleep(8)
            try:
                root.destroy()
            except:
                pass
        
        t = threading.Thread(target=auto_close, daemon=True)
        t.start()
        
        # 关闭按钮
        def on_close():
            root.destroy()
        
        close_btn = tk.Button(
            root,
            text="关闭此窗口",
            command=on_close,
            font=("Microsoft YaHei", 10),
            bg="#3b82f6",
            fg="white",
            width=20
        )
        close_btn.pack(pady=10)
        
        root.protocol("WM_DELETE_WINDOW", on_close)
        root.mainloop()
        
    except Exception as e:
        log(f"GUI 显示失败: {e}", "ERROR")
        # 兜底：用简单的 messagebox
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(title, message[:2000])
            root.destroy()
        except:
            pass

# ============================================================
# 核心处理逻辑
# ============================================================
def process_protocol_url(url: str):
    """处理 ra:// 协议 URL - 诊断版"""
    
    report_lines = []
    report = lambda msg: report_lines.append(msg)
    
    report("=" * 60)
    report("📥 ResearchAssistant Agent Receiver v8.2 (DIAGNOSTIC)")
    report(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report("=" * 60)
    report("")
    
    # Step 0: 检查命令行参数
    report(f"📋 命令行参数数量: {len(sys.argv)}")
    for i, arg in enumerate(sys.argv):
        preview = arg[:100] + "..." if len(arg) > 100 else arg
        report(f"   argv[{i}]: {preview}")
    report("")
    
    if len(sys.argv) < 2:
        report("❌ 错误: 没有收到 URL 参数!")
        report("   这意味着注册表配置可能有问题")
        report("   正确格式: python script.py \"ra://capture?data=...\"")
        show_gui_result("RA 诊断 - 无参数", "\n".join(report_lines), False)
        return False
    
    url_arg = sys.argv[1]
    report(f"📎 收到的 URL 参数长度: {len(url_arg)} 字符")
    report(f"📎 URL 前 200 字符: {url_arg[:200]}")
    report("")
    
    # Step 1: 解析 URL
    report("--- Step 1: 解析 URL ---")
    try:
        parsed = urllib.parse.urlparse(url_arg)
        report(f"   Scheme: {parsed.scheme}")
        report(f"   Netloc: {parsed.netloc}")
        report(f"   Path: {parsed.path}")
        report(f"   Query 参数数: {len(parsed.query)}")
    except Exception as e:
        report(f"   ❌ URL 解析失败: {e}")
        show_gui_result("RA 诊断 - URL解析失败", "\n".join(report_lines), False)
        return False
    
    params = urllib.parse.parse_qs(parsed.query)
    report(f"   Query keys: {list(params.keys())}")
    
    if "data" not in params:
        report("   ❌ 错误: URL 中没有 'data' 参数!")
        show_gui_result("RA 诊断 - 无data参数", "\n".join(report_lines), False)
        return False
    
    raw_data = params["data"][0]
    report(f"   data 参数长度: {len(raw_data)} 字符")
    report("")
    
    # Step 2: URL 解码 + JSON 解析
    report("--- Step 2: JSON 解析 ---")
    try:
        decoded = urllib.parse.unquote(raw_data)
        report(f"   URL 解码后长度: {len(decoded)} 字符")
        payload = json.loads(decoded)
        report(f"   ✅ JSON 解析成功!")
        report(f"   JSON keys: {list(payload.keys())}")
    except json.JSONDecodeError as e:
        report(f"   ❌ JSON 解析失败: {e}")
        report(f"   原始数据前 300 字符:")
        report(f"   {raw_data[:300]}")
        show_gui_result("RA 诊断 - JSON解析失败", "\n".join(report_lines), False)
        return False
    except Exception as e:
        report(f"   ❌ URL 解码失败: {e}")
        show_gui_result("RA 诊断 - URL解码失败", "\n".join(report_lines), False)
        return False
    
    report("")
    
    # Step 3: Token 检查
    report("--- Step 3: Token 验证 ---")
    token = payload.get("token", "")
    report(f"   收到的 token: '{token}'")
    report(f"   期望的 token: '{TOKEN}'")
    if token == TOKEN:
        report("   ✅ Token 匹配")
    else:
        report("   ⚠️ Token 不匹配! (但不阻止处理)")
    report("")
    
    # Step 4: 检测模式
    report("--- Step 4: 协议模式检测 ---")
    mode = payload.get("mode", "full")
    is_slim = (mode == "slim")
    report(f"   模式: {'Slim (瘦身)' if is_slim else 'Full (完整)'}")
    report(f"   标题: {payload.get('title', 'N/A')}")
    report(f"   URL: {payload.get('url', 'N/A')}")
    if is_slim:
        report(f"   正文预览长度: {payload.get('textLength', '?')} 字符")
        report(f"   正文预览(前100字): {(payload.get('textPreview', '') or '')[:100]}")
    report("")
    
    # Step 5: 获取完整数据
    full_data = None
    report("--- Step 5: 数据获取 ---")
    
    if is_slim:
        report("   → Slim 模式：尝试从剪贴板读取完整数据...")
        report("   等待 0.5 秒确保浏览器已完成复制...")
        time.sleep(0.5)
        
        clipboard_text = read_clipboard()
        
        if not clipboard_text:
            report("   ❌ 无法从剪贴板读取数据!")
            report("   可能原因:")
            report("     1. 浏览器未成功复制到剪贴板")
            report("     2. 剪贴板权限被拒绝")
            report("     3. 导航过程中剪贴板被清空")
            
            # 仍然保存元数据
            full_data = {
                "diagnostic": "clipboard_failed",
                "metadata": payload,
                "note": "剪贴板读取失败，仅保存了元数据"
            }
        else:
            report(f"   ✅ 从剪贴板读取到 {len(clipboard_text)} 字符")
            
            # 尝试解析剪贴板中的 JSON
            try:
                clip_json = json.loads(clipboard_text)
                if isinstance(clip_json, dict) and "token" in clip_json:
                    full_data = clip_json
                    report(f"   ✅ 剪贴板内容是有效的 RA JSON!")
                    if "capture" in full_data:
                        cap = full_data["capture"]
                        report(f"      标题: {cap.get('title', 'N/A')}")
                        report(f"      正文长度: {len(cap.get('text', ''))} 字符")
                else:
                    full_data = {
                        "diagnostic": "clipboard_not_ra_format",
                        "raw_clipboard": clipboard_text[:10000],
                        "note": "剪贴板内容不是标准 RA 格式"
                    }
                    report(f"   ⚠️ 剪贴板内容不是标准 RA 格式")
            except json.JSONDecodeError:
                full_data = {
                    "diagnostic": "clipboard_not_json",
                    "text_clipboard": clipboard_text[:10000],
                    "note": "剪贴板内容不是 JSON"
                }
                report(f"   ⚠️ 剪贴板内容不是 JSON (可能是纯文本)")
    else:
        report("   → Full 模式：使用 URL 中的完整数据")
        full_data = payload
    
    report("")
    
    # Step 6: 保存文件
    report("--- Step 6: 保存文件 ---")
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"capture_{timestamp}.json"
    filepath = SAVE_DIR / filename
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(full_data, f, ensure_ascii=False, indent=2)
        file_size = filepath.stat().st_size
        report(f"   ✅ 文件已保存: {filepath}")
        report(f"   文件大小: {file_size:,} 字节")
    except Exception as e:
        report(f"   ❌ 文件保存失败: {e}")
        show_gui_result("RA 诊断 - 保存失败", "\n".join(report_lines), False)
        return False
    
    report("")
    
    # Step 7: 最终报告
    report("=" * 60)
    report("🎉 处理完成!")
    report("=" * 60)
    report(f"📁 输出文件: {filepath}")
    report(f"📁 日志文件: {LOG_FILE}")
    report(f"📁 数据目录: {SAVE_DIR}")
    
    # 判断是否真正成功
    real_success = (
        full_data is not None 
        and full_data.get("diagnostic") != "clipboard_failed"
        and ("capture" in full_data or "raw_clipboard" in full_data or "text_clipboard" in full_data)
    )
    
    final_msg = "\n".join(report_lines)
    log(final_msg)
    
    show_gui_result(
        "RA 诊断 - " + ("成功!" if real_success else "部分成功/需检查"),
        final_msg,
        real_success
    )
    
    return True

# ============================================================
# 主入口
# ============================================================
def main():
    print("=" * 60)
    print("ResearchAssistant Agent Receiver v8.2 (DIAGNOSTIC)")
    print("=" * 60)
    print()
    
    if len(sys.argv) < 2:
        msg = """
╔══════════════════════════════════════════╗
║  📋 RA Agent Receiver v8.2 (诊断版)       ║
╠══════════════════════════════════════════╣
║                                          ║
║  用法:                                   ║
║  python ra-agent-receiver-diag.py        ║
║        "ra://capture?data=..."           ║
║                                          ║
║  此版本会显示 GUI 窗口报告详细诊断信息    ║
║  不会闪退！                              ║
╚══════════════════════════════════════════╝
"""
        print(msg)
        
        # 即使没有参数也显示 GUI
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(
                "RA 诊断版 - 无参数",
                "未收到 URL 参数！\n\n请确保注册表配置正确。\n\n日志将保存到:\n" + str(LOG_FILE)
            )
            root.destroy()
        except:
            pass
        
        sys.exit(1)
    
    url_arg = sys.argv[1]
    success = process_protocol_url(url_arg)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
