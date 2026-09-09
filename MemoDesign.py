import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import os
import json
import ctypes
import sys
import zipfile
import io
import tempfile
import shutil

def get_app_base_dir():
    '''获取exe/脚本真正所在文件夹，config、shortcuts写在这里（onefile模式修复）'''
    if hasattr(sys, '_MEIPASS'):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def resource_path(relative_path):
    '''读取打包进exe内部资源：icons图片，不要用来写config！'''
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def set_app_id():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MemoDesign.MemoDesign.1.0")
    except Exception:
        pass

_ICON_PHOTO_CACHE = {}
def set_window_icon(window, icon_path="app.ico"):
    """设置窗口标题栏图标 + 任务栏图标。优先 .ico，回退 PNG。"""
    try:
        p = resource_path(icon_path)
        if os.path.exists(p):
            window.iconbitmap(p)
            return
    except Exception:
        pass
    try:
        from PIL import Image, ImageTk
        p = resource_path("icons/app.png")
        if os.path.exists(p):
            photo = _ICON_PHOTO_CACHE.get(p)
            if photo is None:
                img = Image.open(p).resize((32, 32), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                _ICON_PHOTO_CACHE[p] = photo
            window.iconphoto(True, photo)
    except Exception:
        pass

# ===================== 高 DPI 感知 =====================
def enable_dpi_awareness():
    """启用 Windows Per-Monitor V2 DPI 感知。必须在创建任何 Tk 窗口前调用一次。"""
    if not sys.platform.startswith("win"):
        return
    try:
        # 优先 Per-Monitor V2 (DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4)
        ctypes.windll.user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
        return
    except Exception:
        pass
    try:
        # 回退 Per-Monitor V1 (PROCESS_PER_MONITOR_DPI_AWARE = 2)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

class DpiHelper:
    """DPI/缩放工具。所有尺寸计算都走这里，方便集中调整。"""
    BASE_DPI = 96.0
    @staticmethod
    def get_window_dpi(win):
        """返回窗口当前 DPI（无法获取时回退 96）。"""
        try:
            if sys.platform.startswith("win"):
                hwnd = win.winfo_id()
                # GetDpiForWindow 在 Win10 1607+ 可用
                return ctypes.windll.user32.GetDpiForWindow(hwnd) or DpiHelper.BASE_DPI
        except Exception:
            pass
        return DpiHelper.BASE_DPI
    @staticmethod
    def scale(win, value):
        """按窗口 DPI 缩放一个数值 (96 为基准)。"""
        dpi = DpiHelper.get_window_dpi(win)
        return value * dpi / DpiHelper.BASE_DPI
    @staticmethod
    def scale_int(win, value):
        return int(round(DpiHelper.scale(win, value)))

# ===================== 字体 / 主题 / 样式 =====================
class AppFonts:
    """统一字体注册。所有 font= 都从这里取。"""
    # 字体族：优先微软雅黑 UI，回退 Arial (tkfont.families() 检测)
    PRIMARY_FAMILY = "Microsoft YaHei UI"
    FALLBACK_FAMILY = "Arial"
    SIZES = {"tiny": 8, "small": 9, "body": 10, "subheading": 11, "heading": 14, "title": 32}
    _ui_scale = 1.0           # 用户自定义 UI 缩放倍率
    _family = None           # 缓存检测到的字体族
    @classmethod
    def family(cls):
        if cls._family is None:
            try:
                from tkinter import font as tkfont
                families = set(tkfont.families())
                cls._family = cls.PRIMARY_FAMILY if cls.PRIMARY_FAMILY in families else cls.FALLBACK_FAMILY
            except Exception:
                # Tk 还没初始化（极少数情况），用 Arial
                cls._family = cls.FALLBACK_FAMILY
        return cls._family
    @classmethod
    def get(cls, key="body", win=None, bold=False, italic=False):
        """获取一个字体元组。DPI 缩放由系统 DPI 感知自动处理，此处只应用 UI 缩放。"""
        size = cls.SIZES.get(key, 10) * cls._ui_scale
        ft = (cls.family(), int(round(size)))
        if bold: ft = ft + ("bold",)
        if italic: ft = ft + ("italic",)
        return ft

class Theme:
    """深色/浅色主题色板。"""
    LIGHT = {
        "bg":          "#f0f0f0",
        "bg_alt":      "#d9d9d9",
        "fg":          "#13245e",
        "fg_muted":    "#595959",
        "accent":      "#3a6ea5",
        "accent_fg":   "#ffffff",
        "canvas_bg":   "#222222",
        "preview_bg":  "#2a2a3a",
        "preview_fg":  "#dddddd",
        "tree_bg":     "#ffffff",
        "tree_fg":     "#13245e",
        "entry_bg":    "#ffffff",
        "entry_fg":    "#000000",
    }
    DARK = {
        "bg":          "#2d2d35",
        "bg_alt":      "#3a3a44",
        "fg":          "#e0e0e8",
        "fg_muted":    "#a0a0b0",
        "accent":      "#3a6ea5",
        "accent_fg":   "#ffffff",
        "canvas_bg":   "#1a1a22",
        "preview_bg":  "#1a1a22",
        "preview_fg":  "#e0e0e8",
        "tree_bg":     "#2d2d35",
        "tree_fg":     "#e0e0e8",
        "entry_bg":    "#3a3a44",
        "entry_fg":    "#e0e0e8",
    }
    @classmethod
    def palette(cls, name):
        return cls.DARK if name == "dark" else cls.LIGHT
    @classmethod
    def is_dark(cls, name):
        return name == "dark"

class AppStyles:
    """ttk.Style 全局配置 + 经典 tk 组件主题递归覆盖。"""
    _initialized = False
    @classmethod
    def apply(cls, root, theme_name="light"):
        """注册并应用所有 ttk 样式 + 经典 tk 组件主题覆盖。"""
        pal = Theme.palette(theme_name)
        dpi = DpiHelper.scale(root, 1)
        # --- 1. ttk.Style 配置 ---
        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        # 全局默认
        style.configure(".", background=pal["bg"], foreground=pal["fg"],
                        font=AppFonts.get("body", root))
        # 各组件
        style.configure("TFrame", background=pal["bg"])
        style.configure("TLabel", background=pal["bg"], foreground=pal["fg"], font=AppFonts.get("body", root))
        style.configure("Muted.TLabel", background=pal["bg"], foreground=pal["fg_muted"], font=AppFonts.get("body", root))
        style.configure("TLabelframe", background=pal["bg"], foreground=pal["fg"])
        style.configure("TLabelframe.Label", background=pal["bg"], foreground=pal["fg"], font=AppFonts.get("subheading", root))
        style.configure("TButton", background=pal["bg_alt"], foreground=pal["fg"],
                        font=AppFonts.get("body", root), padding=(int(10*dpi), int(5*dpi)),
                        relief="flat", borderwidth=0)
        style.map("TButton",
                  background=[("active", pal["accent"]), ("pressed", pal["bg_alt"])],
                  foreground=[("active", pal["accent_fg"])])
        style.configure("Big.TButton", font=AppFonts.get("subheading", root), padding=(int(18*dpi), int(10*dpi)),
                        relief="flat", borderwidth=0)
        style.configure("Accent.TButton", background=pal["accent"], foreground=pal["accent_fg"],
                        font=AppFonts.get("body", root, bold=True),
                        relief="flat", borderwidth=0, padding=(int(12*dpi), int(6*dpi)))
        style.map("Accent.TButton",
                  background=[("active", pal["accent"]), ("pressed", pal["bg_alt"])],
                  foreground=[("active", pal["accent_fg"])])
        style.configure("ToolHL.TButton",
                        background=pal["accent"], foreground=pal["accent_fg"],
                        font=AppFonts.get("body", root),
                        relief="flat", borderwidth=0)
        style.configure("TEntry", fieldbackground=pal["entry_bg"], foreground=pal["entry_fg"],
                        insertbackground=pal["entry_fg"], font=AppFonts.get("body", root),
                        relief="flat", borderwidth=1)
        style.configure("TCombobox", fieldbackground=pal["entry_bg"], foreground="#123456",
                        background=pal["bg_alt"], font=AppFonts.get("body", root),
                        arrowcolor=pal["fg"], bordercolor=pal["bg_alt"],
                        relief="flat", borderwidth=1
                        )
        style.configure("TCheckbutton", background=pal["bg"], foreground=pal["fg"],
                        font=AppFonts.get("body", root))
        style.configure("TRadiobutton", background=pal["bg"], foreground=pal["fg"],
                        font=AppFonts.get("body", root))
        style.configure("Horizontal.TScale", background=pal["bg"])
        style.configure("Horizontal.TScrollbar", background=pal["bg_alt"])
        style.configure("Vertical.TScrollbar", background=pal["bg_alt"])
        style.configure("TSeparator", background=pal["bg_alt"])
        style.configure("TNotebook", background=pal["bg"])
        style.configure("TNotebook.Tab", background=pal["bg_alt"], foreground=pal["fg"],
                        font=AppFonts.get("body", root), padding=(int(12*dpi), int(6*dpi)))
        style.map("TNotebook.Tab",
                  background=[("selected", pal["bg"])],
                  foreground=[("selected", pal["accent"])])
        style.configure("Treeview", background=pal["tree_bg"], foreground=pal["tree_fg"],
                        fieldbackground=pal["tree_bg"], font=AppFonts.get("small", root),
                        rowheight=int(AppFonts.SIZES["small"] * 2.4 * AppFonts._ui_scale * dpi))
        style.configure("Treeview.Heading", background=pal["bg_alt"], foreground=pal["fg"],
                        font=AppFonts.get("body", root, bold=True))
        # --- 2. Toplevel/Tk 根窗口背景 + 容器背景（先设基线） ---
        try:
            cls._set_tk_bg(root, pal)
        except Exception:
            pass
        # --- 3. 递归覆盖经典 tk 组件（后覆盖，确保叶子组件语义优先） ---
        cls._apply_to_classic(root, pal)
        # --- 4. 给所有 ttk.Combobox 绑定下拉弹出配色钩子 ---
        cls._bind_combobox_popdown(root, pal)
        # --- 5. 延迟一次兜底覆盖 ---
        # 因为 apply 可能在子组件创建前被调用（如 MainMenu.__init__），
        # 此时 winfo_children() 为空。用 after 在事件循环空闲时再次覆盖。
        try:
            root.after(10, lambda: cls._apply_deferred(root, theme_name))
        except Exception:
            pass
        cls._initialized = True
    @classmethod
    def _apply_deferred(cls, root, theme_name):
        """延迟覆盖：此时子组件应已全部创建。"""
        try:
            pal = Theme.palette(theme_name)
            cls._set_tk_bg(root, pal)
            cls._apply_to_classic(root, pal)
            cls._bind_combobox_popdown(root, pal)
        except Exception:
            pass
    _CONTAINER_CLASSES = {"Frame", "Toplevel", "Tk", "Canvas"}
    @classmethod
    def _bind_combobox_popdown(cls, root, pal):
        """给所有 ttk.Combobox 绑定 postcommand，在下拉弹出时给 Listbox 上色。
        ttk.Combobox 下拉列表是独立的 Toplevel + Listbox，不在主组件树里，
        ttk.Style 管不到，必须在弹出瞬间手动配色。"""
        def find_combos(win):
            result = []
            try:
                cls_name = win.winfo_class()
            except Exception:
                return result
            try:
                import tkinter.ttk as ttk_mod
                if cls_name == "TCombobox":
                    result.append(win)
            except Exception:
                pass
            for child in win.winfo_children():
                result.extend(find_combos(child))
            return result
        def _color_popdown():
            """在 Combobox 弹出后被调用，找到弹出的 Toplevel 并配色。"""
            try:
                cls._apply_to_classic_popdown(pal)
            except Exception:
                pass
        for combo in find_combos(root):
            try:
                combo.configure(postcommand=_color_popdown)
            except Exception:
                pass
    @classmethod
    def _apply_to_classic_popdown(cls, pal):
        """遍历所有 Toplevel，找到 Combobox 弹出的 Listbox 并配色。"""
        import tkinter as tk_mod
        try:
            for tl in tk_mod.Tk.winfo_children(cls._get_root()):
                if tl.winfo_class() == "Toplevel":
                    for w in tl.winfo_children():
                        cls._apply_one(w, pal)
                        cls._apply_to_classic(w, pal)
        except Exception:
            pass
    @classmethod
    def _get_root(cls):
        """返回应用根 Tk 实例。"""
        import tkinter as tk_mod
        try:
            return tk_mod._default_root
        except Exception:
            return None
    @classmethod
    def _set_tk_bg(cls, win, pal):
        """递归设置容器组件（Frame/Toplevel/Tk/Canvas）背景。
        叶子组件（Label/Listbox/Entry 等）由 _apply_one 处理，此处跳过，
        避免覆盖其语义化颜色（如 Listbox 应是 tree_bg 而非主 bg）。"""
        pal_map = {"main": pal["bg"], "canvas": pal["canvas_bg"], "preview": pal["preview_bg"]}
        cls_name = win.winfo_class()
        if cls_name in cls._CONTAINER_CLASSES:
            semantic = getattr(win, "_theme_bg_semantic", None)
            bg = pal_map.get(semantic, pal["bg"])
            try:
                win.configure(bg=bg)
            except Exception:
                pass
        for child in win.winfo_children():
            cls._set_tk_bg(child, pal)
    @classmethod
    def _apply_to_classic(cls, win, pal):
        """递归遍历所有子组件，对经典 tk 组件按主题色板设置颜色。"""
        import tkinter as tk_mod
        for w in win.winfo_children():
            try:
                cls._apply_one(w, pal)
            except Exception:
                pass
            # 递归子组件
            try:
                cls._apply_to_classic(w, pal)
            except Exception:
                pass
    @classmethod
    def _apply_one(cls, w, pal):
        """对单个经典 tk 组件设置主题颜色。
        每个组件的 configure 调用拆成：核心属性（bg/fg，必须生效）+ 可选属性
        （selectbackground/highlightcolor 等，Tk 版本差异大，单独 try）。
        Frame/Toplevel/Tk/Canvas 容器类由 _set_tk_bg 统一处理，此处跳过。"""
        cls_name = w.winfo_class()
        if cls_name in cls._CONTAINER_CLASSES:
            return
        if cls_name == "Label":
            w.configure(bg=pal["bg"])
            cur_fg = w.cget("fg")
            primary_fgs = ("#13245e", "#e0e0e8", "#000000", "SystemWindowText")
            muted_fgs = ("#595959", "#a0a0b0", "#ffffff", "SystemWindow")
            if cur_fg in primary_fgs:
                w.configure(fg=pal["fg"])
            elif cur_fg in muted_fgs:
                w.configure(fg=pal["fg_muted"])
        elif cls_name == "Listbox":
            try:
                w.configure(bg=pal["tree_bg"], fg=pal["tree_fg"])
            except Exception:
                pass
            try:
                w.configure(selectbackground=pal["accent"],
                            selectforeground=pal["accent_fg"],
                            highlightbackground=pal["bg_alt"],
                            highlightcolor=pal["accent"])
            except Exception:
                pass
            try:
                w.configure(disabledbackground=pal["bg_alt"],
                            disabledforeground=pal["fg_muted"])
            except Exception:
                pass
        elif cls_name == "Entry":
            try:
                w.configure(bg=pal["entry_bg"], fg=pal["entry_fg"])
            except Exception:
                pass
            try:
                w.configure(insertbackground=pal["entry_fg"],
                            highlightbackground=pal["bg_alt"],
                            highlightcolor=pal["accent"])
            except Exception:
                pass
        elif cls_name == "Text":
            try:
                w.configure(bg=pal["entry_bg"], fg=pal["entry_fg"],
                            insertbackground=pal["entry_fg"])
            except Exception:
                pass
        elif cls_name == "Message":
            try:
                w.configure(bg=pal["bg"], fg=pal["fg"])
            except Exception:
                pass
        elif cls_name in ("Radiobutton", "Checkbutton"):
            try:
                w.configure(bg=pal["bg"], fg=pal["fg"],
                             activebackground=pal["bg"], activeforeground=pal["fg"],
                             selectcolor=pal["bg"])
            except Exception:
                pass
        elif cls_name == "Button":
            try:
                w.configure(bg=pal["bg_alt"], fg=pal["fg"],
                            activebackground=pal["accent"],
                            activeforeground=pal["accent_fg"])
            except Exception:
                pass
        elif cls_name == "Menu":
            try:
                w.configure(bg=pal["bg"], fg=pal["fg"],
                            activebackground=pal["accent"],
                            activeforeground=pal["accent_fg"])
            except Exception:
                pass
    @classmethod
    def apply_theme_and_fonts(cls, root, theme_name):
        """DPI 变化或切换主题时调用，重排所有窗口。"""
        cls.apply(root, theme_name)
        # 递归刷新所有 Toplevel 的样式
        def _refresh(win):
            try:
                cls.apply(win, theme_name)
            except Exception:
                pass
            for child in win.winfo_children():
                try: cls._apply_to_classic(child, Theme.palette(theme_name))
                except Exception: pass
                _refresh(child)
        for win in root._dialogs if hasattr(root, "_dialogs") else []:
            try: _refresh(win)
            except Exception: pass

# ===================== 公共对话框基类 =====================
class BaseDialog(tk.Toplevel):
    """所有对话框的基类: 统一 _center / 主题应用 / DPI 跟随。"""
    def __init__(self, parent, title, size, resizable=True, min_size=None, theme_name="light"):
        super().__init__(parent)
        self.title(title); self.geometry(size)
        if not resizable:
            self.resizable(False, False)
        elif min_size:
            self.resizable(True, True)
            self.update_idletasks()
            self.minsize(*min_size)
        self.transient(parent)
        self._theme_name = theme_name
        # DPI 变化跟随
        self.bind("<Map>", self._on_map_dpi)
    def _center(self, parent=None):
        parent = parent or self.master
        self.update_idletasks()
        try:
            x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{max(0,x)}+{max(0,y)}")
        except Exception:
            pass
    def _on_map_dpi(self, event):
        # 窗口映射到屏幕时刷新一次样式（DPI 已生效）
        try:
            AppStyles.apply(self, self._theme_name)
        except Exception:
            pass

# ===================== 可滚动容器 =====================
class ScrollableFrame(ttk.Frame):
    """内部可垂直滚动的容器。用法: ScrollableFrame(parent) 返回外框，
    用 .inner 拿到内部 Frame 放 widget。"""
    def __init__(self, parent, theme_name="light", *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        pal = Theme.palette(theme_name)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=pal["bg"])
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # 宽度跟随容器
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        # 鼠标滚轮
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)
    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._inner_id, width=event.width)
    def _bind_wheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<Button-4>", self._on_wheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_wheel_linux)
    def _unbind_wheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")
        try:
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")
        except Exception:
            pass
    def _on_wheel(self, event):
        try:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass
    def _on_wheel_linux(self, event):
        try:
            if event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")
        except Exception:
            pass
# ===================== 图标路径配置（用户填写相对路径，16x16，邻近渲染）=====================
ICON_PATHS = {
    "new":        "icons/new.png",
    "open":       "icons/open.png",
    "save":       "icons/save.png",
    "undo":       "icons/undo.png",
    "redo":       "icons/redo.png",
    "brush":      "icons/brush.png",
    "eraser":     "icons/eraser.png",
    "rect":       "icons/rect.png",
    "fill":       "icons/fill.png",
    "copy":       "icons/copy.png",
    "paste":      "icons/paste.png",
    "attr":       "icons/attr.png",
    "pan":        "icons/pan.png",
    "tile_edit":  "icons/tile_edit.png",
    "resize":     "icons/resize.png",
}
_ICON_CACHE = {}
def load_icon(name, size=16):
    """加载16x16图标，使用NEAREST邻近渲染避免模糊。找不到返回None。"""
    key = (name, size)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    rel = ICON_PATHS.get(name, "")
    if not rel:
        return None
    p = resource_path(rel)
    if not os.path.exists(p):
        return None
    try:
        img = Image.open(p).convert("RGBA").resize((size, size), Image.Resampling.NEAREST)
        photo = ImageTk.PhotoImage(img)
        _ICON_CACHE[key] = photo
        return photo
    except Exception:
        return None
# ===================== 配置 / 历史 =====================
_app_base = get_app_base_dir()
CONFIG_FILE = os.path.join(_app_base, "config.json")
SHORTCUT_FILE = os.path.join(_app_base, "shortcuts.json")
def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            # 旧版本兼容: ui_scale 存的是百分比 (如 150 = 1.5x)，新版本存小数倍数
            us = cfg.get("ui_scale", 1.0)
            if isinstance(us, (int, float)) and us > 10:
                cfg["ui_scale"] = round(us / 100.0, 2)
                save_config(cfg)
            # 补齐缺失字段
            cfg.setdefault("theme", "light")
            cfg.setdefault("auto_dpi", True)
            cfg.setdefault("screen_scale", 100)
            cfg.setdefault("ui_scale", 1.0)
            return cfg
    except Exception:
        pass
    return {"last_mdtile": "", "history": [], "theme": "light", "auto_dpi": True, "screen_scale": 100, "ui_scale": 1.0}

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def add_history(path, cfg=None):
    if cfg is None:
        cfg = load_config()
    hist = cfg.get("history", [])
    if path in hist:
        hist.remove(path)
    hist.insert(0, path)
    cfg["history"] = hist[:20]
    save_config(cfg)
    return cfg

# ===================== 快捷键 =====================
DEFAULT_SHORTCUTS = {
    "save":        "<Control-s>",
    "save_as":     "<Control-Shift-S>",
    "new_map":     "<Control-n>",
    "open_mdmap":  "<Control-o>",
    "undo":        "<Control-z>",
    "redo":        "<Control-y>",
    "redo_alt":    "<Control-Shift-Z>",
    "tile_editor": "<Control-t>",
    "preferences": "<Control-comma>",
    "tool_brush":  "b",
    "tool_eraser": "e",
    "tool_rect":   "r",
    "tool_fill":   "g",
    "tool_copy":   "c",
    "attr_start":  "s",
    "attr_end":    "d",
    "attr_key":    "k",
    "attr_portal": "j",
    "tool_pan":    "h",
}
SHORTCUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shortcuts.json")

# ===================== 属性库 =====================
ATTRIBUTES_FILE = os.path.join(_app_base, "attributes.json")
# 保存格式: "¿ABCD¿tile_code" 中 A/B/C/D 各占 1 字符；空槽位用 PLACEHOLDER
ATTR_SLOT_PLACEHOLDER = "0"
# 禁止用作属性 ID 的字符: ¿ (格式包装符), 0 (空槽占位)
FORBIDDEN_ATTR_IDS = {"¿", ATTR_SLOT_PLACEHOLDER}
# 4 个特殊属性（内置）的 ID
BUILTIN_ATTR_IDS = {"start": "$", "end": "%", "key": "?", "portal": "!"}
# 内置"单例"属性（整张地图只能存在一个）
SINGLETON_ATTR_IDS = {"$", "%"}
ATTR_SHAPES = ["circle", "square", "octagon", "triangle"]
ATTR_SHAPE_LABELS = {"circle": "圆形", "square": "正方形", "octagon": "八边形", "triangle": "三角形"}

class AttributeDefine:
    """一个属性定义：名称/ID/颜色/形状/是否内置/可选字段。"""
    def __init__(self, name, id_char, color, shape, builtin=False, options=None, singleton=False):
        self.name = name
        self.id_char = id_char  # 单字符
        self.color = color  # 8 位十六进制 (#RRGGBBAA)
        self.shape = shape  # circle / square / octagon / triangle
        self.builtin = builtin
        self.options = list(options or [])  # [{"name":..,"default":..}]
        self.singleton = singleton  # 整张地图唯一

class AttributeLibrary:
    """管理内置 + 用户自定义属性，并持久化到 attributes.json。"""
    def __init__(self):
        self.attrs = []
        self._load_default()
        self._load_user()
    def _load_default(self):
        self.attrs = [
            AttributeDefine("起始点", "$", "#FF3333FF", "circle", builtin=True, singleton=True),
            AttributeDefine("终点", "%", "#33DD33FF", "circle", builtin=True, singleton=True),
            AttributeDefine("钥匙", "?", "#FFDC00FF", "square", builtin=True),
            AttributeDefine("跳转格", "!", "#FF7733FF", "square", builtin=True,
                            options=[{"name": "path", "default": "res://level/"},
                                    {"name": "color", "default": "ff7733"}]),
        ]
    def _load_user(self):
        if os.path.exists(ATTRIBUTES_FILE):
            try:
                with open(ATTRIBUTES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("attributes", []):
                    self.attrs.append(AttributeDefine(
                        item["name"], item["id"], item["color"], item["shape"],
                        builtin=False, options=item.get("options", []),
                        singleton=item.get("singleton", False)))
            except Exception:
                pass
    def save(self):
        data = {"attributes": []}
        for a in self.attrs:
            if a.builtin: continue
            data["attributes"].append({
                "name": a.name, "id": a.id_char, "color": a.color,
                "shape": a.shape, "options": a.options, "singleton": a.singleton})
        try:
            with open(ATTRIBUTES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    def get_by_id(self, id_char):
        for a in self.attrs:
            if a.id_char == id_char: return a
        return None
    def get_by_name(self, name):
        for a in self.attrs:
            if a.name == name: return a
        return None
    def get_names(self):
        return [a.name for a in self.attrs]
    def label_for_id(self, id_char):
        a = self.get_by_id(id_char)
        return a.name if a else id_char
    def id_for_label(self, label):
        a = self.get_by_name(label)
        return a.id_char if a else None
    def is_valid_id(self, id_char):
        if not id_char or len(id_char) != 1: return False
        if id_char in FORBIDDEN_ATTR_IDS: return False
        return True
    def add(self, attr):
        # 防止 ID 冲突
        existing = self.get_by_id(attr.id_char)
        if existing is not None: return False
        self.attrs.append(attr); return True
    def update(self, old_id, attr):
        # 修改用户自定义属性；内置只允许改名称/颜色/形状
        for i, a in enumerate(self.attrs):
            if a.id_char == old_id:
                if a.builtin:
                    # 不允许改 id_char
                    attr.id_char = old_id
                self.attrs[i] = attr; return True
        return False
    def remove(self, id_char):
        for i, a in enumerate(self.attrs):
            if a.id_char == id_char and not a.builtin:
                del self.attrs[i]; return True
        return False
    def to_dict(self):
        return {"attributes": [
            {"name": a.name, "id": a.id_char, "color": a.color,
             "shape": a.shape, "options": a.options, "builtin": a.builtin,
             "singleton": a.singleton} for a in self.attrs]}
    def load_from_dict(self, data, merge_builtin=True):
        """从字典加载（导入 .mdattr）。merge_builtin=True 时保留内置属性。"""
        new_attrs = []
        if merge_builtin:
            new_attrs.extend([a for a in self.attrs if a.builtin])
        for item in data.get("attributes", []):
            if item.get("builtin"): continue  # 内置项不重复导入
            id_char = item.get("id", "")
            if id_char in FORBIDDEN_ATTR_IDS: continue
            # 跳过与内置 ID 冲突
            if any(b.id_char == id_char for b in new_attrs if b.builtin): continue
            # 跳过与已加入项冲突
            if any(b.id_char == id_char for b in new_attrs): continue
            new_attrs.append(AttributeDefine(
                item.get("name", id_char), id_char, item.get("color", "#FFFFFFFF"),
                item.get("shape", "circle"), builtin=False,
                options=item.get("options", []),
                singleton=item.get("singleton", False)))
        self.attrs = new_attrs

def load_shortcuts():
    """快捷键合并进 config.json。兼容旧 shortcuts.json。"""
    cfg = load_config()
    if "shortcuts" in cfg:
        merged = dict(DEFAULT_SHORTCUTS); merged.update(cfg["shortcuts"])
        return merged
    # 兼容旧 shortcuts.json
    try:
        if os.path.exists(SHORTCUT_FILE):
            with open(SHORTCUT_FILE, "r", encoding="utf-8") as f:
                old = json.load(f)
                cfg["shortcuts"] = old; save_config(cfg)
                merged = dict(DEFAULT_SHORTCUTS); merged.update(old)
                return merged
    except Exception:
        pass
    return dict(DEFAULT_SHORTCUTS)

def save_shortcuts(shortcuts):
    """保存快捷键到 config.json（不再单独写 shortcuts.json）。"""
    cfg = load_config()
    cfg["shortcuts"] = shortcuts
    save_config(cfg)
    return True

# ===================== 撤销/重做 =====================
class UndoManager:
    MAX_HISTORY = 50
    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []
    def snapshot(self, map_data):
        snap = {
            "map_name": map_data.map_name,
            "row_count": map_data.row_count,
            "col_count": map_data.col_count,
            "category": map_data.category,
            "background": map_data.background,
            "tiles": list(map_data.tiles),
            "start_pos": map_data.start_pos,
            "end_pos": map_data.end_pos,
            "key_marks": set(map_data.key_marks),
            "portals": {f"{k[0]},{k[1]}": dict(v) for k, v in map_data.portals.items()},
            "tile_attrs": {f"{k[0]},{k[1]}": dict(v) for k, v in map_data.tile_attrs.items()},
            "tile_attr_options": {f"{k[0]},{k[1]},{k[2]}": dict(v) for k, v in map_data.tile_attr_options.items()},
        }
        self.undo_stack.append(snap)
        if len(self.undo_stack) > self.MAX_HISTORY:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
    def can_undo(self): return len(self.undo_stack) > 0
    def can_redo(self): return len(self.redo_stack) > 0
    def pop_undo(self, map_data):
        if not self.can_undo(): return False
        self.redo_stack.append(self._copy(map_data))
        self._restore(self.undo_stack.pop(), map_data)
        return True
    def pop_redo(self, map_data):
        if not self.can_redo(): return False
        self.undo_stack.append(self._copy(map_data))
        self._restore(self.redo_stack.pop(), map_data)
        return True
    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
    @staticmethod
    def _copy(md):
        return {
            "map_name": md.map_name, "row_count": md.row_count, "col_count": md.col_count,"category": md.category, "background": md.background,
            "tiles": list(md.tiles), "start_pos": md.start_pos, "end_pos": md.end_pos,
            "key_marks": set(md.key_marks),
            "portals": {f"{k[0]},{k[1]}": dict(v) for k, v in md.portals.items()},
            "tile_attrs": {f"{k[0]},{k[1]}": dict(v) for k, v in md.tile_attrs.items()},
            "tile_attr_options": {f"{k[0]},{k[1]},{k[2]}": dict(v) for k, v in md.tile_attr_options.items()},
        }
    @staticmethod
    def _restore(snap, md):
        md.map_name = snap["map_name"]; md.row_count = snap["row_count"]; md.col_count = snap["col_count"]
        md.category = snap.get("category", "未分类")
        md.background = snap.get("background", "")
        md.tiles = list(snap["tiles"]); md.start_pos = snap.get("start_pos"); md.end_pos = snap.get("end_pos")
        md.key_marks = set(snap.get("key_marks", set()))
        portals = {}
        for k, v in snap.get("portals", {}).items():
            r, c = k.split(","); portals[(int(r), int(c))] = v
        md.portals = portals
        # 恢复 tile_attrs
        tile_attrs = {}
        for k, v in snap.get("tile_attrs", {}).items():
            r, c = k.split(","); tile_attrs[(int(r), int(c))] = dict(v)
        md.tile_attrs = tile_attrs
        tile_attr_options = {}
        for k, v in snap.get("tile_attr_options", {}).items():
            parts = k.split(",")
            if len(parts) == 3:
                r, c, s = parts
                tile_attr_options[(int(r), int(c), s)] = dict(v)
        md.tile_attr_options = tile_attr_options

# ===================== 数据模型 =====================
class TileDefine:
    def __init__(self, code: str, name: str, img_path: str,
                 walkable: bool = False, layer: str = "0", category: str = "", image_bytes=None):
        self.code = code
        self.name = name
        self.img_path = img_path
        self.walkable = walkable
        self.layer = layer
        self.category = category #新增瓦片分类
        self.image = None
        self.photo = None
        self.image_bytes = image_bytes  # 用于 .mdt 内嵌图片

    def load_image(self, size=(48, 48)):
        try:
            if self.image_bytes is not None:
                img = Image.open(io.BytesIO(self.image_bytes)).convert("RGBA")
            elif self.img_path:
                img = Image.open(self.img_path).convert("RGBA")
            else:
                self.image = None; self.photo = None; return
            img = img.resize(size, Image.Resampling.LANCZOS)
            self.image = img
            self.photo = ImageTk.PhotoImage(img)
        except Exception:
            self.image = None
            self.photo = None

class MapData:
    SLOT_ORDER = ["A", "B", "C", "D"]  # A=左上 B=右上 C=左下 D=右下
    def __init__(self):
        self.map_name = "Untitled"; self.row_count = 10; self.col_count = 10
        self.category = "未分类"
        self.background = ""
        self.tiles = []; self.start_pos = None; self.end_pos = None
        self.key_marks = set(); self.portals = {}
        # 新增: 每个瓦片的 ABCD 属性槽
        self.tile_attrs = {}        # (r,c) -> {"A":id_or_None, "B":.., "C":.., "D":..}
        self.tile_attr_options = {} # (r,c,slot) -> {opt_name: value}
    # ---------- 属性辅助方法 ----------
    def _empty_slots(self):
        return {"A": None, "B": None, "C": None, "D": None}
    def get_slots(self, r, c):
        """返回该格的 4 槽字典（不存在则返回全空）"""
        return dict(self.tile_attrs.get((r, c), self._empty_slots()))
    def set_slot(self, r, c, slot, id_char, options=None):
        slots = self.tile_attrs.setdefault((r, c), self._empty_slots())
        slots[slot] = id_char
        if id_char is None:
            self.tile_attr_options.pop((r, c, slot), None)
        elif options is not None:
            self.tile_attr_options[(r, c, slot)] = dict(options)
    def find_slot_of(self, r, c, id_char):
        slots = self.tile_attrs.get((r, c))
        if not slots: return None
        for s in self.SLOT_ORDER:
            if slots.get(s) == id_char: return s
        return None
    def has_attr(self, r, c, id_char):
        return self.find_slot_of(r, c, id_char) is not None
    def is_full(self, r, c):
        slots = self.tile_attrs.get((r, c))
        if not slots: return False
        return all(slots.get(s) is not None for s in self.SLOT_ORDER)
    def remove_attr(self, r, c, id_char):
        """移除该格上指定 ID 的属性（所有槽），返回是否操作"""
        slots = self.tile_attrs.get((r, c))
        if not slots: return False
        removed = False
        for s in self.SLOT_ORDER:
            if slots.get(s) == id_char:
                slots[s] = None
                self.tile_attr_options.pop((r, c, s), None)
                removed = True
        return removed
    def add_attr(self, r, c, id_char, options=None):
        """按 ABCD 顺序补到第一个空槽。重复/已满返回 False。"""
        if self.has_attr(r, c, id_char): return False
        if self.is_full(r, c): return False
        slots = self.tile_attrs.setdefault((r, c), self._empty_slots())
        for s in self.SLOT_ORDER:
            if slots.get(s) is None:
                slots[s] = id_char
                if options is not None:
                    self.tile_attr_options[(r, c, s)] = dict(options)
                return True
        return False
    def clear_attr_tile(self, r, c):
        self.tile_attrs.pop((r, c), None)
        for s in self.SLOT_ORDER:
            self.tile_attr_options.pop((r, c, s), None)
    def all_attr_positions(self, id_char):
        """所有含有指定 id 的格子位置列表"""
        out = []
        for pos, slots in self.tile_attrs.items():
            for s in self.SLOT_ORDER:
                if slots.get(s) == id_char:
                    out.append((pos[0], pos[1], s)); break
        return out
    def remove_attr_everywhere(self, id_char):
        """整张地图移除某个 id（用于单例属性 / 属性被删）"""
        for pos in list(self.tile_attrs.keys()):
            self.remove_attr(pos[0], pos[1], id_char)
    # ---------- 同步内置 legacy 字段 ----------
    def sync_legacy_attrs(self, attr_lib):
        """从 tile_attrs 重建 start_pos/end_pos/key_marks/portals"""
        self.start_pos = None; self.end_pos = None
        self.key_marks = set(); self.portals = {}
        start_id = BUILTIN_ATTR_IDS["start"]; end_id = BUILTIN_ATTR_IDS["end"]
        key_id = BUILTIN_ATTR_IDS["key"]; portal_id = BUILTIN_ATTR_IDS["portal"]
        for (r, c), slots in self.tile_attrs.items():
            for s in self.SLOT_ORDER:
                aid = slots.get(s)
                if not aid: continue
                if aid == start_id:
                    self.start_pos = (r, c)
                elif aid == end_id:
                    self.end_pos = (r, c)
                elif aid == key_id:
                    self.key_marks.add((r, c))
                elif aid == portal_id:
                    opts = self.tile_attr_options.get((r, c, s), {})
                    self.portals[(r, c)] = {
                        "path": opts.get("path", "res://level/"),
                        "color": opts.get("color", "ff7733")}
    def to_text(self):
        lines = [f"MemoDesign:{self.map_name}", f"Row:{self.row_count}", f"Column:{self.col_count}",
                 f"Category:{self.category}", f"Background:{self.background}", "Tile:"]
        total = self.row_count * self.col_count
        for idx in range(total):
            code = self.tiles[idx] if idx < len(self.tiles) else "air"
            r, c = divmod(idx, self.col_count)
            slots = self.tile_attrs.get((r, c))
            has_attr = slots and any(slots.get(s) is not None for s in self.SLOT_ORDER)
            prefix = ""
            if has_attr:
                chars = []
                for s in self.SLOT_ORDER:
                    aid = slots.get(s)
                    chars.append(aid if aid else ATTR_SLOT_PLACEHOLDER)
                prefix = "¿" + "".join(chars) + "¿"
            lines.append(prefix + code)
        # 选项区: 持久化瓦片属性的可编辑选项 (r,c,slot|key=val;key=val)
        if self.tile_attr_options:
            lines.append("AttrOptions:")
            for (r, c, s), opts in self.tile_attr_options.items():
                if not opts: continue
                parts = [f"{k}={v}" for k, v in opts.items()]
                lines.append(f"{r},{c},{s}|" + ";".join(parts))
        return "\n".join(lines)
    @staticmethod
    def parse_text(text):
        md = MapData()
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        tile_start = -1
        for i, line in enumerate(lines):
            if line.startswith("MemoDesign:"): md.map_name = line.split(":", 1)[1]
            elif line.startswith("Row:"): md.row_count = int(line.split(":", 1)[1])
            elif line.startswith("Column:"): md.col_count = int(line.split(":", 1)[1])
            elif line.startswith("Category:"): md.category = line[len("Category:"):].strip()
            elif line.startswith("Background:"): md.background = line[len("Background:"):].strip()
            elif line == "Tile:": tile_start = i + 1
        if tile_start != -1:
            raw = lines[tile_start:]
            expect = md.row_count * md.col_count
            while len(raw) < expect: raw.append("air")
            raw = raw[:expect]
            parsed = []
            for idx, item in enumerate(raw):
                r, c = divmod(idx, md.col_count)
                code = item
                if code.startswith("¿"):
                    # 新格式: ¿ABCD¿tile_code
                    end = code.find("¿", 1)
                    if end == -1:
                        real = code
                    else:
                        slot_chars = code[1:end]
                        real = code[end+1:]
                        slots = md._empty_slots()
                        for i, sk in enumerate(md.SLOT_ORDER):
                            if i < len(slot_chars):
                                ch = slot_chars[i]
                                if ch != ATTR_SLOT_PLACEHOLDER and ch != "":
                                    slots[sk] = ch
                        if any(slots.get(s) for s in md.SLOT_ORDER):
                            md.tile_attrs[(r, c)] = slots
                        code = real
                else:
                    # 旧格式: 按出现顺序转入 ABCD 槽（兼容）
                    slots = md._empty_slots()
                    is_key = False
                    if code.startswith("!"):
                        rest = code[1:]; at1 = rest.find("@")
                        color = rest[:at1]; rest2 = rest[at1+1:]; at2 = rest2.find("@")
                        path = rest2[:at2]; real = rest2[at2+1:]
                        md.portals[(r, c)] = {"path": path, "color": color}
                        slots["A"] = "!"
                        md.tile_attr_options[(r, c, "A")] = {"path": path, "color": color}
                        code = real
                    if code.startswith("?"): is_key = True; code = code[1:]; slots["B"] = "?"
                    if code.startswith("$"):
                        code = code[1:]; md.start_pos = (r, c); slots["C"] = "$"
                    elif code.startswith("%"):
                        code = code[1:]; md.end_pos = (r, c); slots["D"] = "%"
                    if is_key: md.key_marks.add((r, c))
                    if any(slots.get(s) for s in md.SLOT_ORDER):
                        md.tile_attrs[(r, c)] = slots
                parsed.append(code)
            md.tiles = parsed
        # 解析选项区 AttrOptions:
        opt_start = -1
        for i, line in enumerate(lines):
            if line == "AttrOptions:":
                opt_start = i + 1; break
        if opt_start != -1:
            for line in lines[opt_start:]:
                if line.startswith("MemoDesign:") or line.startswith("Row:") \
                   or line.startswith("Column:") or line == "Tile:":
                    break
                if "|" not in line: continue
                head, body = line.split("|", 1)
                parts = head.split(",")
                if len(parts) != 3: continue
                r, c, s = int(parts[0]), int(parts[1]), parts[2]
                opts = {}
                for kv in body.split(";"):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        opts[k] = v
                if opts:
                    md.tile_attr_options[(r, c, s)] = opts
        return md
    def validate(self, tile_library):
        """导出前校验，返回警告列表"""
        warns = []
        if self.start_pos is None: warns.append("缺少起始点")
        if self.end_pos is None: warns.append("缺少结束点")
        for pos, p in self.portals.items():
            if not p.get("path", "").strip():
                warns.append(f"跳转格({pos[0]},{pos[1]})路径为空")
            color = p.get("color", "")
            if len(color) != 6:
                warns.append(f"跳转格({pos[0]},{pos[1]})颜色不是6位16进制")
            else:
                try: int(color, 16)
                except ValueError: warns.append(f"跳转格({pos[0]},{pos[1]})颜色非法")
        for idx, code in enumerate(self.tiles):
            if code != "air" and code not in tile_library:
                r, c = divmod(idx, self.col_count)
                warns.append(f"格子({r},{c})使用了未定义的瓦片: {code}")
        return warns

# ===================== 弹窗 =====================
class NewMapDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent); self.title("新建地图"); self.geometry("400x280")
        self.resizable(False, False); self.transient(parent); self.grab_set(); self.result = None
        self._theme_name = getattr(parent, "_theme_name", "light")
        AppStyles.apply(self, self._theme_name)
        f = ttk.Frame(self, padding=10); f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text="地图名称:").grid(row=0, column=0, sticky="w", pady=4)
        self.var_name = tk.StringVar(value="newmap")
        ttk.Entry(f, textvariable=self.var_name, width=22).grid(row=0, column=1, padx=6)
        ttk.Label(f, text="行数:").grid(row=1, column=0, sticky="w", pady=4)
        self.var_row = tk.StringVar(value="10")
        ttk.Entry(f, textvariable=self.var_row, width=22).grid(row=1, column=1, padx=6)
        ttk.Label(f, text="列数:").grid(row=2, column=0, sticky="w", pady=4)
        self.var_col = tk.StringVar(value="10")
        ttk.Label(f, text="类别:").grid(row=3, column=0, sticky="w", pady=4)
        self.var_category = tk.StringVar(value="未分类")
        ttk.Entry(f, textvariable=self.var_category, width=22).grid(row=3, column=1, padx=6)
        ttk.Label(f, text="背景:").grid(row=4, column=0, sticky="w", pady=4)
        self.var_background = tk.StringVar(value="")
        ttk.Entry(f, textvariable=self.var_background, width=22).grid(row=4, column=1, padx=6)
        bf = ttk.Frame(f); bf.grid(row=5, column=0, columnspan=2, pady=12)
        ttk.Button(bf, text="确定", command=self.ok).pack(side=tk.LEFT, padx=8)
        ttk.Button(bf, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=8)
        self._center(parent)
    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    def ok(self):
        name = self.var_name.get().strip()
        if not name: messagebox.showwarning("提示", "名称不能为空！"); return
        try:
            r = int(self.var_row.get()); c = int(self.var_col.get())
            if r < 1 or c < 1: messagebox.showwarning("提示", "行列必须≥1"); return
            self.result = (name, r, c,
                           self.var_category.get().strip() or "未分类",
                           self.var_background.get().strip()); self.destroy()
        except ValueError:
            messagebox.showerror("错误", "行列请输入有效数字！")

class ResizeMapDialog(tk.Toplevel):
    def __init__(self, parent, cur_row, cur_col):
        super().__init__(parent); self.title("调整地图大小"); self.geometry("380x230")
        self.resizable(False, False); self.transient(parent); self.grab_set(); self.result = None
        self._theme_name = getattr(parent, "_theme_name", "light")
        AppStyles.apply(self, self._theme_name)
        f = ttk.Frame(self, padding=10); f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text=f"当前: {cur_row} 行 × {cur_col} 列").grid(row=0, column=0, columnspan=2, pady=4)
        ttk.Label(f, text="新行数:").grid(row=1, column=0, sticky="w", pady=4)
        self.var_row = tk.StringVar(value=str(cur_row))
        ttk.Entry(f, textvariable=self.var_row, width=12).grid(row=1, column=1, padx=6)
        ttk.Label(f, text="新列数:").grid(row=2, column=0, sticky="w", pady=4)
        self.var_col = tk.StringVar(value=str(cur_col))
        ttk.Entry(f, textvariable=self.var_col, width=12).grid(row=2, column=1, padx=6)
        ttk.Label(f, text="缩小会丢弃右侧/下方内容", foreground="gray").grid(row=3, column=0, columnspan=2, pady=2)
        bf = ttk.Frame(f); bf.grid(row=4, column=0, columnspan=2, pady=8)
        ttk.Button(bf, text="确定", command=self.ok).pack(side=tk.LEFT, padx=8)
        ttk.Button(bf, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=8)
        self._center(parent)
    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    def ok(self):
        try:
            r = int(self.var_row.get()); c = int(self.var_col.get())
            if r < 1 or c < 1: messagebox.showwarning("提示", "行列必须≥1"); return
            self.result = (r, c); self.destroy()
        except ValueError:
            messagebox.showerror("错误", "请输入有效数字！")

class MapInfoDialog(tk.Toplevel):
    """查看/修改地图基本信息：名称、类别、背景"""
    def __init__(self, parent, map_data):
        super().__init__(parent); self.title("地图信息"); self.geometry("440x300")
        self.resizable(False, False); self.transient(parent); self.grab_set(); self.result = None
        self._theme_name = getattr(parent, "_theme_name", "light")
        AppStyles.apply(self, self._theme_name)
        f = ttk.Frame(self, padding=10); f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text="地图名称:").grid(row=0, column=0, sticky="w", pady=4)
        self.var_name = tk.StringVar(value=map_data.map_name)
        ttk.Entry(f, textvariable=self.var_name, width=24).grid(row=0, column=1, padx=6)
        ttk.Label(f, text="类别:").grid(row=1, column=0, sticky="w", pady=4)
        self.var_category = tk.StringVar(value=map_data.category)
        ttk.Entry(f, textvariable=self.var_category, width=24).grid(row=1, column=1, padx=6)
        ttk.Label(f, text="背景:").grid(row=2, column=0, sticky="w", pady=4)
        self.var_background = tk.StringVar(value=map_data.background)
        ttk.Entry(f, textvariable=self.var_background, width=24).grid(row=2, column=1, padx=6)
        bf = ttk.Frame(f); bf.grid(row=3, column=0, columnspan=2, pady=12)
        ttk.Button(bf, text="确定", command=self.ok).pack(side=tk.LEFT, padx=8)
        ttk.Button(bf, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=8)
        self._center(parent)
    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    def ok(self):
        name = self.var_name.get().strip()
        if not name: messagebox.showwarning("提示", "名称不能为空！"); return
        self.result = (name, self.var_category.get().strip() or "未分类",
                       self.var_background.get().strip()); self.destroy()

class PortalEditDialog(tk.Toplevel):
    def __init__(self, parent, old_portal=None):
        super().__init__(parent); self.title("关卡跳转格设置"); self.geometry("520x260")
        self.resizable(False, False); self.transient(parent); self.grab_set(); self.result = None
        self._theme_name = getattr(parent, "_theme_name", "light")
        AppStyles.apply(self, self._theme_name)
        f = ttk.Frame(self, padding=12); f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text="目标关卡路径:").grid(row=0, column=0, sticky="w", pady=6)
        self.var_path = tk.StringVar(value=old_portal["path"] if old_portal else "res://level/")
        ttk.Entry(f, textvariable=self.var_path, width=40).grid(row=0, column=1, padx=6)
        ttk.Label(f, text="颜色(6位16进制):").grid(row=1, column=0, sticky="w", pady=6)
        self.var_color = tk.StringVar(value=old_portal["color"] if old_portal else "ff7733")
        ttk.Entry(f, textvariable=self.var_color, width=15).grid(row=1, column=1, padx=6, sticky="w")
        bf = ttk.Frame(f); bf.grid(row=2, column=0, columnspan=2, pady=12)
        ttk.Button(bf, text="确认", command=self.ok).pack(side=tk.LEFT, padx=8)
        ttk.Button(bf, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=8)
        self._center(parent)
    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    def ok(self):
        path = self.var_path.get().strip(); color = self.var_color.get().strip().lstrip("#")
        if not path: messagebox.showwarning("提示", "路径不能为空！"); return
        if len(color) != 6: messagebox.showwarning("提示", "颜色必须是6位16进制！"); return
        try: int(color, 16)
        except ValueError: messagebox.showwarning("提示", "颜色不是合法16进制！"); return
        self.result = {"path": path, "color": color}; self.destroy()

class TileEditDialog(tk.Toplevel):
    def __init__(self, parent, exist_codes, old_tile=None, categories=None):
        super().__init__(parent); self.parent = parent; self.exist_codes = exist_codes
        self.old_tile = old_tile; self.result = None; self.selected_img_path = ""
        self.categories = categories or ["未分类"]
        if old_tile:
            self.title("编辑瓦片")
            self.var_code = tk.StringVar(value=old_tile.code)
            self.var_name = tk.StringVar(value=old_tile.name)
            self.selected_img_path = old_tile.img_path
            self.var_walkable = tk.BooleanVar(value=old_tile.walkable)
            self.var_layer = tk.StringVar(value=str(old_tile.layer))
            self.var_category = tk.StringVar(value=old_tile.category)
        else:
            self.title("新增瓦片")
            self.var_code = tk.StringVar(); self.var_name = tk.StringVar()
            self.var_walkable = tk.BooleanVar(value=False); self.var_layer = tk.StringVar(value="0")
            self.var_category = tk.StringVar(value="未分类")
        self.geometry("520x520"); self.resizable(False, False)
        self.transient(parent); self.grab_set()
        self._theme_name = getattr(parent, "_theme_name", "light")
        AppStyles.apply(self, self._theme_name)
        f = ttk.Frame(self, padding=10); f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text="瓦片代码:").grid(row=0, column=0, sticky="w", pady=4)
        ent = ttk.Entry(f, textvariable=self.var_code, width=26); ent.grid(row=0, column=1, padx=6)
        if old_tile and old_tile.code == "air": ent.config(state="disabled")
        ttk.Label(f, text="显示名称:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.var_name, width=26).grid(row=1, column=1, padx=6)
        ttk.Label(f, text="图片路径:").grid(row=2, column=0, sticky="w", pady=4)
        self.label_img = ttk.Label(f, text=self.selected_img_path or "未选择", wraplength=200)
        self.label_img.grid(row=2, column=1, padx=6, sticky="w")
        ttk.Button(f, text="选择图片", command=self.select_image).grid(row=3, column=1, sticky="w", pady=2)
        # 图片预览
        ttk.Label(f, text="预览:").grid(row=4, column=0, sticky="nw", pady=4)
        self.preview_lbl = ttk.Label(f, text="(无图片)", anchor="center", width=20)
        self.preview_lbl.grid(row=4, column=1, padx=6, pady=4, sticky="w")
        self._preview_photo = None
        self._update_preview()
        ttk.Label(f, text="可通行:").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Checkbutton(f, variable=self.var_walkable).grid(row=5, column=1, sticky="w", padx=6)
        ttk.Label(f, text="图层:").grid(row=6, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.var_layer, width=10).grid(row=6, column=1, sticky="w", padx=6)
        ttk.Label(f, text="分类:").grid(row=7, column=0, sticky="w", pady=4)
        cb = ttk.Combobox(f, textvariable=self.var_category, values=self.categories, width=14)
        cb.grid(row=7, column=1, sticky="w", padx=6)
        bf = ttk.Frame(f); bf.grid(row=8, column=0, columnspan=2, pady=10)
        ttk.Button(bf, text="确认", command=self.ok).pack(side=tk.LEFT, padx=8)
        ttk.Button(bf, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=8)
        self._center(parent)
    def _update_preview(self):
        """更新图片预览（64x64）。"""
        p = self.selected_img_path
        if p and os.path.exists(p):
            try:
                from PIL import Image as _PILImage, ImageTk as _PILImageTk
                img = _PILImage.open(p)
                img.thumbnail((64, 64))
                self._preview_photo = _PILImageTk.PhotoImage(img)
                self.preview_lbl.config(image=self._preview_photo, text="")
            except Exception:
                self._preview_photo = None
                self.preview_lbl.config(image="", text="(无法显示)")
        else:
            self._preview_photo = None
            self.preview_lbl.config(image="", text="(无图片)")
    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    def select_image(self):
        p = filedialog.askopenfilename(title="选择瓦片图片", filetypes=[("图片","*.png;*.jpg;*.jpeg;*.bmp")])
        if p: self.selected_img_path = p; self.label_img.config(text=p); self._update_preview()
    def ok(self):
        code = self.var_code.get().strip(); name = self.var_name.get().strip()
        if not code: messagebox.showwarning("提示", "瓦片代码不能为空！"); return
        if not name: messagebox.showwarning("提示", "显示名称不能为空！"); return
        if not (self.old_tile and self.old_tile.code == code):
            if code in self.exist_codes: messagebox.showwarning("冲突", "该代码已存在！"); return
        cat = self.var_category.get().strip() or "未分类"
        self.result = (code, name, self.selected_img_path, self.var_walkable.get(),
                       self.var_layer.get(), cat); self.destroy()

class BatchTileDialog(tk.Toplevel):
    """批量加入瓦片：表格录入，横向属性，竖向瓦片"""
    COLS = [("code", "代码", 80), ("name", "名称", 100), ("img_path", "图片路径", 260),
            ("category", "分类", 80), ("walkable", "可通行", 60), ("layer", "图层", 50)]
    def __init__(self, parent, exist_codes):
        super().__init__(parent); self.title("批量加入瓦片"); self.geometry("900x600")
        self.transient(parent); self.grab_set(); self.exist_codes = exist_codes; self.result = []
        # 可缩放 + 最小尺寸
        self.resizable(True, True); self.minsize(720, 480)
        self._theme_name = getattr(parent, "_theme_name", "light")
        AppStyles.apply(self, self._theme_name)
        top = ttk.Frame(self, padding=6); top.pack(fill=tk.X)
        ttk.Label(top, text="双击单元格编辑。可通行列填 yes/no，图片路径可手动粘贴或点选。").pack(anchor="w")
        bf = ttk.Frame(top); bf.pack(anchor="w", pady=4)
        ttk.Button(bf, text="添加行", command=self.add_row).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="删除选中行", command=self.del_row).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="批量选择图片", command=self.batch_pick_images).pack(side=tk.LEFT, padx=2)
        tree_frame = ttk.Frame(self); tree_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        cols = [c[0] for c in self.COLS]
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=14)
        for key, label, w in self.COLS:
            self.tree.heading(key, text=label); self.tree.column(key, width=w, anchor="w")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y); self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", self.on_edit)
        for _ in range(5): self.add_row(silent=True)
        bot = ttk.Frame(self, padding=6); bot.pack(fill=tk.X)
        ttk.Button(bot, text="确认导入", command=self.ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bot, text="取消", command=self.destroy).pack(side=tk.RIGHT, padx=4)
        self._center(parent)
    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    def add_row(self, silent=False):
        self.tree.insert("", tk.END, values=("", "", "", "未分类", "no", "0"))
    def del_row(self):
        for iid in self.tree.selection(): self.tree.delete(iid)
    def batch_pick_images(self):
        paths = filedialog.askopenfilenames(title="批量选择瓦片图片", filetypes=[("图片","*.png;*.jpg;*.jpeg;*.bmp")])
        if not paths: return
        items = self.tree.get_children()
        for i, p in enumerate(paths):
            base = os.path.splitext(os.path.basename(p))[0]
            if i < len(items):
                vals = list(self.tree.item(items[i], "values"))
                if not vals[0]: vals[0] = base
                if not vals[1]: vals[1] = base
                vals[2] = p
                self.tree.item(items[i], values=vals)
            else:
                self.tree.insert("", tk.END, values=(base, base, p, "未分类", "no", "0"))
    def on_edit(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell": return
        iid = self.tree.identify_row(event.y); col = self.tree.identify_column(event.x)
        if not iid: return
        col_idx = int(col.replace("#", "")) - 1
        col_key = self.COLS[col_idx][0]
        cur = self.tree.item(iid, "values")[col_idx]
        x, y, w, h = self.tree.bbox(iid, col)
        if col_key == "walkable":
            var = tk.StringVar(value=cur)
            cb = ttk.Combobox(self.tree, textvariable=var, values=["yes", "no"], state="readonly", width=w//7)
            cb.place(x=x, y=y, width=w, height=h); cb.focus_set()
            def commit(e=None):
                vals = list(self.tree.item(iid, "values")); vals[col_idx] = var.get()
                self.tree.item(iid, values=vals); cb.destroy()
            cb.bind("<<ComboboxSelected>>", commit); cb.bind("<FocusOut>", commit)
        elif col_key == "img_path":
            p = filedialog.askopenfilename(title="选择图片", filetypes=[("图片","*.png;*.jpg;*.jpeg;*.bmp")])
            if p:
                vals = list(self.tree.item(iid, "values")); vals[col_idx] = p
                self.tree.item(iid, values=vals)
        else:
            var = tk.StringVar(value=cur)
            ent = ttk.Entry(self.tree, textvariable=var, width=w//7)
            ent.place(x=x, y=y, width=w, height=h); ent.focus_set(); ent.select_range(0, tk.END)
            def commit(e=None):
                vals = list(self.tree.item(iid, "values")); vals[col_idx] = var.get()
                self.tree.item(iid, values=vals); ent.destroy()
            ent.bind("<Return>", commit); ent.bind("<FocusOut>", commit)
    def ok(self):
        rows = []
        seen = set(self.exist_codes)
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, "values")
            code = vals[0].strip()
            if not code: continue
            if code in seen:
                messagebox.showwarning("跳过", f"代码 {code} 已存在或重复，已跳过"); continue
            seen.add(code)
            name = vals[1].strip() or code
            img = vals[2].strip()
            cat = vals[3].strip() or "未分类"
            walk = str(vals[4]).strip().lower() in ("yes", "true", "1", "y")
            layer = str(vals[5]).strip() or "0"
            rows.append((code, name, img, walk, layer, cat))
        if not rows: messagebox.showinfo("提示", "没有有效数据"); return
        self.result = rows; self.destroy()

class ShortcutSettingsDialog(tk.Toplevel):
    LABEL_MAP = {
        "save":"保存","save_as":"另存为","new_map":"新建地图","open_mdmap":"打开 .mdmap",
        "undo":"撤销","redo":"重做","redo_alt":"重做(备选)","tile_editor":"瓦片库编辑器",
        "preferences":"首选项","tool_brush":"画笔","tool_eraser":"橡皮","tool_rect":"矩形","tool_fill":"填充",
        "tool_copy":"复制选择","attr_start":"属性:起始点","attr_end":"属性:结束点",
        "attr_key":"属性:钥匙","attr_portal":"属性:跳转格","tool_pan":"画布拖拽",
    }
    def __init__(self, parent, shortcuts):
        super().__init__(parent); self.title("快捷键设置"); self.geometry("640x680")
        self.transient(parent); self.grab_set(); self.shortcuts = dict(shortcuts)
        # 可缩放 + 最小尺寸
        self.resizable(True, True); self.minsize(560, 520)
        self._theme_name = getattr(parent, "_theme_name", "light")
        AppStyles.apply(self, self._theme_name)
        mf = ttk.Frame(self, padding=10); mf.pack(fill=tk.BOTH, expand=True)
        ttk.Label(mf, text="双击一行后按下新组合键。", font=AppFonts.get("small", self)).pack(anchor="w", pady=(0,8))
        self.tree = ttk.Treeview(mf, columns=("a","k"), show="headings", height=18)
        self.tree.heading("a", text="功能"); self.tree.heading("k", text="快捷键")
        self.tree.column("a", width=260); self.tree.column("k", width=200)
        self.tree.pack(fill=tk.BOTH, expand=True)
        for key in DEFAULT_SHORTCUTS:
            self.tree.insert("", tk.END, iid=key, values=(self.LABEL_MAP.get(key,key),
                self._fmt(self.shortcuts.get(key, DEFAULT_SHORTCUTS[key]))))
        self.tree.bind("<Double-1>", self.on_dbl)
        bf = ttk.Frame(mf); bf.pack(fill=tk.X, pady=(10,0))
        ttk.Button(bf, text="恢复默认", command=self.reset).pack(side=tk.LEFT, padx=4)
        ttk.Button(bf, text="确定", command=self.ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bf, text="取消", command=self.destroy).pack(side=tk.RIGHT, padx=4)
        self.bind("<Key>", self.on_key); self._editing = None
        self._center(parent)
    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    def _fmt(self, b): return b.strip("<>").replace("-","+").capitalize().replace("Control","Ctrl")
    def on_dbl(self, e):
        sel = self.tree.selection()
        if not sel: return
        iid = sel[0]
        if iid == "redo_alt": messagebox.showinfo("提示","备选绑定无需单独修改"); return
        self._editing = iid; self.tree.set(iid, "k", ">>> 按下新键 <<<")
    def on_key(self, event):
        if not self._editing: return
        ks = event.keysym.lower(); state = event.state & ~0x12
        parts = []
        if state & 0x4: parts.append("Control")
        if state & 0x1: parts.append("Shift")
        if state & 0x20000: parts.append("Alt")
        if ks in {"control_l","control_r","shift_l","shift_r","alt_l","alt_r","caps_lock","num_lock","scroll_lock","tab","escape"}: return
        if len(ks)==1 or ks.startswith("f") or ks in ("space","return","backspace","delete","insert","home","end","page_up","page_down","up","down","left","right"):
            parts.append(ks); nb = "<" + "-".join(parts) + ">"
            self.shortcuts[self._editing] = nb
            if self._editing == "redo":
                self.shortcuts["redo_alt"] = nb.upper().replace("SHIFT-","").replace("<CTRL-Y>","<Control-Shift-Z>")
            self.tree.set(self._editing, "k", self._fmt(nb)); self._editing = None
    def reset(self):
        if messagebox.askyesno("确认","恢复默认？"):
            self.shortcuts = dict(DEFAULT_SHORTCUTS)
            for k in DEFAULT_SHORTCUTS: self.tree.item(k, values=(self.LABEL_MAP.get(k,k), self._fmt(self.shortcuts[k])))
    def ok(self):
        seen = {}
        for k, v in self.shortcuts.items():
            if k == "redo_alt": continue
            if v in seen: messagebox.showwarning("冲突","快捷键冲突！"); return
            seen[v] = k
        if save_shortcuts(self.shortcuts): self.destroy()

# ===================== 属性图标绘制 =====================
_ATTR_ICON_CACHE = {}
def make_attr_icon(color_hex, shape, size):
    """生成属性形状图标 (RGBA) 的 PhotoImage，带缓存。
    color_hex: #RRGGBBAA 或 #RRGGBB；shape: circle/square/octagon/triangle"""
    key = (color_hex, shape, size)
    if key in _ATTR_ICON_CACHE:
        return _ATTR_ICON_CACHE[key]
    # 解析颜色
    ch = color_hex.lstrip("#")
    if len(ch) == 8:
        r, g, b, a = int(ch[0:2],16), int(ch[2:4],16), int(ch[4:6],16), int(ch[6:8],16)
    elif len(ch) == 6:
        r, g, b, a = int(ch[0:2],16), int(ch[2:4],16), int(ch[4:6],16), 255
    else:
        r, g, b, a = 255, 255, 255, 200
    img = Image.new("RGBA", (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    pad = max(1, size // 8)
    fill = (r, g, b, a)
    outline = (max(0,r-40), max(0,g-40), max(0,b-40), 255)
    if shape == "circle":
        draw.ellipse((pad, pad, size-pad, size-pad), fill=fill, outline=outline, width=max(1,size//16))
    elif shape == "square":
        draw.rectangle((pad, pad, size-pad, size-pad), fill=fill, outline=outline, width=max(1,size//16))
    elif shape == "octagon":
        # 八边形 8 个顶点
        m = size * 0.15
        pts = [(m,0),(size-m,0),(size,m),(size,size-m),(size-m,size),(m,size),(0,size-m),(0,m)]
        # 缩放到 pad 内
        scale = (size - 2*pad) / size
        pts = [(pad + (x*scale if x>0 else 0) + (0 if x==0 else (x-1)*scale*(size-2*pad)/size), 
                pad + (y*scale if y>0 else 0) + (0 if y==0 else (y-1)*scale*(size-2*pad)/size)) for x,y in pts]
        # 简化: 直接构造规整八边形
        cx = size / 2; cy = size / 2; rad = (size - 2*pad) / 2
        import math
        pts = []
        for i in range(8):
            ang = math.pi/8 + i * math.pi/4
            pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
        draw.polygon(pts, fill=fill, outline=outline, width=max(1,size//16))
    elif shape == "triangle":
        draw.polygon([(size/2, pad), (pad, size-pad), (size-pad, size-pad)], fill=fill, outline=outline, width=max(1,size//16))
    else:
        draw.ellipse((pad, pad, size-pad, size-pad), fill=fill)
    photo = ImageTk.PhotoImage(img)
    _ATTR_ICON_CACHE[key] = photo
    return photo

# ===================== 属性列表编辑器 =====================
class AttributeEditDialog(tk.Toplevel):
    """新增/编辑一个属性定义。"""
    def __init__(self, parent, attr_lib, old_attr=None):
        super().__init__(parent); self.title("编辑属性" if old_attr else "新增属性")
        self.geometry("460x400"); self.resizable(False, False)
        self.transient(parent); self.grab_set()
        self.attr_lib = attr_lib; self.old_attr = old_attr; self.result = None
        self._theme_name = getattr(parent, "_theme_name", "light")
        AppStyles.apply(self, self._theme_name)
        f = ttk.Frame(self, padding=10); f.pack(fill=tk.BOTH, expand=True)
        # 名称
        ttk.Label(f, text="名称:").grid(row=0, column=0, sticky="w", pady=4)
        self.var_name = tk.StringVar(value=old_attr.name if old_attr else "")
        ttk.Entry(f, textvariable=self.var_name, width=24).grid(row=0, column=1, padx=6)
        # ID
        ttk.Label(f, text="ID(单字符):").grid(row=1, column=0, sticky="w", pady=4)
        self.var_id = tk.StringVar(value=old_attr.id_char if old_attr else "")
        ent_id = ttk.Entry(f, textvariable=self.var_id, width=4)
        ent_id.grid(row=1, column=1, sticky="w", padx=6)
        if old_attr and old_attr.builtin:
            ent_id.config(state="disabled")
        # 颜色
        ttk.Label(f, text="颜色(8位16进制):").grid(row=2, column=0, sticky="w", pady=4)
        color_row = ttk.Frame(f); color_row.grid(row=2, column=1, sticky="w", padx=6)
        self.var_color = tk.StringVar(value=(old_attr.color if old_attr else "#FFFFFFFF"))
        ttk.Entry(color_row, textvariable=self.var_color, width=12).pack(side=tk.LEFT)
        ttk.Button(color_row, text="选色", command=self.pick_color).pack(side=tk.LEFT, padx=4)
        # 形状
        ttk.Label(f, text="形状:").grid(row=3, column=0, sticky="w", pady=4)
        self.var_shape = tk.StringVar(value=(old_attr.shape if old_attr else "circle"))
        cb_shape = ttk.Combobox(f, textvariable=self.var_shape, state="readonly", width=10)
        cb_shape["values"] = [ATTR_SHAPE_LABELS[s] for s in ATTR_SHAPES]
        cb_shape.current(ATTR_SHAPES.index(self.var_shape.get()))
        cb_shape.grid(row=3, column=1, sticky="w", padx=6)
        # 单例
        ttk.Label(f, text="整图唯一:").grid(row=4, column=0, sticky="w", pady=4)
        self.var_singleton = tk.BooleanVar(value=(old_attr.singleton if old_attr else False))
        ttk.Checkbutton(f, variable=self.var_singleton).grid(row=4, column=1, sticky="w", padx=6)
        # 预览
        ttk.Label(f, text="预览:").grid(row=5, column=0, sticky="nw", pady=4)
        self.preview_lbl = tk.Label(f, bg="#222222", width=4, height=2)
        self.preview_lbl.grid(row=5, column=1, sticky="w", padx=6, pady=4)
        self._update_preview()
        for v in (self.var_color, self.var_shape):
            v.trace_add("write", lambda *_: self._update_preview())
        # 按钮
        bf = ttk.Frame(f); bf.grid(row=6, column=0, columnspan=2, pady=10)
        ttk.Button(bf, text="确认", command=self.ok).pack(side=tk.LEFT, padx=8)
        ttk.Button(bf, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=8)
        self._center(parent)
    def _shape_key(self):
        label = self.var_shape.get()
        for k, v in ATTR_SHAPE_LABELS.items():
            if v == label: return k
        return "circle"
    def _update_preview(self):
        color = self.var_color.get().strip() or "#FFFFFFFF"
        shape = self._shape_key()
        try:
            ic = make_attr_icon(color, shape, 32)
            self.preview_lbl.config(image=ic)
            self.preview_lbl.image = ic
        except Exception:
            self.preview_lbl.config(image="")
    def pick_color(self):
        """弹出系统颜色选择器，选完写入 var_color。"""
        from tkinter import colorchooser
        cur = self.var_color.get().strip()
        # colorchooser 接受 #RRGGBB
        init = cur[:7] if cur.startswith("#") and len(cur) >= 7 else "#ffffff"
        try:
            result = colorchooser.askcolor(title="选择颜色", initialcolor=init)
            if result and result[1]:
                # result = ((r,g,b), '#rrggbb')
                rgb_hex = result[1].upper()  # #RRGGBB
                # 保留原 alpha (8 位色)，否则默认 FF
                alpha = cur[7:9] if len(cur) >= 9 else "FF"
                self.var_color.set(rgb_hex + alpha)
        except Exception as e:
            messagebox.showerror("错误", f"颜色选择失败: {e}")
    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    def ok(self):
        name = self.var_name.get().strip()
        id_char = self.var_id.get().strip()
        color = self.var_color.get().strip()
        shape = self._shape_key()
        singleton = self.var_singleton.get()
        if not name: messagebox.showwarning("提示", "名称不能为空"); return
        # ID 校验
        if not self.old_attr or not self.old_attr.builtin:
            if not id_char or len(id_char) != 1:
                messagebox.showwarning("提示", "ID 必须是单个字符"); return
            if id_char in FORBIDDEN_ATTR_IDS:
                messagebox.showwarning("提示", f"ID 不能使用 {' / '.join(FORBIDDEN_ATTR_IDS)} (保留字符)"); return
            existing = self.attr_lib.get_by_id(id_char)
            if existing is not None and (not self.old_attr or existing.id_char != self.old_attr.id_char):
                messagebox.showwarning("冲突", f"ID '{id_char}' 已被使用"); return
        # 颜色校验
        ch = color.lstrip("#")
        if len(ch) not in (6, 8):
            messagebox.showwarning("提示", "颜色需为 6 或 8 位十六进制"); return
        try: int(ch, 16)
        except ValueError:
            messagebox.showwarning("提示", "颜色不是合法十六进制"); return
        if len(ch) == 6:
            color = "#" + ch + "FF"
        builtin = self.old_attr.builtin if self.old_attr else False
        opts = list(self.old_attr.options) if self.old_attr and self.old_attr.options else []
        self.result = AttributeDefine(name, id_char, color, shape, builtin=builtin,
                                     options=opts, singleton=singleton)
        self.destroy()

# ===================== 瓦片属性编辑器 =====================
class TileAttributeEditor(tk.Toplevel):
    """编辑单个瓦片的 ABCD 4 个属性槽。"""
    SLOT_NAMES = {"A":"左上 A", "B":"右上 B", "C":"左下 C", "D":"右下 D"}
    def __init__(self, parent, map_data, r, c, attr_lib):
        super().__init__(parent); self.title(f"瓦片属性编辑器 ({r},{c})"); self.geometry("520x580")
        self.transient(parent); self.grab_set()
        self.map_data = map_data; self.r = r; self.c = c; self.attr_lib = attr_lib
        self.result = None
        # 可缩放 + 最小尺寸（内部使用滚动容器）
        self.resizable(True, True); self.minsize(460, 440)
        self._theme_name = getattr(parent, "_theme_name", "light")
        AppStyles.apply(self, self._theme_name)
        # 当前瓦片状态副本
        self.slots = map_data.get_slots(r, c)
        self.options = {}
        for s in MapData.SLOT_ORDER:
            slot = self.slots.get(s)
            if slot:
                self.options[s] = dict(map_data.tile_attr_options.get((r, c, s), {}))
        # 外层：按钮栏固定在底部，上方使用滚动容器
        outer = ttk.Frame(self); outer.pack(fill=tk.BOTH, expand=True)
        scroll = ScrollableFrame(outer, theme_name=self._theme_name); scroll.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        f = scroll.inner
        ttk.Label(f, text=f"位置: 行 {r} 列 {c}", font=AppFonts.get("body", self, bold=True)).pack(anchor="w", pady=(0,8))
        # 4 个槽
        self.slot_widgets = {}
        for s in MapData.SLOT_ORDER:
            self._build_slot_row(f, s)
        bf = ttk.Frame(outer); bf.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        ttk.Button(bf, text="确认", command=self.ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bf, text="取消", command=self.destroy).pack(side=tk.RIGHT, padx=4)
        self._center(parent)
    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    def _build_slot_row(self, parent, slot):
        frame = ttk.LabelFrame(parent, text=self.SLOT_NAMES[slot], padding=6)
        frame.pack(fill=tk.X, pady=4)
        # 复选框
        var_has = tk.BooleanVar(value=self.slots.get(slot) is not None)
        cb = ttk.Checkbutton(frame, text="有属性", variable=var_has,
                             command=lambda s=slot: self._on_toggle(s))
        cb.pack(anchor="w")
        # 属性选择
        combo_frame = ttk.Frame(frame); combo_frame.pack(fill=tk.X, pady=2)
        ttk.Label(combo_frame, text="属性:").pack(side=tk.LEFT)
        var_attr = tk.StringVar(value=self.attr_lib.label_for_id(self.slots.get(slot)) if self.slots.get(slot) else "")
        cmb = ttk.Combobox(combo_frame, textvariable=var_attr, state="readonly", width=12)
        cmb["values"] = self.attr_lib.get_names()
        cmb.pack(side=tk.LEFT, padx=4)
        if self.slots.get(slot): cmb.set(self.attr_lib.label_for_id(self.slots.get(slot)))
        # 选项区（动态）
        opts_frame = ttk.Frame(frame); opts_frame.pack(fill=tk.X, pady=2)
        # 备注标签：未选中时禁用
        disable_hint = ttk.Label(frame, text="(未启用)", foreground="gray")
        disable_hint.pack(anchor="w")
        self.slot_widgets[slot] = {
            "var_has": var_has, "var_attr": var_attr, "cmb": cmb,
            "opts_frame": opts_frame, "opt_entries": {},
            "disable_hint": disable_hint
        }
        cmb.bind("<<ComboboxSelected>>", lambda e, s=slot: self._on_attr_change(s))
        self._on_toggle(slot, _initial=True)
    def _on_toggle(self, slot, _initial=False):
        w = self.slot_widgets[slot]
        has = w["var_has"].get()
        if has:
            w["disable_hint"].pack_forget()
            w["cmb"].config(state="readonly")
            if not w["var_attr"].get() and self.attr_lib.attrs:
                w["var_attr"].set(self.attr_lib.attrs[0].name)
            self._on_attr_change(slot, _initial=_initial)
        else:
            w["disable_hint"].pack(anchor="w")
            w["cmb"].config(state="disabled")
            for child in w["opts_frame"].winfo_children():
                child.destroy()
            w["opt_entries"].clear()
    def _on_attr_change(self, slot, _initial=False):
        w = self.slot_widgets[slot]
        # 清空选项区
        for child in w["opts_frame"].winfo_children():
            child.destroy()
        w["opt_entries"].clear()
        name = w["var_attr"].get()
        attr = self.attr_lib.get_by_name(name)
        if not attr: return
        # 为该属性的所有 option 字段构建输入框
        for opt in attr.options:
            ttk.Label(w["opts_frame"], text=opt["name"]+":").pack(anchor="w")
            cur_val = self.options.get(slot, {}).get(opt["name"], opt["default"])
            var = tk.StringVar(value=cur_val)
            ent = ttk.Entry(w["opts_frame"], textvariable=var, width=30)
            ent.pack(anchor="w", padx=8)
            w["opt_entries"][opt["name"]] = var
    def ok(self):
        # 收集结果
        new_slots = {"A": None, "B": None, "C": None, "D": None}
        new_options = {}
        for s in MapData.SLOT_ORDER:
            w = self.slot_widgets[s]
            if not w["var_has"].get():
                continue
            name = w["var_attr"].get()
            attr = self.attr_lib.get_by_name(name)
            if not attr:
                continue
            # 单例检查
            if attr.singleton:
                # 检查其它槽位是否已经设了同名属性
                for s2 in MapData.SLOT_ORDER:
                    if s2 == s: continue
                    w2 = self.slot_widgets[s2]
                    if w2["var_has"].get() and w2["var_attr"].get() == name:
                        messagebox.showwarning("冲突", f"'{name}' 是整图唯一属性，不能在 {self.SLOT_NAMES[s]} 和 {self.SLOT_NAMES[s2]} 同时设置")
                        return
            new_slots[s] = attr.id_char
            opts = {}
            for opt in attr.options:
                v = w["opt_entries"].get(opt["name"])
                opts[opt["name"]] = v.get() if v else opt["default"]
            if opts:
                new_options[s] = opts
        self.result = (new_slots, new_options)
        self.destroy()

# ===================== 首选项 =====================
class PreferencesDialog(tk.Toplevel):
    """统一首选项窗口: 3 标签页 (显示/快捷键/属性列表)。"""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.title("首选项"); self.geometry("780x680")
        self.transient(parent); self.grab_set()
        self.app = app; self.result = None
        self.resizable(True, True); self.minsize(640, 520)
        self._theme_name = getattr(parent, "_theme_name", "light")
        AppStyles.apply(self, self._theme_name)
        # Notebook
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        # 三个标签页
        self._build_display_tab()
        self._build_shortcuts_tab()
        self._build_attrs_tab()
        # 底部按钮
        bf = ttk.Frame(self); bf.pack(fill=tk.X, padx=8, pady=(0,8))
        ttk.Button(bf, text="确定", command=self.ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bf, text="取消", command=self.destroy).pack(side=tk.RIGHT, padx=4)
        self._center(parent)
    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0,x)}+{max(0,y)}")
    # ---------- 显示标签页 ----------
    def _build_display_tab(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="显示")
        f = ttk.LabelFrame(tab, text="缩放", padding=10); f.pack(fill=tk.X, padx=8, pady=8)
        cfg = self.app.cfg
        # 屏幕缩放
        ttk.Label(f, text="屏幕缩放 (DPI):").grid(row=0, column=0, sticky="w", pady=4)
        self.var_auto_dpi = tk.BooleanVar(value=cfg.get("auto_dpi", True))
        ttk.Checkbutton(f, text="自动检测系统 DPI", variable=self.var_auto_dpi,
                        command=self._on_auto_dpi_toggle).grid(row=0, column=1, sticky="w", padx=6)
        self.var_screen_scale = tk.StringVar(value=str(cfg.get("screen_scale", 100)))
        self.cmb_screen = ttk.Combobox(f, textvariable=self.var_screen_scale,
                                        values=["自动", "100", "125", "150", "175", "200"],
                                        state="readonly", width=8)
        self.cmb_screen.set("自动" if self.var_auto_dpi.get() else str(self.var_screen_scale.get()))
        self.cmb_screen.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(f, text="取消自动后手动选择 DPI 倍率", foreground="gray").grid(row=2, column=1, sticky="w", padx=6)
        # UI 缩放
        ttk.Label(f, text="UI 缩放:").grid(row=3, column=0, sticky="w", pady=(8,4))
        self.var_ui_scale = tk.DoubleVar(value=float(cfg.get("ui_scale", 1.0)))
        self.lbl_ui_scale = ttk.Label(f, text=f"{self.var_ui_scale.get():.2f}x")
        self.lbl_ui_scale.grid(row=3, column=1, sticky="w", padx=6)
        scl = ttk.Scale(f, from_=0.8, to=2.0, variable=self.var_ui_scale,
                        orient=tk.HORIZONTAL, length=200, command=self._on_ui_scale_change)
        scl.grid(row=4, column=1, sticky="w", padx=6)
        # 立即应用
        ttk.Button(f, text="立即应用", command=self._apply_display_now).grid(row=5, column=1, sticky="w", padx=6, pady=6)
        # 主题
        tf = ttk.LabelFrame(tab, text="主题", padding=10); tf.pack(fill=tk.X, padx=8, pady=8)
        self.var_theme = tk.StringVar(value=cfg.get("theme", "light"))
        ttk.Radiobutton(tf, text="浅色", value="light", variable=self.var_theme).pack(anchor="w")
        ttk.Radiobutton(tf, text="深色", value="dark", variable=self.var_theme).pack(anchor="w")
        ttk.Label(tf, text="主题切换需要重新打开对话框才完全生效", foreground="gray").pack(anchor="w", pady=(4,0))
    def _on_auto_dpi_toggle(self):
        if self.var_auto_dpi.get():
            self.cmb_screen.set("自动")
            self.cmb_screen.config(state="disabled")
        else:
            self.cmb_screen.config(state="readonly")
            if self.cmb_screen.get() == "自动":
                self.cmb_screen.set("100")
    def _on_ui_scale_change(self, _=None):
        self.lbl_ui_scale.config(text=f"{self.var_ui_scale.get():.2f}x")
    def _apply_display_now(self):
        """立即应用显示设置到当前窗口。"""
        ui = float(self.var_ui_scale.get())
        AppFonts._ui_scale = ui
        AppStyles.apply(self, self.var_theme.get())
        messagebox.showinfo("已应用", f"UI 缩放已设为 {ui:.2f}x\n\n完整生效请点击'确定'保存后重启程序。")
    # ---------- 快捷键标签页 ----------
    def _build_shortcuts_tab(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="快捷键")
        mf = ttk.Frame(tab, padding=8); mf.pack(fill=tk.BOTH, expand=True)
        self._sc_shortcuts = dict(self.app.shortcuts)
        ttk.Label(mf, text="双击一行后按下新组合键。", font=AppFonts.get("small", self)).pack(anchor="w", pady=(0,8))
        self.sc_tree = ttk.Treeview(mf, columns=("a","k"), show="headings", height=14)
        self.sc_tree.heading("a", text="功能"); self.sc_tree.heading("k", text="快捷键")
        self.sc_tree.column("a", width=240); self.sc_tree.column("k", width=180)
        sc_sb = ttk.Scrollbar(mf, orient="vertical", command=self.sc_tree.yview)
        sc_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.sc_tree.configure(yscrollcommand=sc_sb.set)
        self.sc_tree.pack(fill=tk.BOTH, expand=True)
        for key in DEFAULT_SHORTCUTS:
            self.sc_tree.insert("", tk.END, iid=key, values=(self._sc_label(key),
                self._sc_fmt(self._sc_shortcuts.get(key, DEFAULT_SHORTCUTS[key]))))
        self.sc_tree.bind("<Double-1>", self._sc_on_dbl)
        bf = ttk.Frame(mf); bf.pack(fill=tk.X, pady=(8,0))
        ttk.Button(bf, text="恢复默认", command=self._sc_reset).pack(side=tk.LEFT, padx=4)
        self.bind("<Key>", self._sc_on_key); self._sc_editing = None
    def _sc_label(self, key):
        return ShortcutSettingsDialog.LABEL_MAP.get(key, key)
    def _sc_fmt(self, b): return b.strip("<>").replace("-","+").capitalize().replace("Control","Ctrl")
    def _sc_on_dbl(self, e):
        sel = self.sc_tree.selection()
        if not sel: return
        self._sc_editing = sel[0]
        messagebox.showinfo("录入", "请按下新的组合键（按 Esc 取消）", parent=self)
    def _sc_on_key(self, e):
        if not self._sc_editing: return
        if e.keysym == "Escape":
            self._sc_editing = None; return
        # 组合键字符串
        parts = []
        if e.state & 0x4: parts.append("Control")
        if e.state & 0x1: parts.append("Shift")
        if e.state & 0x2: parts.append("Alt")
        key = e.keysym
        if key in ("Control_L","Control_R","Shift_L","Shift_R","Alt_L","Alt_R"): return
        parts.append(key)
        binding = "<" + "-".join(parts) + ">"
        # 简单单键
        if len(parts) == 1 and not (e.state & 0x7):
            binding = parts[0]
        self._sc_shortcuts[self._sc_editing] = binding
        self.sc_tree.item(self._sc_editing, values=(self._sc_label(self._sc_editing), self._sc_fmt(binding)))
        self._sc_editing = None
    def _sc_reset(self):
        self._sc_shortcuts = dict(DEFAULT_SHORTCUTS)
        for key in DEFAULT_SHORTCUTS:
            self.sc_tree.item(key, values=(self._sc_label(key), self._sc_fmt(self._sc_shortcuts[key])))
    # ---------- 属性列表标签页 ----------
    def _build_attrs_tab(self):
        tab = ttk.Frame(self.nb); self.nb.add(tab, text="属性列表")
        top = ttk.Frame(tab, padding=6); top.pack(fill=tk.X)
        ttk.Label(top, text="内置: 起始点/终点/钥匙/跳转格。可新增自定义属性。", style="Muted.TLabel").pack(anchor="w")
        bf = ttk.Frame(top); bf.pack(anchor="w", pady=4)
        ttk.Button(bf, text="新增", command=lambda: self._attr_action("add")).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="编辑", command=lambda: self._attr_action("edit")).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="删除", command=lambda: self._attr_action("delete")).pack(side=tk.LEFT, padx=2)
        ttk.Separator(bf, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(bf, text="导入 .mdattr", command=lambda: self._attr_action("import")).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="导出 .mdattr", command=lambda: self._attr_action("export")).pack(side=tk.LEFT, padx=2)
        tree_frame = ttk.Frame(tab); tree_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        cols = ("name","id","color","shape","singleton","builtin")
        self.attr_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=12)
        labels = {"name":"名称","id":"ID","color":"颜色","shape":"形状","singleton":"整图唯一","builtin":"内置"}
        widths = {"name":120,"id":40,"color":80,"shape":70,"singleton":70,"builtin":50}
        for k in cols:
            self.attr_tree.heading(k, text=labels[k]); self.attr_tree.column(k, width=widths[k], anchor="w")
        attr_sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.attr_tree.yview)
        attr_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.attr_tree.configure(yscrollcommand=attr_sb.set)
        self.attr_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.attr_tree.bind("<Double-1>", lambda e: self._attr_action("edit"))
        self._attr_refresh()
    def _attr_refresh(self):
        for i in self.attr_tree.get_children(): self.attr_tree.delete(i)
        for a in self.app.attr_lib.attrs:
            shape_label = ATTR_SHAPE_LABELS.get(a.shape, a.shape)
            self.attr_tree.insert("", tk.END, iid=a.id_char,
                values=(a.name, a.id_char, a.color, shape_label,
                        "是" if a.singleton else "否", "是" if a.builtin else "否"))
    def _attr_action(self, action):
        if action == "add":
            dlg = AttributeEditDialog(self, self.app.attr_lib); self.wait_window(dlg)
            if dlg.result:
                self.app.attr_lib.add(dlg.result); self.app.attr_lib.save(); self._attr_refresh()
                if hasattr(self.app, "_on_attr_lib_changed"): self.app._on_attr_lib_changed()
        elif action == "edit":
            sel = self.attr_tree.selection()
            if not sel: messagebox.showinfo("提示","请先选中一条"); return
            old = self.app.attr_lib.get_by_id(sel[0])
            if not old: return
            dlg = AttributeEditDialog(self, self.app.attr_lib, old_attr=old); self.wait_window(dlg)
            if dlg.result:
                self.app.attr_lib.update(old.id_char, dlg.result); self.app.attr_lib.save(); self._attr_refresh()
                if hasattr(self.app, "_on_attr_lib_changed"): self.app._on_attr_lib_changed()
        elif action == "delete":
            sel = self.attr_tree.selection()
            if not sel: return
            id_char = sel[0]; attr = self.app.attr_lib.get_by_id(id_char)
            if not attr: return
            if attr.builtin:
                messagebox.showwarning("禁止","内置属性不能删除"); return
            if messagebox.askyesno("确认", f"删除属性 '{attr.name}' (ID={id_char})？\n地图中使用此属性的格子也会被清除。"):
                self.app.attr_lib.remove(id_char); self.app.attr_lib.save(); self._attr_refresh()
                if hasattr(self.app, "_on_attr_lib_changed"): self.app._on_attr_lib_changed()
                # 若 app 有 map_data，清除地图中该属性
                if hasattr(self.app, "map_data") and self.app.map_data is not None:
                    try: self.app.map_data.remove_attr_everywhere(id_char)
                    except Exception: pass
        elif action == "import":
            p = filedialog.askopenfilename(filetypes=[("MDAttr","*.mdattr")], title="导入属性列表")
            if not p: return
            try:
                with open(p, "r", encoding="utf-8") as f: data = json.load(f)
                self.app.attr_lib.load_from_dict(data); self.app.attr_lib.save(); self._attr_refresh()
                if hasattr(self.app, "_on_attr_lib_changed"): self.app._on_attr_lib_changed()
                messagebox.showinfo("成功", f"已导入 {len(self.app.attr_lib.attrs)} 个属性")
            except Exception as e:
                messagebox.showerror("失败", str(e))
        elif action == "export":
            p = filedialog.asksaveasfilename(defaultextension=".mdattr", filetypes=[("MDAttr","*.mdattr")])
            if not p: return
            try:
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(self.app.attr_lib.to_dict(), f, indent=2, ensure_ascii=False)
                messagebox.showinfo("成功", f"已导出:\n{p}")
            except Exception as e:
                messagebox.showerror("失败", str(e))
    # ---------- 确认 ----------
    def ok(self):
        cfg = self.app.cfg
        cfg["theme"] = self.var_theme.get()
        cfg["auto_dpi"] = self.var_auto_dpi.get()
        if not self.var_auto_dpi.get():
            s = self.cmb_screen.get()
            if s != "自动":
                try: cfg["screen_scale"] = int(s)
                except Exception: pass
        cfg["ui_scale"] = float(self.var_ui_scale.get())
        save_config(cfg)
        # 快捷键
        save_shortcuts(self._sc_shortcuts)
        self.app.shortcuts = self._sc_shortcuts
        self.app.bind_all_shortcuts()
        self.result = True
        self.destroy()

# ===================== JSON 导出对话框 =====================
class JsonExportDialog(tk.Toplevel):
    """JSON 导出: 提供目录转换规则 (如 res://art/set/%.png)。"""
    def __init__(self, parent):
        super().__init__(parent); self.title("导出 JSON"); self.geometry("580x300")
        self.transient(parent); self.grab_set(); self.result = None
        self._theme_name = getattr(parent, "_theme_name", "light")
        AppStyles.apply(self, self._theme_name)
        f = ttk.Frame(self, padding=10); f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text="JSON 输出文件:").grid(row=0, column=0, sticky="w", pady=4)
        self.var_path = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_path, width=40).grid(row=0, column=1, padx=6)
        ttk.Button(f, text="浏览", command=self.browse).grid(row=0, column=2, padx=4)
        ttk.Label(f, text="目录转换规则:").grid(row=1, column=0, sticky="w", pady=4)
        self.var_rule = tk.StringVar(value="res://art/set/%.png")
        ttk.Entry(f, textvariable=self.var_rule, width=40).grid(row=1, column=1, padx=6)
        ttk.Label(f, text="% 会被替换为瓦片代码", foreground="gray").grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(f, text="留空则使用瓦片库中的原图片路径", foreground="gray").grid(row=3, column=1, sticky="w", padx=6)
        bf = ttk.Frame(f); bf.grid(row=4, column=0, columnspan=3, pady=12)
        ttk.Button(bf, text="确定", command=self.ok).pack(side=tk.LEFT, padx=8)
        ttk.Button(bf, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=8)
        self._center(parent)
    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    def browse(self):
        p = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json")])
        if p: self.var_path.set(p)
    def ok(self):
        path = self.var_path.get().strip()
        if not path: messagebox.showwarning("提示","请选择输出文件"); return
        self.result = (path, self.var_rule.get().strip())
        self.destroy()

# ===================== 瓦片库编辑器 =====================
class TileLibraryEditor(tk.Toplevel):
    def __init__(self, parent, tile_lib, tile_pixel_size, mdtile_path=None):
        super().__init__(parent); self.title("瓦片库编辑器 .mdtile"); self.geometry("920x620")
        self.parent_app = parent; self.tile_lib = tile_lib; self.tile_size = tile_pixel_size
        self.transient(parent); self.current_path = mdtile_path
        # 可缩放 + 最小尺寸约束
        self.resizable(True, True); self.minsize(780, 460)
        # 应用主题
        self._theme_name = getattr(parent, "_theme_name", "light")
        AppStyles.apply(self, self._theme_name)
        top = ttk.Frame(self); top.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(top, text="新增瓦片", command=self.add_tile).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="编辑选中", command=self.edit_tile).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="删除选中", command=self.del_tile).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="批量加入", command=self.batch_add).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="导入旧 .mdtile", command=self.import_mdtile).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="导出 .json", command=self.export_json).pack(side=tk.RIGHT, padx=2)
        ttk.Button(top, text="另存为 .mdt", command=self.save_as_mdt).pack(side=tk.RIGHT, padx=2)
        ttk.Button(top, text="保存 .mdt", command=self.save_mdt).pack(side=tk.RIGHT, padx=2)
        ttk.Button(top, text="保存 .mdtile", command=self.save_mdtile).pack(side=tk.RIGHT, padx=2)
        cols = ("code","name","imgpath","category","walkable","layer")
        tree_frame = ttk.Frame(self); tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings")
        for k, l, w in [("code","代码",80),("name","名称",100),("imgpath","图片",300),("category","分类",80),("walkable","可通行",60),("layer","图层",50)]:
            self.tree.heading(k, text=l); self.tree.column(k, width=w, anchor="w")
        tree_sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        tree_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=tree_sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", lambda e: self.edit_tile())
        self.refresh()
    def _cats(self):
        return sorted(set([t.category for t in self.tile_lib.values()] + ["未分类"]))
    def refresh(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for td in self.tile_lib.values():
            self.tree.insert("", tk.END, values=(td.code, td.name, td.img_path, td.category,
                "是" if td.walkable else "否", td.layer))
    def add_tile(self):
        dlg = TileEditDialog(self, set(self.tile_lib.keys()), categories=self._cats())
        self.parent_app.wait_window(dlg)
        if not dlg.result: return
        code, name, img, walk, layer, cat = dlg.result
        td = TileDefine(code, name, img, walkable=walk, layer=layer, category=cat)
        td.load_image((self.parent_app.effective_tile_size, self.parent_app.effective_tile_size))
        self.tile_lib[code] = td; self.refresh(); self.parent_app.refresh_tile_list(); self.parent_app.redraw_canvas()
    def edit_tile(self):
        sel = self.tree.selection()
        if not sel: messagebox.showinfo("提示","请先选中一条"); return
        code = self.tree.item(sel[0])["values"][0]; old = self.tile_lib[code]
        dlg = TileEditDialog(self, set(self.tile_lib.keys()), old_tile=old, categories=self._cats())
        self.parent_app.wait_window(dlg)
        if not dlg.result: return
        nc, nn, ni, nw, nl, ncat = dlg.result
        if nc != old.code: del self.tile_lib[old.code]
        nt = TileDefine(nc, nn, ni, walkable=nw, layer=nl, category=ncat)
        nt.load_image((self.parent_app.effective_tile_size, self.parent_app.effective_tile_size))
        self.tile_lib[nc] = nt; self.refresh(); self.parent_app.refresh_tile_list(); self.parent_app.redraw_canvas()
    def del_tile(self):
        sel = self.tree.selection()
        if not sel: return
        code = self.tree.item(sel[0])["values"][0]
        if code == "air": messagebox.showwarning("禁止","air 不能删除"); return
        if messagebox.askyesno("确认", f"删除 {code}？"):
            del self.tile_lib[code]; self.refresh(); self.parent_app.refresh_tile_list(); self.parent_app.redraw_canvas()
    def batch_add(self):
        dlg = BatchTileDialog(self, set(self.tile_lib.keys()))
        self.parent_app.wait_window(dlg)
        if not dlg.result: return
        sz = self.parent_app.effective_tile_size
        for code, name, img, walk, layer, cat in dlg.result:
            td = TileDefine(code, name, img, walkable=walk, layer=layer, category=cat)
            td.load_image((sz, sz)); self.tile_lib[code] = td
        self.refresh(); self.parent_app.refresh_tile_list(); self.parent_app.redraw_canvas()
        messagebox.showinfo("完成", f"已批量加入 {len(dlg.result)} 个瓦片")
    def save_mdtile(self):
        if self.current_path and self.current_path.endswith(".mdtile"):
            self._write_mdtile(self.current_path); messagebox.showinfo("成功","已保存")
        else:
            p = filedialog.asksaveasfilename(defaultextension=".mdtile", filetypes=[("MDTile","*.mdtile")])
            if p: self._write_mdtile(p); self.current_path = p; messagebox.showinfo("成功","已保存")
    def export_json(self):
        # 导出前校验
        warns = []
        for td in self.tile_lib.values():
            if td.code != "air" and not td.img_path:
                warns.append(f"瓦片 {td.code} 没有图片路径")
        if warns:
            if not messagebox.askyesno("警告", "\n".join(warns[:10]) + "\n\n仍要导出？"): return
        dlg = JsonExportDialog(self); self.parent_app.wait_window(dlg)
        if not dlg.result: return
        path, rule = dlg.result
        data = {"tile_size": [self.tile_size, self.tile_size], "tiles": {}}
        for td in self.tile_lib.values():
            # 应用目录转换规则
            if rule and "%" in rule:
                texture = rule.replace("%", td.code)
            else:
                texture = td.img_path
            data["tiles"][td.code] = {"name": td.name, "texture": texture,
                "walkable": td.walkable, "layer": td.layer}
        with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
        messagebox.showinfo("成功", f"已导出 JSON（不含分类字段）:\n{path}")
    def _write_mdtile(self, path):
        lines = []
        for td in self.tile_lib.values():
            lines.append(f"{td.code}#{td.name}#{td.img_path}#{td.category}")
        with open(path, "w", encoding="utf-8") as f: f.write("\n".join(lines))
    def save_as_mdtile(self):
        p = filedialog.asksaveasfilename(defaultextension=".mdtile", filetypes=[("MDTile","*.mdtile")])
        if not p: return
        self._write_mdtile(p); self.current_path = p
        messagebox.showinfo("成功", f"已另存为：\n{p}")
    # ===================== .mdt (zip) 格式 =====================
    def save_mdt(self):
        if self.current_path and self.current_path.endswith(".mdt"):
            self._write_mdt(self.current_path); messagebox.showinfo("成功","已保存")
        else:
            self.save_as_mdt()
    def save_as_mdt(self):
        p = filedialog.asksaveasfilename(defaultextension=".mdt", filetypes=[("MDT","*.mdt")])
        if not p: return
        self._write_mdt(p); self.current_path = p
        messagebox.showinfo("成功", f"已另存为：\n{p}")
    def _write_mdt(self, path):
        """将瓦片库写入 .mdt (zip)。结构:
            /tiles.txt  - 原始 mdtile 文本（图片路径替换为 res://）
            /res/       - 所有图片资源
        """
        # 收集所有图片并复制到临时目录
        tmpdir = tempfile.mkdtemp(prefix="mdt_")
        res_dir = os.path.join(tmpdir, "res")
        os.makedirs(res_dir, exist_ok=True)
        lines = []
        for td in self.tile_lib.values():
            # 把绝对路径图片打包进 res/，并在 tiles.txt 中改用 res:// 引用
            new_img_path = td.img_path
            if td.img_path and os.path.exists(td.img_path):
                ext = os.path.splitext(td.img_path)[1] or ".png"
                # 用瓦片 code 作为文件名，避免冲突
                fname = f"{td.code}{ext}"
                dst = os.path.join(res_dir, fname)
                try:
                    shutil.copy2(td.img_path, dst)
                    new_img_path = f"res://{fname}"
                except Exception:
                    pass
            elif td.img_path and td.img_path.startswith("res://"):
                # 已经是 res:// 引用，尝试从 image_bytes 取出（如果有）
                if td.image_bytes is not None:
                    ext = ".png"
                    fname = f"{td.code}{ext}"
                    dst = os.path.join(res_dir, fname)
                    try:
                        with open(dst, "wb") as outf: outf.write(td.image_bytes)
                    except Exception:
                        pass
                    new_img_path = f"res://{fname}"
            lines.append(f"{td.code}#{td.name}#{new_img_path}#{td.category}")
        # 写入 tiles.txt
        txt_path = os.path.join(tmpdir, "tiles.txt")
        with open(txt_path, "w", encoding="utf-8") as f: f.write("\n".join(lines))
        # 打包成 zip
        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(txt_path, "tiles.txt")
                for root, _, files in os.walk(res_dir):
                    for fn in files:
                        full = os.path.join(root, fn)
                        arc = os.path.relpath(full, tmpdir).replace("\\", "/")
                        zf.write(full, arc)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    def import_mdtile(self):
        """从旧 .mdtile 导入到当前编辑（不入 res，仅加入瓦片条目）。"""
        p = filedialog.askopenfilename(filetypes=[("MDTile","*.mdtile")], title="导入旧 .mdtile")
        if not p: return
        try:
            with open(p, "r", encoding="utf-8") as f:
                lines = f.readlines()
            added = 0
            for line in lines:
                line = line.strip()
                if not line: continue
                parts = line.split("#", 3)
                if len(parts) < 3: continue
                code, name, img = parts[0], parts[1], parts[2]
                cat = parts[3] if len(parts) > 3 else "未分类"
                if code in self.tile_lib:
                    continue  # 跳过已存在
                td = TileDefine(code, name, img, walkable=False, layer="0", category=cat)
                sz = self.parent_app.effective_tile_size
                td.load_image((sz, sz))
                self.tile_lib[code] = td
                added += 1
            self.refresh(); self.parent_app.refresh_tile_list(); self.parent_app.redraw_canvas()
            messagebox.showinfo("成功", f"已导入 {added} 个瓦片（已跳过同名）")
        except Exception as e:
            messagebox.showerror("失败", str(e))


# ===================== 主界面 =====================
class MainMenu(tk.Tk):
    def __init__(self):
        super().__init__(); set_app_id()
        self.title("MemoDesign"); self.geometry("1800x1200")
        set_window_icon(self)
        # 主菜单允许缩放，但有最小尺寸约束，防止按钮被吞
        self.resizable(True, True); self.minsize(640, 400)
        self.cfg = load_config()
        # 应用主题与字体（在创建子 widget 前调用，确保样式生效）
        self._theme_name = self.cfg.get("theme", "light")
        AppFonts._ui_scale = float(self.cfg.get("ui_scale", 1.0))
        AppStyles.apply(self, self._theme_name)
        # 自动加载上次mdtile
        self.tile_library = {}
        last = self.cfg.get("last_mdtile", "")
        if last and os.path.exists(last):
            self._load_mdtile_silent(last)
        # 快捷键
        self.shortcuts = load_shortcuts()
        self.bind_all_shortcuts()
        # 属性库 (主菜单也需要，用于首选项)
        self.attr_lib = AttributeLibrary()

        # 主分割容器：左右对半分
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # -------- 左侧面板：标题+按钮+瓦片库状态【全部左对齐】 --------
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=1)

        # anchor="nw" = 靠左上角，不再整体居中；去掉expand=True
        left_inner = ttk.Frame(left_frame)
        left_inner.pack(anchor="nw", pady=10)

        tk.Label(left_inner, text="MemoDesign", font=AppFonts.get("title", self, bold=True), fg="#13245e").pack(anchor="w", pady=(0,6))
        tk.Label(left_inner, text="瓦片地图编辑器", font=AppFonts.get("subheading", self), fg="#13245e").pack(anchor="w", pady=(0,25))

        ttk.Button(left_inner, text="  打开地图  ", style="Big.TButton", command=self.open_map).pack(anchor="w", pady=6)
        ttk.Button(left_inner, text="  新建地图  ", style="Big.TButton", command=self.new_map).pack(anchor="w", pady=6)
        ttk.Button(left_inner, text="  加载瓦片库  ", style="Big.TButton", command=self.load_tiles).pack(anchor="w", pady=6)
        ttk.Button(left_inner, text="  首选项  ", style="Big.TButton", command=self.open_preferences).pack(anchor="w", pady=6)
        tk.Label(left_inner, text="MemoDesign 1.3 开源至 GitHub", font=AppFonts.get("small", self), fg="#595959").pack(anchor="w", pady=(0,4))

        self.lbl_tile = tk.Label(left_inner, text="", font=AppFonts.get("small", self), fg="#13245e")
        self.lbl_tile.pack(anchor="w", pady=(18,0))
        self._update_tile_label()

        # -------- 右侧面板：历史记录 --------
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=1)

        right_inner = ttk.Frame(right_frame)
        right_inner.pack(fill=tk.BOTH, expand=True)

        tk.Label(right_inner, text="最近打开", font=AppFonts.get("body", self, bold=True), fg="#13245e").pack(anchor="w", pady=(0,4))
        hist_frame = ttk.Frame(right_inner); hist_frame.pack(fill=tk.BOTH, expand=True)
        self.lb_hist = tk.Listbox(hist_frame, height=10, fg="#13245e",
            highlightthickness=0, activestyle="none", font=AppFonts.get("small", self))
        hist_sb = ttk.Scrollbar(hist_frame, orient="vertical", command=self.lb_hist.yview)
        hist_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.lb_hist.configure(yscrollcommand=hist_sb.set)
        self.lb_hist.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Button(right_inner, text="清除历史记录", command=self.clear_history).pack(anchor="e", pady=6)
        self.lb_hist.bind("<Double-1>", self._hist_open)
        self._refresh_history()


    def _update_tile_label(self):
        if self.tile_library:
            self.lbl_tile.config(text=f"当前瓦片库: {self.cfg.get('last_mdtile','')}  ({len(self.tile_library)} 个瓦片)")
        else:
            self.lbl_tile.config(text="未加载瓦片库")
    def _refresh_history(self):
        self.lb_hist.delete(0, tk.END)
        for p in self.cfg.get("history", [])[:10]:
            self.lb_hist.insert(tk.END, p)
    def clear_history(self):
        self.cfg["history"] = []
        save_config(self.cfg)
        self._refresh_history()
    def open_preferences(self):
        """打开首选项 (主菜单入口)。"""
        old_theme = self.cfg.get("theme", "light")
        old_ui_scale = AppFonts._ui_scale
        dlg = PreferencesDialog(self, self); self.wait_window(dlg)
        self.cfg = load_config()
        self.shortcuts = load_shortcuts()
        new_theme = self.cfg.get("theme", "light")
        if new_theme != old_theme or AppFonts._ui_scale != old_ui_scale:
            self._theme_name = new_theme
            AppFonts._ui_scale = float(self.cfg.get("ui_scale", 1.0))
            AppStyles.apply(self, self._theme_name)
        self.bind_all_shortcuts()
    def bind_all_shortcuts(self):
        """绑定主菜单级快捷键。"""
        self.unbind_all("<Control-comma>")
        sc = self.shortcuts
        D = DEFAULT_SHORTCUTS
        self.bind(sc.get("preferences", D["preferences"]), lambda e: self.open_preferences())
    def _on_attr_lib_changed(self):
        pass

    def _load_mdtile_silent(self, path):
        try:
            if path.lower().endswith(".mdt"):
                return self._load_mdt_silent(path)
            lib = {}
            with open(path, "r", encoding="utf-8") as f:
                for line in f.readlines():
                    line = line.strip()
                    if not line: continue
                    parts = line.split("#", 3)
                    if len(parts) < 3: continue
                    code, name, img = parts[0], parts[1], parts[2]
                    cat = parts[3] if len(parts) > 3 else "未分类"
                    # 修复：补齐walkable、layer位置参数，mdtile磁盘文件不存这两个，给默认值
                    lib[code] = TileDefine(code, name, img, walkable=False, layer="0", category=cat)
            # 强制修正air瓦片固定属性
            if "air" in lib:
                lib["air"].walkable = True
                lib["air"].layer = "-5"
                lib["air"].category = "基础"
            else:
                lib["air"] = TileDefine("air","空气","",walkable=True,layer="-5",category="基础")
            self.tile_library = lib
        except Exception:
            self.tile_library = {}

    def _load_mdt_silent(self, path):
        """从 .mdt (zip) 加载瓦片库。zip 内 tiles.txt + res/ 文件夹。"""
        lib = {}
        tmpdir = tempfile.mkdtemp(prefix="mdt_extract_")
        try:
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(tmpdir)
        except Exception:
            self.tile_library = {}; return
        # 读 tiles.txt
        txt_path = os.path.join(tmpdir, "tiles.txt")
        if not os.path.exists(txt_path):
            self.tile_library = {}; return
        res_dir = os.path.join(tmpdir, "res")
        with open(txt_path, "r", encoding="utf-8") as f:
            for line in f.readlines():
                line = line.strip()
                if not line: continue
                parts = line.split("#", 3)
                if len(parts) < 3: continue
                code, name, img = parts[0], parts[1], parts[2]
                cat = parts[3] if len(parts) > 3 else "未分类"
                image_bytes = None
                img_path_disp = img
                if img.startswith("res://"):
                    fname = img[len("res://"):]
                    full = os.path.join(res_dir, fname)
                    if os.path.exists(full):
                        try:
                            with open(full, "rb") as bf: image_bytes = bf.read()
                            img_path_disp = full  # 加载图片时使用解压后的本地路径
                        except Exception:
                            pass
                td = TileDefine(code, name, img_path_disp, walkable=False, layer="0",
                                category=cat, image_bytes=image_bytes)
                lib[code] = td
        # 强制修正 air
        if "air" in lib:
            lib["air"].walkable = True; lib["air"].layer = "-5"; lib["air"].category = "基础"
        else:
            lib["air"] = TileDefine("air","空气","",walkable=True,layer="-5",category="基础")
        self.tile_library = lib

    def load_tiles(self):
        p = filedialog.askopenfilename(filetypes=[("MDT/MDTile","*.mdt;*.mdtile")])
        if not p: return
        self._load_mdtile_silent(p)
        self.cfg["last_mdtile"] = p; save_config(self.cfg); self._update_tile_label()
        messagebox.showinfo("成功", f"已加载 {len(self.tile_library)} 个瓦片")
    def open_map(self):
        p = filedialog.askopenfilename(filetypes=[("MDMap","*.mdmap")])
        if p: self._launch_editor(map_path=p)
    def new_map(self):
        self._launch_editor(new=True)
    def _hist_open(self, e):
        sel = self.lb_hist.curselection()
        if not sel: return
        p = self.lb_hist.get(sel[0])
        if os.path.exists(p): self._launch_editor(map_path=p)
        else: messagebox.showerror("错误", "文件不存在")
    def _launch_editor(self, map_path=None, new=False):
        self.withdraw()
        app = MemoDesignApp(master=self, map_path=map_path, new_map=new,
                            tile_library=dict(self.tile_library),
                            last_mdtile=self.cfg.get("last_mdtile", ""))
        self.wait_window(app)
        # 编辑器关闭后刷新
        self.cfg = load_config()
        self._refresh_history()
        self._update_tile_label()
        self.deiconify()

# ===================== 主编辑器 =====================
class MemoDesignApp(tk.Toplevel):
    ATTR_TYPES = ["startpoint", "endpoint", "key", "portal"]
    ATTR_LABELS = {"startpoint":"起始点","endpoint":"结束点","key":"钥匙","portal":"跳转格"}
    def __init__(self, master=None, map_path=None, new_map=False, tile_library=None, last_mdtile=""):
        if master:
            super().__init__(master)
        else:
            super().__init__()
        set_app_id()
        self._icon_cache = {}
        self.title("MemoDesign - 编辑器"); self.geometry("2400x1460")
        set_window_icon(self)
        # 编辑器允许缩放，最小尺寸约束防止 UI 被吞
        self.resizable(True, True); self.minsize(960, 540)
        self._master = master
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # 数据
        self.map_data = MapData()
        self.tile_library = tile_library if tile_library else {}
        if "air" not in self.tile_library:
            self.tile_library["air"] = TileDefine("air","空气","",walkable=True,layer="-5",category="基础")
        self.selected_tile_code = "air"; self.tile_size = 48; self.zoom_scale = 1.0
        self.current_map_path = None; self.last_mdtile = last_mdtile
        self.undo_mgr = UndoManager(); self.shortcuts = load_shortcuts()
        # 应用主题与字体
        self.cfg = load_config()
        self._theme_name = self.cfg.get("theme", "light")
        AppStyles.apply(self, self._theme_name)
        # 工具状态
        self.draw_mode = "brush"; self.attr_subtype = "startpoint"
        self.rect_start = None; self._dragging = False; self._last_drag_pos = None
        self._pan_active = False; self._pan_sx = 0; self._pan_sy = 0
        # 复制粘贴
        self.clipboard = None; self._copy_rect = None; self._paste_mode = False; self._paste_hover = None
        # 图层与显示
        self.layer_filter = tk.StringVar(value="全部")
        self.show_start = tk.BooleanVar(value=True); self.show_end = tk.BooleanVar(value=True)
        self.show_key = tk.BooleanVar(value=True); self.show_portal = tk.BooleanVar(value=True)
        # 属性库 + 当前选中的属性 id
        self.attr_lib = AttributeLibrary()
        self.attr_subtype_id = BUILTIN_ATTR_IDS["start"]  # 默认起始点 ($)
        # 工具按钮引用 (用于高亮)
        self._tool_buttons = {}
        # 悬浮预览
        self._preview_win = None; self._preview_item = None
        self.create_menu(); self.create_widgets(); self.bind_all_shortcuts()
        self._update_tool_highlight()  # 初始化默认画笔高亮
        self.reload_tile_images(); self.refresh_tile_list()
        # 加载地图
        if new_map:
            self.new_map(silent=True)
        elif map_path:
            self._load_map_file(map_path)
        else:
            self.map_data.tiles = ["air"] * 100; self.redraw_canvas()
        self._update_status()
    def _on_close(self):
        self.destroy()
    # ---------- 快捷键 ----------
    def bind_all_shortcuts(self):
        sc = self.shortcuts; D = DEFAULT_SHORTCUTS
        self.bind(sc.get("save",D["save"]), lambda e: self.save_mdmap())
        self.bind(sc.get("save_as",D["save_as"]), lambda e: self.save_as_mdmap())
        self.bind(sc.get("new_map",D["new_map"]), lambda e: self.new_map())
        self.bind(sc.get("open_mdmap",D["open_mdmap"]), lambda e: self.open_mdmap())
        self.bind(sc.get("undo",D["undo"]), lambda e: self.do_undo())
        self.bind(sc.get("redo",D["redo"]), lambda e: self.do_redo())
        ra = sc.get("redo_alt",D["redo_alt"])
        if ra != sc.get("redo",""): self.bind(ra, lambda e: self.do_redo())
        self.bind(sc.get("tile_editor",D["tile_editor"]), lambda e: self.open_tile_editor())
        self.bind(sc.get("tool_brush",D["tool_brush"]), lambda e: self.set_mode("brush"))
        self.bind(sc.get("tool_eraser",D["tool_eraser"]), lambda e: self.set_mode("eraser"))
        self.bind(sc.get("tool_rect",D["tool_rect"]), lambda e: self.set_mode("rect"))
        self.bind(sc.get("tool_fill",D["tool_fill"]), lambda e: self.set_mode("fill"))
        self.bind(sc.get("tool_copy",D["tool_copy"]), lambda e: self.set_mode("copy"))
        self.bind(sc.get("attr_start",D["attr_start"]), lambda e: self.set_attr_subtype("startpoint"))
        self.bind(sc.get("attr_end",D["attr_end"]), lambda e: self.set_attr_subtype("endpoint"))
        self.bind(sc.get("attr_key",D["attr_key"]), lambda e: self.set_attr_subtype("key"))
        self.bind(sc.get("attr_portal",D["attr_portal"]), lambda e: self.set_attr_subtype("portal"))
        self.bind(sc.get("tool_pan",D["tool_pan"]), lambda e: self.set_mode("pan"))
        self.bind(sc.get("preferences",D["preferences"]), lambda e: self.open_preferences())
    def _accel(self, key):
        b = self.shortcuts.get(key, DEFAULT_SHORTCUTS.get(key,"")).strip("<>")
        parts = []
        for p in b.split("-"):
            pl = p.lower()
            if pl == "control": parts.append("Ctrl")
            elif pl == "shift": parts.append("Shift")
            elif pl == "alt": parts.append("Alt")
            else: parts.append(p.upper())
        return "+".join(parts)
    # ---------- 菜单 ----------
    def create_menu(self):
        mb = tk.Menu(self)
        mf = tk.Menu(mb, tearoff=0)
        mf.add_command(label="新建地图", command=self.new_map, accelerator=self._accel("new_map"))
        mf.add_command(label="打开地图", command=self.open_mdmap, accelerator=self._accel("open_mdmap"))
        mf.add_separator()
        mf.add_command(label="保存", command=self.save_mdmap, accelerator=self._accel("save"))
        mf.add_command(label="另存为", command=self.save_as_mdmap, accelerator=self._accel("save_as"))
        mf.add_command(label="地图信息...", command=self.edit_map_info)
        mf.add_separator()
        mf.add_command(label="调整地图大小", command=self.resize_map)
        mf.add_command(label="加载瓦片库(.mdt/.mdtile)", command=self.open_mdtile)
        mf.add_command(label="瓦片库编辑器", command=self.open_tile_editor, accelerator=self._accel("tile_editor"))
        mf.add_separator()
        mf.add_command(label="首选项...", command=self.open_preferences, accelerator=self._accel("preferences"))
        mf.add_separator()
        mf.add_command(label="返回主界面", command=self._on_close)
        mb.add_cascade(label="文件", menu=mf)
        me = tk.Menu(mb, tearoff=0)
        me.add_command(label="撤销", command=self.do_undo, accelerator=self._accel("undo"))
        me.add_command(label="重做", command=self.do_redo, accelerator=self._accel("redo"))
        mb.add_cascade(label="编辑", menu=me)
        self.config(menu=mb)
    def open_preferences(self):
        """打开统一首选项窗口（显示/快捷键/属性列表）。"""
        old_theme = self.cfg.get("theme", "light")
        old_ui_scale = AppFonts._ui_scale
        dlg = PreferencesDialog(self, self); self.wait_window(dlg)
        # 重新读取配置
        self.cfg = load_config()
        self.shortcuts = load_shortcuts()
        # 应用主题（如果变了）
        new_theme = self.cfg.get("theme", "light")
        if new_theme != old_theme or AppFonts._ui_scale != old_ui_scale:
            self._theme_name = new_theme
            AppFonts._ui_scale = float(self.cfg.get("ui_scale", 1.0))
            AppStyles.apply(self, self._theme_name)
            self._apply_theme_to_children()
        self.bind_all_shortcuts()
    def _apply_theme_to_children(self):
        """主题变化后重新应用样式到现有子组件（部分刷新）。"""
        try:
            for child in self.winfo_children():
                try: AppStyles.apply(child, self._theme_name)
                except Exception: pass
        except Exception:
            pass
    # ---------- UI ----------
    def create_widgets(self):
        # 工具栏
        tb = ttk.Frame(self); tb.pack(fill=tk.X, padx=4, pady=3)

        def icon_btn(parent, name, fallback_text, cmd, key=None):
            ic_size = DpiHelper.scale_int(self, 16)
            ic = load_icon(name, ic_size)
            btn_sz = DpiHelper.scale_int(self, 26)
            btn = tk.Button(
                parent,
                image=self._icon_cache.setdefault((name, ic_size), ic) if ic else "",
                text=fallback_text if not ic else "",
                compound="top" if ic else tk.CENTER,
                width=btn_sz, height=btn_sz, command=cmd, relief=tk.RAISED, bd=1
            ) if ic else ttk.Button(parent, text=fallback_text, command=cmd, width=3)
            if key:
                self._tool_buttons[key] = btn
            return btn

        icon_btn(tb, "new", "新", self.new_map).pack(side=tk.LEFT, padx=2)
        icon_btn(tb, "open", "开", self.open_mdmap).pack(side=tk.LEFT, padx=2)
        icon_btn(tb, "save", "存", self.save_mdmap).pack(side=tk.LEFT, padx=2)
        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)

        icon_btn(tb, "undo", "↶", self.do_undo).pack(side=tk.LEFT, padx=2)
        icon_btn(tb, "redo", "↷", self.do_redo).pack(side=tk.LEFT, padx=2)
        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)

        self.btn_brush = icon_btn(tb, "brush", "笔", lambda: self.set_mode("brush"), key="brush")
        self.btn_brush.pack(side=tk.LEFT, padx=2)
        self.btn_eraser = icon_btn(tb, "eraser", "擦", lambda: self.set_mode("eraser"), key="eraser")
        self.btn_eraser.pack(side=tk.LEFT, padx=2)
        self.btn_rect = icon_btn(tb, "rect", "矩", lambda: self.set_mode("rect"), key="rect")
        self.btn_rect.pack(side=tk.LEFT, padx=2)
        self.btn_fill = icon_btn(tb, "fill", "填", lambda: self.set_mode("fill"), key="fill")
        self.btn_fill.pack(side=tk.LEFT, padx=2)
        self.btn_copy = icon_btn(tb, "copy", "复", lambda: self.set_mode("copy"), key="copy")
        self.btn_copy.pack(side=tk.LEFT, padx=2)

        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
        self.btn_attr = icon_btn(tb, "attr", "属", lambda: self.set_mode("attr"), key="attr")
        self.btn_attr.pack(side=tk.LEFT, padx=2)

        self.var_attr = tk.StringVar(value=self.attr_lib.get_names()[0] if self.attr_lib.get_names() else "")
        self.cmb_attr = ttk.Combobox(tb, textvariable=self.var_attr, state="readonly", width=10)
        self._refresh_attr_combobox()
        self.cmb_attr.pack(side=tk.LEFT, padx=2)
        self.cmb_attr.bind("<<ComboboxSelected>>", self._on_attr_change)

        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
        self.btn_pan = icon_btn(tb, "pan", "拖", lambda: self.set_mode("pan"), key="pan")
        self.btn_pan.pack(side=tk.LEFT, padx=2)
        icon_btn(tb, "resize", "尺", self.resize_map).pack(side=tk.LEFT, padx=2)

        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
        # 图层筛选
        ttk.Label(tb, text="图层:").pack(side=tk.LEFT, padx=(8,2))
        self.cmb_layer = ttk.Combobox(tb, textvariable=self.layer_filter, state="readonly", width=8)
        self.cmb_layer["values"] = ["全部"]; self.cmb_layer.pack(side=tk.LEFT, padx=2)
        self.cmb_layer.bind("<<ComboboxSelected>>", lambda e: self.redraw_canvas())
        # 显示开关
        ttk.Checkbutton(tb, text="起点", variable=self.show_start, command=self.redraw_canvas).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(tb, text="终点", variable=self.show_end, command=self.redraw_canvas).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(tb, text="钥匙", variable=self.show_key, command=self.redraw_canvas).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(tb, text="跳转", variable=self.show_portal, command=self.redraw_canvas).pack(side=tk.LEFT, padx=4)

        self.mode_label = ttk.Label(tb, text="模式: 画笔", style="Muted.TLabel")
        self.mode_label.pack(side=tk.RIGHT, padx=10)

        # 主区域
        pw = ttk.PanedWindow(self, orient=tk.HORIZONTAL); pw.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        left = ttk.Frame(pw); pw.add(left, weight=3)

        # 缩放条
        zf = ttk.Frame(left); zf.pack(fill=tk.X, padx=4, pady=2)
        ttk.Label(zf, text="缩放:").pack(side=tk.LEFT)
        self.zoom_var = tk.DoubleVar(value=1.0)
        ttk.Scale(zf, from_=0.25, to=4.0, variable=self.zoom_var, orient=tk.HORIZONTAL,
                  length=240, command=self.on_zoom).pack(side=tk.LEFT, padx=5)
        self.zoom_label = ttk.Label(zf, text="100%", width=6); self.zoom_label.pack(side=tk.LEFT)
        for t, v in [("50%",0.5),("100%",1.0),("200%",2.0)]:
            ttk.Button(zf, text=t, command=lambda v=v: self.set_zoom(v)).pack(side=tk.LEFT, padx=2)

        # 画布
        self.canvas = tk.Canvas(left, bg=Theme.palette(self._theme_name)["canvas_bg"], highlightthickness=0)
        self.canvas._theme_bg_semantic = "canvas"
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_lmb_down)
        self.canvas.bind("<B1-Motion>", self.on_lmb_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_lmb_up)
        self.canvas.bind("<Button-3>", self.on_rmb_down)
        self.canvas.bind("<B3-Motion>", self.on_rmb_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_rmb_up)
        self.canvas.bind("<Motion>", self.on_canvas_motion)
        self.canvas.bind("<MouseWheel>", self.on_wheel)
        self.canvas.bind("<Button-4>", self.on_wheel_linux)
        self.canvas.bind("<Button-5>", self.on_wheel_linux)

        # 右侧瓦片库
        right = ttk.Frame(pw, width=240); pw.add(right, weight=1)
        ttk.Label(right, text="瓦片素材库", font=AppFonts.get("subheading", self, bold=True)).pack(pady=4)
        tframe = ttk.Frame(right); tframe.pack(fill=tk.BOTH, expand=True, padx=4)
        self.tile_tree = ttk.Treeview(tframe, columns=("info",), show="tree headings", height=20)
        self.tile_tree.heading("#0", text="分类/瓦片"); self.tile_tree.heading("info", text="属性")
        self.tile_tree.column("#0", width=130); self.tile_tree.column("info", width=90)
        sb = ttk.Scrollbar(tframe, orient="vertical", command=self.tile_tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y); self.tile_tree.configure(yscrollcommand=sb.set)
        self.tile_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tile_tree.bind("<<TreeviewSelect>>", self.on_tile_select)
        self.tile_tree.bind("<Motion>", self.on_tile_hover)
        self.tile_tree.bind("<Leave>", lambda e: self._hide_preview())

        # 状态栏
        self.status = ttk.Label(self, text="", anchor="w", relief=tk.SUNKEN, padding=(6, 2))
        self.status.pack(fill=tk.X, side=tk.BOTTOM)

    # ---------- 瓦片库分组 ----------
    def refresh_tile_list(self):
        for i in self.tile_tree.get_children(): self.tile_tree.delete(i)
        cats = {}
        for code, td in self.tile_library.items():
            cats.setdefault(td.category, []).append(td)
        for cat in sorted(cats.keys()):
            cid = self.tile_tree.insert("", tk.END, text=cat, values=("",), open=True)
            for td in sorted(cats[cat], key=lambda t: t.code):
                walk = "✓" if td.walkable else "✗"
                self.tile_tree.insert(cid, tk.END, iid=f"tile:{td.code}",
                    text=f"  {td.code}", values=(f"{td.name} L{td.layer} {walk}"))
        # 更新图层下拉
        layers = sorted(set([str(td.layer) for td in self.tile_library.values()]))
        self.cmb_layer["values"] = ["全部"] + layers
    def on_tile_select(self, e):
        sel = self.tile_tree.selection()
        if not sel: return
        iid = sel[0]
        if iid.startswith("tile:"):
            self.selected_tile_code = iid[5:]
    def on_tile_hover(self, event):
        iid = self.tile_tree.identify_row(event.y)
        if not iid or not iid.startswith("tile:"):
            self._hide_preview(); return
        if self._preview_item == iid and self._preview_win: return
        self._hide_preview()
        code = iid[5:]; td = self.tile_library.get(code)
        if not td: return
        self._preview_item = iid
        win = tk.Toplevel(self); win.overrideredirect(True)
        pal = Theme.palette(self._theme_name)
        win.configure(bg=pal["preview_bg"])
        win._theme_bg_semantic = "preview"
        x = self.winfo_rootx() + self.winfo_width() - 260
        y = event.y_root + 10
        win.geometry(f"+{x}+{y}")
        if td.photo:
            lbl_img = tk.Label(win, image=td.photo, bg=pal["preview_bg"]); lbl_img.pack(padx=8, pady=8)
        info = f"代码: {td.code}\n名称: {td.name}\n分类: {td.category}\n图层: {td.layer}\n可通行: {'是' if td.walkable else '否'}\n图片: {os.path.basename(td.img_path) if td.img_path else '无'}"
        tk.Label(win, text=info, fg=pal["preview_fg"], bg=pal["preview_bg"], justify="left", font=AppFonts.get("small", self)).pack(padx=8, pady=(0,8))
        self._preview_win = win
    def _hide_preview(self):
        if self._preview_win:
            try: self._preview_win.destroy()
            except Exception: pass
        self._preview_win = None; self._preview_item = None
    # ---------- 缩放 ----------
    @property
    def effective_tile_size(self): return max(8, int(self.tile_size * self.zoom_scale))
    def set_zoom(self, v):
        self.zoom_scale = max(0.25, min(4.0, v)); self.zoom_var.set(self.zoom_scale)
        self.zoom_label.config(text=f"{int(self.zoom_scale*100)}%")
        self.reload_tile_images(); self.redraw_canvas()
    def on_zoom(self, v):
        self.zoom_scale = float(v); self.zoom_label.config(text=f"{int(self.zoom_scale*100)}%")
        self.reload_tile_images(); self.redraw_canvas()
    def on_wheel(self, e):
        self.set_zoom(self.zoom_scale + 0.1 * (e.delta // 120))
    def on_wheel_linux(self, e):
        self.set_zoom(self.zoom_scale + (0.1 if e.num == 4 else -0.1))
    def reload_tile_images(self):
        sz = self.effective_tile_size
        for td in self.tile_library.values():
            if td.img_path: td.load_image((sz, sz))
    # ---------- 模式 ----------
    def set_mode(self, mode):
        self.draw_mode = mode; self._paste_mode = False; self._copy_rect = None
        attr_label = self.var_attr.get() if hasattr(self, "var_attr") else ""
        names = {"brush":"画笔","eraser":"橡皮","rect":"矩形","fill":"填充","copy":"复制选择","attr":f"属性({attr_label})","pan":"拖拽"}
        self.mode_label.config(text=f"模式: {names.get(mode, mode)}")
        self._dragging = False; self._pan_active = False; self.rect_start = None
        self._update_tool_highlight()
        self.redraw_canvas()
    def _update_tool_highlight(self):
        """高亮当前选中的工具按钮。"""
        pal = Theme.palette(getattr(self, "_theme_name", "light"))
        active_bg = pal["accent"]; active_fg = pal["accent_fg"]
        idle_bg = pal["bg_alt"]; idle_fg = pal["fg"]
        for key, btn in self._tool_buttons.items():
            try:
                is_active = (key == self.draw_mode)
                if isinstance(btn, tk.Button):
                    btn.config(bg=active_bg if is_active else idle_bg,
                               fg=active_fg if is_active else idle_fg,
                               relief=tk.SUNKEN if is_active else tk.RAISED)
                else:  # ttk.Button 降级
                    style_name = f"ToolHL.TButton" if is_active else "TButton"
                    btn.configure(style=style_name)
            except Exception:
                pass
    def set_attr_subtype(self, sub):
        """通过内置子类型名 (startpoint/endpoint/key/portal) 设置属性。"""
        self.attr_subtype = sub
        id_char = BUILTIN_ATTR_IDS.get(sub)
        if id_char:
            self.attr_subtype_id = id_char
            attr = self.attr_lib.get_by_id(id_char)
            if attr: self.var_attr.set(attr.name)
        self.set_mode("attr")
    def set_attr_by_id(self, id_char):
        """通过属性 id 设置当前属性。"""
        attr = self.attr_lib.get_by_id(id_char)
        if not attr: return
        self.attr_subtype_id = id_char
        # 同步 attr_subtype 用于兼容快捷键逻辑
        for k, v in BUILTIN_ATTR_IDS.items():
            if v == id_char: self.attr_subtype = k; break
        self.var_attr.set(attr.name)
        if self.draw_mode == "attr":
            self.mode_label.config(text=f"模式: 属性({attr.name})")
    def _refresh_attr_combobox(self):
        """从 attr_lib 重建属性下拉框。"""
        names = self.attr_lib.get_names()
        self.cmb_attr["values"] = names
        # 当前选中保留
        cur = self.var_attr.get()
        if cur not in names:
            if names: self.var_attr.set(names[0]); self.attr_subtype_id = self.attr_lib.get_by_name(names[0]).id_char
        # 同步 attr_subtype_id
        attr = self.attr_lib.get_by_name(cur)
        if attr: self.attr_subtype_id = attr.id_char
    def _on_attr_change(self, e=None):
        name = self.var_attr.get()
        attr = self.attr_lib.get_by_name(name)
        if attr:
            self.attr_subtype_id = attr.id_char
            # 同步 attr_subtype 用于兼容
            self.attr_subtype = None
            for k, v in BUILTIN_ATTR_IDS.items():
                if v == attr.id_char: self.attr_subtype = k; break
            if self.draw_mode == "attr":
                self.mode_label.config(text=f"模式: 属性({attr.name})")
    def _on_attr_lib_changed(self):
        """属性库变更后的回调（新增/编辑/导入时）。"""
        self._refresh_attr_combobox()
        self.map_data.sync_legacy_attrs(self.attr_lib)
        self.redraw_canvas()
    # ---------- 坐标 ----------
    def _grid(self, event):
        sz = self.effective_tile_size
        cx = self.canvas.canvasx(event.x); cy = self.canvas.canvasy(event.y)
        c = int(cx // sz); r = int(cy // sz)
        if 0 <= c < self.map_data.col_count and 0 <= r < self.map_data.row_count:
            return r, c
        return None
    def _tile_at(self, r, c):
        idx = r * self.map_data.col_count + c
        return self.map_data.tiles[idx] if idx < len(self.map_data.tiles) else "air"
    def _set_tile(self, r, c, code):
        idx = r * self.map_data.col_count + c
        while len(self.map_data.tiles) <= idx: self.map_data.tiles.append("air")
        self.map_data.tiles[idx] = code
    # ---------- 鼠标 ----------
    def on_lmb_down(self, event):
        # 粘贴模式优先：点击即放置
        if self._paste_mode:
            grid = self._grid(event)
            if grid: self._do_paste(grid[0], grid[1])
            return
        if self.draw_mode == "pan":
            self._pan_active = True; self._pan_sx = event.x; self._pan_sy = event.y; return
        grid = self._grid(event)
        if self.draw_mode == "copy":
            if grid: self._copy_rect = [grid[0], grid[1], grid[0], grid[1]]; self._dragging = True
            return
        if not grid: return
        r, c = grid
        if self.draw_mode in ("brush", "eraser"):
            self._dragging = True; self.undo_mgr.snapshot(self.map_data)
            self._set_tile(r, c, self.selected_tile_code if self.draw_mode == "brush" else "air")
            self._last_drag_pos = (r, c); self.redraw_canvas()
        elif self.draw_mode == "rect":
            self.rect_start = (r, c); self._dragging = True; self.redraw_canvas()
        elif self.draw_mode == "fill":
            self._flood_fill(r, c)
        elif self.draw_mode == "attr":
            self._apply_attr(r, c)
    def on_lmb_drag(self, event):
        if self._pan_active:
            dx = (self._pan_sx - event.x) // 3; dy = (self._pan_sy - event.y) // 3
            if dx or dy:
                self.canvas.xview_scroll(int(dx), tk.UNITS); self.canvas.yview_scroll(int(dy), tk.UNITS)
                self._pan_sx = event.x; self._pan_sy = event.y
            return
        if self.draw_mode == "copy" and self._dragging:
            grid = self._grid(event)
            if grid: self._copy_rect[2], self._copy_rect[3] = grid[0], grid[1]; self.redraw_canvas()
            return
        if self._paste_mode:
            self._paste_hover = self._grid(event); self.redraw_canvas(); return
        if not self._dragging: return
        grid = self._grid(event)
        if not grid: return
        r, c = grid
        if self.draw_mode in ("brush", "eraser") and (r, c) != self._last_drag_pos:
            self._set_tile(r, c, self.selected_tile_code if self.draw_mode == "brush" else "air")
            self._last_drag_pos = (r, c); self.redraw_canvas()
        elif self.draw_mode == "rect":
            self.redraw_canvas()
    def on_lmb_up(self, event):
        self._pan_active = False
        if self.draw_mode == "copy" and self._dragging and self._copy_rect:
            self._do_copy(); return
        if self.draw_mode == "rect" and self._dragging and self.rect_start:
            grid = self._grid(event); sr, sc = self.rect_start
            er, ec = (grid if grid else (sr, sc))
            self.undo_mgr.snapshot(self.map_data)
            for r in range(min(sr,er), max(sr,er)+1):
                for c in range(min(sc,ec), max(sc,ec)+1): self._set_tile(r, c, self.selected_tile_code)
            self.redraw_canvas()
        self._dragging = False; self.rect_start = None; self._last_drag_pos = None
    def on_canvas_motion(self, event):
        grid = self._grid(event)
        if self._paste_mode:
            self._paste_hover = grid; self.redraw_canvas()
        self._update_status(grid)
    # 右键：默认拖拽，attr模式下覆盖为编辑/删除标记
    def on_rmb_down(self, event):
        if self.draw_mode == "attr":
            grid = self._grid(event)
            if grid: self._attr_right_click(grid[0], grid[1], event)
            return
        # 默认右键 = 拖拽
        self._pan_active = True; self._pan_sx = event.x; self._pan_sy = event.y
    def on_rmb_drag(self, event):
        if self.draw_mode == "attr": return
        if self._pan_active:
            dx = (self._pan_sx - event.x) // 3; dy = (self._pan_sy - event.y) // 3
            if dx or dy:
                self.canvas.xview_scroll(int(dx), tk.UNITS); self.canvas.yview_scroll(int(dy), tk.UNITS)
                self._pan_sx = event.x; self._pan_sy = event.y
    def on_rmb_up(self, event):
        self._pan_active = False
    # ---------- 填充 ----------
    def _flood_fill(self, r, c):
        target = self._tile_at(r, c)
        if target == self.selected_tile_code: return
        self.undo_mgr.snapshot(self.map_data)
        stack = [(r, c)]; visited = set()
        while stack:
            cr, cc = stack.pop()
            if (cr, cc) in visited: continue
            if cr < 0 or cr >= self.map_data.row_count or cc < 0 or cc >= self.map_data.col_count: continue
            if self._tile_at(cr, cc) != target: continue
            visited.add((cr, cc)); self._set_tile(cr, cc, self.selected_tile_code)
            stack.extend([(cr+1,cc),(cr-1,cc),(cr,cc+1),(cr,cc-1)])
        self.redraw_canvas()
    # ---------- 复制粘贴 ----------
    def _do_copy(self):
        r0, c0, r1, c1 = self._copy_rect
        r0, r1 = min(r0, r1), max(r0, r1)
        c0, c1 = min(c0, c1), max(c0, c1)
        h, w = r1 - r0 + 1, c1 - c0 + 1
        tiles = [[self._tile_at(r0+i, c0+j) for j in range(w)] for i in range(h)]
        start = end = None; keys = set(); portals = {}
        for i in range(h):
            for j in range(w):
                gr, gc = r0+i, c0+j
                if self.map_data.start_pos == (gr, gc): start = (i, j)
                if self.map_data.end_pos == (gr, gc): end = (i, j)
                if (gr, gc) in self.map_data.key_marks: keys.add((i, j))
                if (gr, gc) in self.map_data.portals: portals[(i, j)] = dict(self.map_data.portals[(gr, gc)])
        self.clipboard = {"h":h,"w":w,"tiles":tiles,"start":start,"end":end,"keys":keys,"portals":portals}
        self._paste_mode = True; self._copy_rect = None; self._dragging = False
        self.mode_label.config(text=f"模式: 粘贴中(点击放置, 切换工具取消)"); self.redraw_canvas()
    def _do_paste(self, r, c):
        if not self.clipboard: return
        cb = self.clipboard; self.undo_mgr.snapshot(self.map_data)
        for i in range(cb["h"]):
            for j in range(cb["w"]):
                gr, gc = r+i, c+j
                if 0 <= gr < self.map_data.row_count and 0 <= gc < self.map_data.col_count:
                    self._set_tile(gr, gc, cb["tiles"][i][j])
        if cb["start"]:
            i, j = cb["start"]; gr, gc = r+i, c+j
            if 0 <= gr < self.map_data.row_count and 0 <= gc < self.map_data.col_count:
                self.map_data.start_pos = (gr, gc)
        if cb["end"]:
            i, j = cb["end"]; gr, gc = r+i, c+j
            if 0 <= gr < self.map_data.row_count and 0 <= gc < self.map_data.col_count:
                self.map_data.end_pos = (gr, gc)
        for (i, j) in cb["keys"]:
            gr, gc = r+i, c+j
            if 0 <= gr < self.map_data.row_count and 0 <= gc < self.map_data.col_count:
                self.map_data.key_marks.add((gr, gc))
        for (i, j), p in cb["portals"].items():
            gr, gc = r+i, c+j
            if 0 <= gr < self.map_data.row_count and 0 <= gc < self.map_data.col_count:
                self.map_data.portals[(gr, gc)] = dict(p)
        self.redraw_canvas()
    # ---------- 属性 ----------
    def _apply_attr(self, r, c):
        """属性工具左键: 按 ABCD 顺序补到第一个空槽；重复/已满则提示。"""
        attr = self.attr_lib.get_by_id(self.attr_subtype_id)
        if not attr:
            messagebox.showwarning("提示", "未选择有效属性"); return
        # 重复检测
        if self.map_data.has_attr(r, c, attr.id_char):
            messagebox.showinfo("提示", "此格已有该属性"); return
        if self.map_data.is_full(r, c):
            messagebox.showinfo("提示", "此格 4 个属性槽已满\n请右键打开瓦片属性编辑器修改"); return
        # 单例检测（整图唯一）
        if attr.singleton:
            for (pr, pc), slots in self.map_data.tile_attrs.items():
                for s in MapData.SLOT_ORDER:
                    if slots.get(s) == attr.id_char:
                        if not messagebox.askyesno("单例属性",
                                f"'{attr.name}' 是整图唯一属性，已在 ({pr},{pc}) 出现。\n是否从原位置移除并放到当前格？"):
                            return
                        self.undo_mgr.snapshot(self.map_data)
                        self.map_data.remove_attr(pr, pc, attr.id_char)
                        # 跳出后继续向下添加
                        break
                else:
                    continue
                break
        # portal 等带 options 的属性：弹出编辑对话框
        options = None
        if attr.options:
            # 收集当前选项默认值
            cur_opts = {opt["name"]: opt["default"] for opt in attr.options}
            # 若该格已有 portal 等同 id 属性（理论上不会，已被 has_attr 拦截）
            dlg = PortalEditDialog(self, {**cur_opts, "color": cur_opts.get("color", "ff7733")})
            self.wait_window(dlg)
            if dlg.result is None: return
            options = dict(dlg.result)
        self.undo_mgr.snapshot(self.map_data)
        self.map_data.add_attr(r, c, attr.id_char, options=options)
        # 同步 legacy 字段（start/end/key/portal）
        self.map_data.sync_legacy_attrs(self.attr_lib)
        self.redraw_canvas()
    def _attr_right_click(self, r, c, event):
        """attr 模式右键：弹出菜单（瓦片属性编辑器、首选项）。"""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="瓦片属性编辑器...", command=lambda: self._open_tile_attr_editor(r, c))
        menu.add_command(label="首选项...", command=self.open_preferences)
        menu.add_separator()
        # 显示该格已有属性信息
        slots = self.map_data.get_slots(r, c)
        any_attr = any(slots.get(s) for s in MapData.SLOT_ORDER)
        if any_attr:
            menu.add_command(label=f"当前: {self._format_tile_attrs(r, c)}", command=lambda: None, state="disabled")
        menu.tk_popup(event.x_root, event.y_root)
    def _format_tile_attrs(self, r, c):
        """格式化显示瓦片各槽的属性名。"""
        slots = self.map_data.get_slots(r, c)
        parts = []
        for s in MapData.SLOT_ORDER:
            aid = slots.get(s)
            if aid:
                attr = self.attr_lib.get_by_id(aid)
                name = attr.name if attr else aid
                parts.append(f"{s}={name}")
        return " ".join(parts)
    def _open_tile_attr_editor(self, r, c):
        """打开瓦片属性编辑器对话框。"""
        self.undo_mgr.snapshot(self.map_data)
        dlg = TileAttributeEditor(self, self.map_data, r, c, self.attr_lib)
        self.wait_window(dlg)
        if dlg.result is None:
            # 撤销此次 snapshot（无变化）
            self.undo_mgr.undo_stack.pop(); return
        new_slots, new_options = dlg.result
        # 应用结果
        for s in MapData.SLOT_ORDER:
            self.map_data.set_slot(r, c, s, new_slots.get(s),
                                   options=new_options.get(s) if new_slots.get(s) else None)
        # 清理空槽位
        slots = self.map_data.tile_attrs.get((r, c))
        if slots and not any(slots.get(s) for s in MapData.SLOT_ORDER):
            self.map_data.clear_attr_tile(r, c)
        self.map_data.sync_legacy_attrs(self.attr_lib)
        self.redraw_canvas()
    def _edit_portal(self, r, c):
        old = self.map_data.portals.get((r, c))
        dlg = PortalEditDialog(self, old); self.wait_window(dlg)
        if dlg.result:
            self.undo_mgr.snapshot(self.map_data)
            self.map_data.portals[(r, c)] = dlg.result; self.redraw_canvas()
    def _del_mark(self, kind, r, c):
        self.undo_mgr.snapshot(self.map_data)
        if kind == "start": self.map_data.start_pos = None
        elif kind == "end": self.map_data.end_pos = None
        elif kind == "key": self.map_data.key_marks.discard((r, c))
        elif kind == "portal": self.map_data.portals.pop((r, c), None)
        self.redraw_canvas()
    # ---------- 撤销重做 ----------
    def do_undo(self):
        if self.undo_mgr.pop_undo(self.map_data): self.redraw_canvas()
    def do_redo(self):
        if self.undo_mgr.pop_redo(self.map_data): self.redraw_canvas()
    # ---------- 绘制 ----------
    def redraw_canvas(self):
        self.canvas.delete("all")
        rows, cols = self.map_data.row_count, self.map_data.col_count
        sz = self.effective_tile_size
        layer_f = self.layer_filter.get()
        for y in range(rows):
            for x in range(cols):
                code = self._tile_at(y, x)
                px, py = x * sz, y * sz
                self.canvas.create_rectangle(px, py, px+sz, py+sz, outline="#444")
                td = self.tile_library.get(code)
                # 图层筛选
                if layer_f != "全部" and td and str(td.layer) != layer_f:
                    # 不渲染瓦片图，只显示灰色占位
                    self.canvas.create_rectangle(px+1, py+1, px+sz-1, py+sz-1, fill="#2a2a2a", outline="")
                else:
                    if td and td.photo:
                        self.canvas.create_image(px+sz//2, py+sz//2, image=td.photo)
                    else:
                        txt = td.name if td else code
                        fs = max(7, int(8 * self.zoom_scale))
                        self.canvas.create_text(px+sz//2, py+sz//2, text=txt, fill="#888", font=(AppFonts.family(), fs))
                # 属性标记 (ABCD 四角, 各占 1/4, 留出空间)
                self._draw_tile_attrs(y, x, px, py, sz)
        # 复制框选
        if self.draw_mode == "copy" and self._copy_rect:
            r0, c0, r1, c1 = self._copy_rect
            r0, r1 = min(r0,r1), max(r0,r1); c0, c1 = min(c0,c1), max(c0,c1)
            self.canvas.create_rectangle(c0*sz, r0*sz, (c1+1)*sz, (r1+1)*sz,
                outline="#ffcc00", width=2, dash=(4,4))
        # 粘贴预览
        if self._paste_mode and self._paste_hover and self.clipboard:
            r, c = self._paste_hover; cb = self.clipboard
            self.canvas.create_rectangle(c*sz, r*sz, (c+cb["w"])*sz, (r+cb["h"])*sz,
                outline="#00ccff", width=2, dash=(3,3))
        # 矩形预览
        if self.draw_mode == "rect" and self._dragging and self.rect_start:
            sr, sc = self.rect_start
            try:
                mx = self.canvas.canvasx(self.canvas.winfo_pointerx() - self.canvas.winfo_rootx())
                my = self.canvas.canvasy(self.canvas.winfo_pointery() - self.canvas.winfo_rooty())
                ec = max(0, min(int(mx//sz), cols-1)); er = max(0, min(int(my//sz), rows-1))
            except Exception: er, ec = sr, sc
            self.canvas.create_rectangle(min(sc,ec)*sz, min(sr,er)*sz, (max(sc,ec)+1)*sz, (max(sr,er)+1)*sz,
                outline="#4488ff", width=2, dash=(4,4), stipple="gray25", fill="#4488ff")
        self.canvas.configure(scrollregion=(0, 0, cols*sz, rows*sz))
    def _dot(self, cx, cy, d, color):
        key = (d, color)
        if not hasattr(self, "_dot_cache"): self._dot_cache = {}
        if key not in self._dot_cache:
            img = Image.new("RGBA", (d, d), (0,0,0,0))
            ImageDraw.Draw(img).ellipse((0,0,d,d), fill=color)
            self._dot_cache[key] = ImageTk.PhotoImage(img)
        self.canvas.create_image(cx, cy, image=self._dot_cache[key])
    def _draw_tile_attrs(self, r, c, px, py, sz):
        """绘制瓦片的 ABCD 四角属性图标 (1/4 大小, 居于一角)。"""
        slots = self.map_data.tile_attrs.get((r, c))
        if not slots: return
        # 每个图标占格子的 1/4 边长 (留出空隙)
        ic_size = max(6, sz // 4)
        # 内边距 (让图标居于角落但不贴边)
        pad = max(1, sz // 16)
        # 位置: A=左上 B=右上 C=左下 D=右下
        positions = {
            "A": (px + pad, py + pad),
            "B": (px + sz - pad - ic_size, py + pad),
            "C": (px + pad, py + sz - pad - ic_size),
            "D": (px + sz - pad - ic_size, py + sz - pad - ic_size),
        }
        # 显示开关: 仅对内置属性生效
        show_map = {
            BUILTIN_ATTR_IDS["start"]: self.show_start.get(),
            BUILTIN_ATTR_IDS["end"]: self.show_end.get(),
            BUILTIN_ATTR_IDS["key"]: self.show_key.get(),
            BUILTIN_ATTR_IDS["portal"]: self.show_portal.get(),
        }
        for s in MapData.SLOT_ORDER:
            aid = slots.get(s)
            if not aid: continue
            attr = self.attr_lib.get_by_id(aid)
            if not attr: continue
            # 内置属性受显示开关控制
            if aid in show_map and not show_map[aid]:
                continue
            try:
                ic = make_attr_icon(attr.color, attr.shape, ic_size)
                cx, cy = positions[s]
                # 居中锚定: 让图标中心位于角落中心
                ax = cx + ic_size // 2; ay = cy + ic_size // 2
                self.canvas.create_image(ax, ay, image=ic)
            except Exception:
                pass
    # ---------- 状态栏 ----------
    def _update_status(self, grid=None):
        md = self.map_data
        parts = [f"地图: {md.map_name}", f"尺寸: {md.row_count}×{md.col_count}",
                 f"瓦片: {len([t for t in md.tiles if t!='air'])}",
                 f"钥匙: {len(md.key_marks)}", f"跳转: {len(md.portals)}"]
        if grid:
            r, c = grid; code = self._tile_at(r, c)
            td = self.tile_library.get(code)
            info = f"光标: ({r},{c}) 瓦片={code}"
            if td: info += f" 名={td.name} 层={td.layer} 通行={'是' if td.walkable else '否'}"
            if md.start_pos == (r,c): info += " [起点]"
            if md.end_pos == (r,c): info += " [终点]"
            if (r,c) in md.key_marks: info += " [钥匙]"
            if (r,c) in md.portals: info += f" [跳转→{md.portals[(r,c)]['path']}]"
            parts.append(info)
        if self.clipboard: parts.append(f"剪贴板: {self.clipboard['h']}×{self.clipboard['w']}")
        self.status.config(text="  |  ".join(parts))
    # ---------- 文件操作 ----------
    def new_map(self, silent=False):
        if silent:
            self.map_data = MapData(); self.map_data.tiles = ["air"]*100
            self.current_map_path = None; self.undo_mgr.clear(); self.redraw_canvas(); return
        dlg = NewMapDialog(self); self.wait_window(dlg)
        if not dlg.result: return
        name, r, c, cat, bg = dlg.result
        self.map_data = MapData(); self.map_data.map_name = name
        self.map_data.row_count = r; self.map_data.col_count = c
        self.map_data.category = cat; self.map_data.background = bg
        self.map_data.tiles = ["air"] * (r*c); self.current_map_path = None
        self.undo_mgr.clear(); self.redraw_canvas(); self._update_status()
    def open_mdmap(self):
        p = filedialog.askopenfilename(filetypes=[("MDMap","*.mdmap")])
        if p: self._load_map_file(p)
    def _load_map_file(self, p):
        try:
            with open(p, "r", encoding="utf-8") as f: text = f.read()
            self.map_data = MapData.parse_text(text); self.current_map_path = p
            # 从新属性系统同步 legacy 字段（旧格式由 parse_text 直接设置 legacy，
            # sync_legacy_attrs 会覆盖；因此统一以 tile_attrs 为准）
            self.map_data.sync_legacy_attrs(self.attr_lib)
            self.undo_mgr.clear(); self.redraw_canvas(); self._update_status()
            cfg = add_history(p); save_config(cfg)
        except Exception as e:
            messagebox.showerror("读取失败", str(e))
    def _validate_and_confirm(self):
        warns = self.map_data.validate(self.tile_library)
        if warns:
            msg = "\n".join(warns[:15])
            if len(warns) > 15: msg += f"\n...还有 {len(warns)-15} 条"
            return messagebox.askyesno("导出警告", msg + "\n\n仍要保存？")
        return True
    def save_mdmap(self):
        if self.current_map_path:
            if not self._validate_and_confirm(): return
            try:
                with open(self.current_map_path, "w", encoding="utf-8") as f:
                    f.write(self.map_data.to_text())
                messagebox.showinfo("成功", "已保存")
            except Exception as e: messagebox.showerror("失败", str(e))
        else: self.save_as_mdmap()
    def save_as_mdmap(self):
        p = filedialog.asksaveasfilename(defaultextension=".mdmap", filetypes=[("MDMap","*.mdmap")])
        if not p: return
        if not self._validate_and_confirm(): return
        try:
            with open(p, "w", encoding="utf-8") as f: f.write(self.map_data.to_text())
            self.current_map_path = p; cfg = add_history(p); save_config(cfg)
            messagebox.showinfo("成功", "已保存")
        except Exception as e: messagebox.showerror("失败", str(e))
    def resize_map(self):
        dlg = ResizeMapDialog(self, self.map_data.row_count, self.map_data.col_count)
        self.wait_window(dlg)
        if not dlg.result: return
        nr, nc = dlg.result
        self.undo_mgr.snapshot(self.map_data)
        old_r, old_c = self.map_data.row_count, self.map_data.col_count
        new_tiles = []
        for r in range(nr):
            for c in range(nc):
                if r < old_r and c < old_c:
                    new_tiles.append(self._tile_at(r, c))
                else:
                    new_tiles.append("air")
        self.map_data.tiles = new_tiles; self.map_data.row_count = nr; self.map_data.col_count = nc
        # 清理越界标记
        if self.map_data.start_pos and (self.map_data.start_pos[0] >= nr or self.map_data.start_pos[1] >= nc):
            self.map_data.start_pos = None
        if self.map_data.end_pos and (self.map_data.end_pos[0] >= nr or self.map_data.end_pos[1] >= nc):
            self.map_data.end_pos = None
        self.map_data.key_marks = {(r,c) for r,c in self.map_data.key_marks if r < nr and c < nc}
        self.map_data.portals = {k:v for k,v in self.map_data.portals.items() if k[0] < nr and k[1] < nc}
        self.redraw_canvas(); self._update_status()
    def open_mdtile(self):
        p = filedialog.askopenfilename(filetypes=[("MDT/MDTile","*.mdt;*.mdtile")])
        if not p: return
        try:
            if p.lower().endswith(".mdt"):
                lib = self._load_mdt_to_lib(p)
            else:
                lib = {}
                with open(p, "r", encoding="utf-8") as f:
                    for line in f.readlines():
                        line = line.strip()
                        if not line: continue
                        parts = line.split("#", 3)
                        if len(parts) < 3: continue
                        code, name, img = parts[0], parts[1], parts[2]
                        cat = parts[3] if len(parts) > 3 else "未分类"
                        td = TileDefine(code, name, img, walkable=False, layer="0", category=cat)
                        td.load_image((self.effective_tile_size, self.effective_tile_size))
                        lib[code] = td
            # 强制修正air
            if "air" in lib:
                lib["air"].walkable = True
                lib["air"].layer = "-5"
                lib["air"].category = "基础"
            else:
                lib["air"] = TileDefine("air","空气","",walkable=True,layer="-5",category="基础")
            self.tile_library = lib; self.last_mdtile = p
            cfg = load_config(); cfg["last_mdtile"] = p; save_config(cfg)
            self.reload_tile_images(); self.refresh_tile_list(); self.redraw_canvas()
            messagebox.showinfo("成功", f"载入 {len(lib)} 个瓦片")
        except Exception as e: messagebox.showerror("失败", str(e))
    def _load_mdt_to_lib(self, path):
        """从 .mdt (zip) 加载到 dict (TileDefine)。"""
        lib = {}
        tmpdir = tempfile.mkdtemp(prefix="mdt_extract_")
        try:
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(tmpdir)
        except Exception:
            return lib
        txt_path = os.path.join(tmpdir, "tiles.txt")
        if not os.path.exists(txt_path): return lib
        res_dir = os.path.join(tmpdir, "res")
        with open(txt_path, "r", encoding="utf-8") as f:
            for line in f.readlines():
                line = line.strip()
                if not line: continue
                parts = line.split("#", 3)
                if len(parts) < 3: continue
                code, name, img = parts[0], parts[1], parts[2]
                cat = parts[3] if len(parts) > 3 else "未分类"
                image_bytes = None; img_path_disp = img
                if img.startswith("res://"):
                    fname = img[len("res://"):]
                    full = os.path.join(res_dir, fname)
                    if os.path.exists(full):
                        try:
                            with open(full, "rb") as bf: image_bytes = bf.read()
                            img_path_disp = full
                        except Exception: pass
                td = TileDefine(code, name, img_path_disp, walkable=False, layer="0",
                                category=cat, image_bytes=image_bytes)
                td.load_image((self.effective_tile_size, self.effective_tile_size))
                lib[code] = td
        return lib
    def open_tile_editor(self):
        TileLibraryEditor(self, self.tile_library, self.tile_size, self.last_mdtile)
    def edit_map_info(self):
        dlg = MapInfoDialog(self, self.map_data); self.wait_window(dlg)
        if not dlg.result: return
        self.undo_mgr.snapshot(self.map_data)
        name, cat, bg = dlg.result
        self.map_data.map_name = name; self.map_data.category = cat; self.map_data.background = bg
        self._update_status()
# ===================== 启动 =====================
if __name__ == "__main__":
    import sys
    import os
    enable_dpi_awareness()
    app = MainMenu()

    launch_file = None
    if len(sys.argv) >= 2:
        p = sys.argv[1]
        if os.path.exists(p):
            launch_file = p

    is_launch_editor_direct = False
    if launch_file:
        ext = os.path.splitext(launch_file)[1].lower()
        if ext == ".mdmap":
            # mdmap：直接打开编辑器，编辑器关闭后整个程序退出，不显示主界面
            app._launch_editor(map_path=launch_file)
            is_launch_editor_direct = True
        elif ext in (".mdtile", ".mdt"):
            # mdtile / mdt：临时加载，询问是否保存到config作为默认瓦片库
            # _load_mdtile_silent 内部已按后缀分派 .mdt 走 _load_mdt_silent
            app._load_mdtile_silent(launch_file)
            app._update_tile_label()
            res = messagebox.askyesno("瓦片库", f"已加载瓦片库:\n{launch_file}\n\n是否设为默认瓦片库(写入config.json)?")
            if res:
                app.cfg["last_mdtile"] = launch_file
                save_config(app.cfg)
        elif ext == ".mdattr":
            # mdattr：导入属性到 attributes.json，下次编辑器自动加载
            try:
                with open(launch_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                lib = AttributeLibrary()
                lib.load_from_dict(data)
                lib.save()
                messagebox.showinfo("属性列表", f"已导入 {len(lib.attrs)} 个属性:\n{launch_file}\n\n(已写入 attributes.json)")
            except Exception as e:
                messagebox.showerror("导入失败", str(e))

    if not is_launch_editor_direct:
        app.mainloop()

