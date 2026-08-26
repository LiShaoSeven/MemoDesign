import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import os
import json
import ctypes
import sys

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
                return json.load(f)
    except Exception:
        pass
    return {"last_mdtile": "", "history": []}

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

def load_shortcuts():
    try:
        if os.path.exists(SHORTCUT_FILE):
            with open(SHORTCUT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return dict(DEFAULT_SHORTCUTS)

def save_shortcuts(shortcuts):
    try:
        with open(SHORTCUT_FILE, "w", encoding="utf-8") as f:
            json.dump(shortcuts, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        messagebox.showerror("保存失败", f"无法保存快捷键设置：\n{e}")
        return False

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
            "tiles": list(map_data.tiles),
            "start_pos": map_data.start_pos,
            "end_pos": map_data.end_pos,
            "key_marks": set(map_data.key_marks),
            "portals": {f"{k[0]},{k[1]}": dict(v) for k, v in map_data.portals.items()},
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
            "map_name": md.map_name, "row_count": md.row_count, "col_count": md.col_count,
            "tiles": list(md.tiles), "start_pos": md.start_pos, "end_pos": md.end_pos,
            "key_marks": set(md.key_marks),
            "portals": {f"{k[0]},{k[1]}": dict(v) for k, v in md.portals.items()},
        }
    @staticmethod
    def _restore(snap, md):
        md.map_name = snap["map_name"]; md.row_count = snap["row_count"]; md.col_count = snap["col_count"]
        md.tiles = list(snap["tiles"]); md.start_pos = snap.get("start_pos"); md.end_pos = snap.get("end_pos")
        md.key_marks = set(snap.get("key_marks", set()))
        portals = {}
        for k, v in snap.get("portals", {}).items():
            r, c = k.split(","); portals[(int(r), int(c))] = v
        md.portals = portals

# ===================== 数据模型 =====================
class TileDefine:
    def __init__(self, code: str, name: str, img_path: str,
                 walkable: bool = False, layer: str = "0", category: str = ""):
        self.code = code
        self.name = name
        self.img_path = img_path
        self.walkable = walkable
        self.layer = layer
        self.category = category #新增瓦片分类
        self.image = None
        self.photo = None

    def load_image(self, size=(48, 48)):
        try:
            img = Image.open(self.img_path).convert("RGBA")
            img = img.resize(size, Image.Resampling.LANCZOS)
            self.image = img
            self.photo = ImageTk.PhotoImage(img)
        except Exception:
            self.image = None
            self.photo = None

class MapData:
    def __init__(self):
        self.map_name = "Untitled"; self.row_count = 10; self.col_count = 10
        self.tiles = []; self.start_pos = None; self.end_pos = None
        self.key_marks = set(); self.portals = {}
    def to_text(self):
        lines = [f"MemoDesign:{self.map_name}", f"Row:{self.row_count}", f"Column:{self.col_count}", "Tile:"]
        total = self.row_count * self.col_count
        for idx in range(total):
            code = self.tiles[idx] if idx < len(self.tiles) else "air"
            r, c = divmod(idx, self.col_count)
            prefix = ""
            if (r, c) in self.portals:
                p = self.portals[(r, c)]
                prefix = f"!{p['color']}@{p['path']}@"
            else:
                if self.start_pos and (r, c) == self.start_pos: prefix = "$"
                elif self.end_pos and (r, c) == self.end_pos: prefix = "%"
                if (r, c) in self.key_marks: prefix = "?" + prefix
            lines.append(prefix + code)
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
            elif line == "Tile:": tile_start = i + 1
        if tile_start != -1:
            raw = lines[tile_start:]
            expect = md.row_count * md.col_count
            while len(raw) < expect: raw.append("air")
            raw = raw[:expect]
            parsed = []
            for idx, item in enumerate(raw):
                r, c = divmod(idx, md.col_count)
                code = item; is_key = False
                if code.startswith("!"):
                    rest = code[1:]; at1 = rest.find("@")
                    color = rest[:at1]; rest2 = rest[at1+1:]; at2 = rest2.find("@")
                    path = rest2[:at2]; real = rest2[at2+1:]
                    md.portals[(r, c)] = {"path": path, "color": color}; code = real
                else:
                    if code.startswith("?"): is_key = True; code = code[1:]
                    if code.startswith("$"): code = code[1:]; md.start_pos = (r, c)
                    elif code.startswith("%"): code = code[1:]; md.end_pos = (r, c)
                    if is_key: md.key_marks.add((r, c))
                parsed.append(code)
            md.tiles = parsed
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
        super().__init__(parent); self.title("新建地图"); self.geometry("320x200")
        self.resizable(False, False); self.transient(parent); self.grab_set(); self.result = None
        f = ttk.Frame(self, padding=10); f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text="地图名称:").grid(row=0, column=0, sticky="w", pady=4)
        self.var_name = tk.StringVar(value="newmap")
        ttk.Entry(f, textvariable=self.var_name, width=22).grid(row=0, column=1, padx=6)
        ttk.Label(f, text="行数:").grid(row=1, column=0, sticky="w", pady=4)
        self.var_row = tk.StringVar(value="10")
        ttk.Entry(f, textvariable=self.var_row, width=22).grid(row=1, column=1, padx=6)
        ttk.Label(f, text="列数:").grid(row=2, column=0, sticky="w", pady=4)
        self.var_col = tk.StringVar(value="10")
        ttk.Entry(f, textvariable=self.var_col, width=22).grid(row=2, column=1, padx=6)
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
        try:
            r = int(self.var_row.get()); c = int(self.var_col.get())
            if r < 1 or c < 1: messagebox.showwarning("提示", "行列必须≥1"); return
            self.result = (name, r, c); self.destroy()
        except ValueError:
            messagebox.showerror("错误", "行列请输入有效数字！")

class ResizeMapDialog(tk.Toplevel):
    def __init__(self, parent, cur_row, cur_col):
        super().__init__(parent); self.title("调整地图大小"); self.geometry("300x160")
        self.resizable(False, False); self.transient(parent); self.grab_set(); self.result = None
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

class PortalEditDialog(tk.Toplevel):
    def __init__(self, parent, old_portal=None):
        super().__init__(parent); self.title("关卡跳转格设置"); self.geometry("420x180")
        self.resizable(False, False); self.transient(parent); self.grab_set(); self.result = None
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
        self.geometry("380x340"); self.resizable(False, False)
        self.transient(parent); self.grab_set()
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
        ttk.Label(f, text="可通行:").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Checkbutton(f, variable=self.var_walkable).grid(row=4, column=1, sticky="w", padx=6)
        ttk.Label(f, text="图层:").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.var_layer, width=10).grid(row=5, column=1, sticky="w", padx=6)
        ttk.Label(f, text="分类:").grid(row=6, column=0, sticky="w", pady=4)
        cb = ttk.Combobox(f, textvariable=self.var_category, values=self.categories, width=14)
        cb.grid(row=6, column=1, sticky="w", padx=6)
        bf = ttk.Frame(f); bf.grid(row=7, column=0, columnspan=2, pady=10)
        ttk.Button(bf, text="确认", command=self.ok).pack(side=tk.LEFT, padx=8)
        ttk.Button(bf, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=8)
        self._center(parent)
    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    def select_image(self):
        p = filedialog.askopenfilename(title="选择瓦片图片", filetypes=[("图片","*.png;*.jpg;*.jpeg;*.bmp")])
        if p: self.selected_img_path = p; self.label_img.config(text=p)
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
        super().__init__(parent); self.title("批量加入瓦片"); self.geometry("720x460")
        self.transient(parent); self.grab_set(); self.exist_codes = exist_codes; self.result = []
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
        "tool_brush":"画笔","tool_eraser":"橡皮","tool_rect":"矩形","tool_fill":"填充",
        "tool_copy":"复制选择","attr_start":"属性:起始点","attr_end":"属性:结束点",
        "attr_key":"属性:钥匙","attr_portal":"属性:跳转格","tool_pan":"画布拖拽",
    }
    def __init__(self, parent, shortcuts):
        super().__init__(parent); self.title("快捷键设置"); self.geometry("520x540")
        self.transient(parent); self.grab_set(); self.shortcuts = dict(shortcuts)
        mf = ttk.Frame(self, padding=10); mf.pack(fill=tk.BOTH, expand=True)
        ttk.Label(mf, text="双击一行后按下新组合键。", font=("Arial",9)).pack(anchor="w", pady=(0,8))
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

# ===================== 瓦片库编辑器 =====================
class TileLibraryEditor(tk.Toplevel):
    def __init__(self, parent, tile_lib, tile_pixel_size, mdtile_path=None):
        super().__init__(parent); self.title("瓦片库编辑器 .mdtile"); self.geometry("760x480")
        self.parent_app = parent; self.tile_lib = tile_lib; self.tile_size = tile_pixel_size
        self.transient(parent); self.current_path = mdtile_path
        top = ttk.Frame(self); top.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(top, text="新增瓦片", command=self.add_tile).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="编辑选中", command=self.edit_tile).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="删除选中", command=self.del_tile).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="批量加入", command=self.batch_add).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="导出 .json", command=self.export_json).pack(side=tk.RIGHT, padx=2)
        ttk.Button(top, text="另存为 .mdtile", command=self.save_as_mdtile).pack(side=tk.RIGHT, padx=2)
        ttk.Button(top, text="保存 .mdtile", command=self.save_mdtile).pack(side=tk.RIGHT, padx=2)
        cols = ("code","name","imgpath","category","walkable","layer")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for k, l, w in [("code","代码",80),("name","名称",100),("imgpath","图片",300),("category","分类",80),("walkable","可通行",60),("layer","图层",50)]:
            self.tree.heading(k, text=l); self.tree.column(k, width=w, anchor="w")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
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
        p = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json")])
        if not p: return
        data = {"tile_size": [self.tile_size, self.tile_size], "tiles": {}}
        for td in self.tile_lib.values():
            data["tiles"][td.code] = {"name": td.name, "texture": td.img_path,
                "walkable": td.walkable, "layer": td.layer}
        with open(p, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
        messagebox.showinfo("成功", f"已导出 JSON（不含分类字段）:\n{p}")
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


# ===================== 主界面 =====================
class MainMenu(tk.Tk):
    def __init__(self):
        super().__init__(); set_app_id()
        self.title("MemoDesign"); self.geometry("800x520"); self.resizable(False, False)
        self.cfg = load_config()
        # 自动加载上次mdtile
        self.tile_library = {}
        last = self.cfg.get("last_mdtile", "")
        if last and os.path.exists(last):
            self._load_mdtile_silent(last)

        # 主分割容器：左右对半分
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # -------- 左侧面板：标题+按钮+瓦片库状态【全部左对齐】 --------
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=1)

        # anchor="nw" = 靠左上角，不再整体居中；去掉expand=True
        left_inner = ttk.Frame(left_frame)
        left_inner.pack(anchor="nw", pady=10)

        tk.Label(left_inner, text="MemoDesign", font=("Arial", 32, "bold"), fg="#13245e").pack(anchor="w", pady=(0,6))
        tk.Label(left_inner, text="瓦片地图编辑器", font=("Arial", 12), fg="#13245e").pack(anchor="w", pady=(0,25))

        style = ttk.Style(); style.configure("Big.TButton", font=("Arial", 11), padding=10)
        ttk.Button(left_inner, text="  打开地图  ", style="Big.TButton", command=self.open_map).pack(anchor="w", pady=6)
        ttk.Button(left_inner, text="  新建地图  ", style="Big.TButton", command=self.new_map).pack(anchor="w", pady=6)
        ttk.Button(left_inner, text="  加载瓦片库  ", style="Big.TButton", command=self.load_tiles).pack(anchor="w", pady=6)

        self.lbl_tile = tk.Label(left_inner, text="", font=("Arial", 9), fg="#13245e")
        self.lbl_tile.pack(anchor="w", pady=(18,0))
        self._update_tile_label()

        # -------- 右侧面板：历史记录 --------
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=1)

        right_inner = ttk.Frame(right_frame)
        right_inner.pack(fill=tk.BOTH, expand=True)

        tk.Label(right_inner, text="最近打开", font=("Arial", 10, "bold"), fg="#13245e").pack(anchor="w", pady=(0,4))
        self.lb_hist = tk.Listbox(right_inner, height=10, fg="#13245e",
            highlightthickness=0, activestyle="none", font=("Arial",9))
        self.lb_hist.pack(fill=tk.BOTH, expand=True)

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

    def _load_mdtile_silent(self, path):
        try:
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

    def load_tiles(self):
        p = filedialog.askopenfilename(filetypes=[("MDTile","*.mdtile")])
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
        self.title("MemoDesign - 编辑器"); self.geometry("1200x760")
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
        # 悬浮预览
        self._preview_win = None; self._preview_item = None
        self.create_menu(); self.create_widgets(); self.bind_all_shortcuts()
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
        mf.add_separator()
        mf.add_command(label="调整地图大小", command=self.resize_map)
        mf.add_command(label="加载瓦片库(.mdtile)", command=self.open_mdtile)
        mf.add_command(label="瓦片库编辑器", command=self.open_tile_editor, accelerator=self._accel("tile_editor"))
        mf.add_separator()
        mf.add_command(label="返回主界面", command=self._on_close)
        mb.add_cascade(label="文件", menu=mf)
        me = tk.Menu(mb, tearoff=0)
        me.add_command(label="撤销", command=self.do_undo, accelerator=self._accel("undo"))
        me.add_command(label="重做", command=self.do_redo, accelerator=self._accel("redo"))
        me.add_separator()
        me.add_command(label="快捷键设置", command=self.open_shortcut_settings)
        mb.add_cascade(label="编辑", menu=me)
        self.config(menu=mb)
    def open_shortcut_settings(self):
        dlg = ShortcutSettingsDialog(self, self.shortcuts); self.wait_window(dlg)
        self.shortcuts = load_shortcuts()
    # ---------- UI ----------
    def create_widgets(self):
        # 工具栏
        tb = ttk.Frame(self); tb.pack(fill=tk.X, padx=4, pady=3)

        def icon_btn(parent, name, fallback_text, cmd):
            ic = load_icon(name)
            if ic:
                self._icon_cache[name] = ic
                # tk.Button：正方形按钮，像素宽高，只画图标(compound="top")
                return tk.Button(
                    parent,
                    image=self._icon_cache[name],
                    compound="top",
                    width=26,
                    height=26,
                    command=cmd,
                    relief=tk.RAISED,
                    bd=1
                )
            # 图标加载失败，降级ttk文字按钮
            return ttk.Button(parent, text=fallback_text, command=cmd, width=3)

        icon_btn(tb, "new", "新", self.new_map).pack(side=tk.LEFT, padx=2)
        icon_btn(tb, "open", "开", self.open_mdmap).pack(side=tk.LEFT, padx=2)
        icon_btn(tb, "save", "存", self.save_mdmap).pack(side=tk.LEFT, padx=2)
        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)

        icon_btn(tb, "undo", "↶", self.do_undo).pack(side=tk.LEFT, padx=2)
        icon_btn(tb, "redo", "↷", self.do_redo).pack(side=tk.LEFT, padx=2)
        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)

        self.btn_brush = icon_btn(tb, "brush", "笔", lambda: self.set_mode("brush"))
        self.btn_brush.pack(side=tk.LEFT, padx=2)
        self.btn_eraser = icon_btn(tb, "eraser", "擦", lambda: self.set_mode("eraser"))
        self.btn_eraser.pack(side=tk.LEFT, padx=2)
        self.btn_rect = icon_btn(tb, "rect", "矩", lambda: self.set_mode("rect"))
        self.btn_rect.pack(side=tk.LEFT, padx=2)
        self.btn_fill = icon_btn(tb, "fill", "填", lambda: self.set_mode("fill"))
        self.btn_fill.pack(side=tk.LEFT, padx=2)
        self.btn_copy = icon_btn(tb, "copy", "复", lambda: self.set_mode("copy"))
        self.btn_copy.pack(side=tk.LEFT, padx=2)

        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
        self.btn_attr = icon_btn(tb, "attr", "属", lambda: self.set_mode("attr"))
        self.btn_attr.pack(side=tk.LEFT, padx=2)

        self.var_attr = tk.StringVar(value=self.ATTR_LABELS["startpoint"])
        self.cmb_attr = ttk.Combobox(tb, textvariable=self.var_attr, state="readonly", width=8)
        self.cmb_attr["values"] = [self.ATTR_LABELS[t] for t in self.ATTR_TYPES]
        self.cmb_attr.current(0); self.cmb_attr.pack(side=tk.LEFT, padx=2)
        self.cmb_attr.bind("<<ComboboxSelected>>", self._on_attr_change)

        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
        self.btn_pan = icon_btn(tb, "pan", "拖", lambda: self.set_mode("pan"))
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

        self.mode_label = ttk.Label(tb, text="模式: 画笔", foreground="#555")
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
        self.canvas = tk.Canvas(left, bg="#222222", highlightthickness=0)
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
        ttk.Label(right, text="瓦片素材库", font=("Arial",11,"bold")).pack(pady=4)
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
        win.configure(bg="#2a2a3a")
        x = self.winfo_rootx() + self.winfo_width() - 260
        y = event.y_root + 10
        win.geometry(f"+{x}+{y}")
        # 图片
        if td.photo:
            lbl_img = tk.Label(win, image=td.photo, bg="#2a2a3a"); lbl_img.pack(padx=8, pady=8)
        info = f"代码: {td.code}\n名称: {td.name}\n分类: {td.category}\n图层: {td.layer}\n可通行: {'是' if td.walkable else '否'}\n图片: {os.path.basename(td.img_path) if td.img_path else '无'}"
        tk.Label(win, text=info, fg="#ddd", bg="#2a2a3a", justify="left", font=("Arial",9)).pack(padx=8, pady=(0,8))
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
        names = {"brush":"画笔","eraser":"橡皮","rect":"矩形","fill":"填充","copy":"复制选择","attr":f"属性({self.ATTR_LABELS[self.attr_subtype]})","pan":"拖拽"}
        self.mode_label.config(text=f"模式: {names.get(mode, mode)}")
        self._dragging = False; self._pan_active = False; self.rect_start = None
        self.redraw_canvas()
    def set_attr_subtype(self, sub):
        self.attr_subtype = sub; self.var_attr.set(self.ATTR_LABELS[sub]); self.set_mode("attr")
    def _on_attr_change(self, e):
        label = self.var_attr.get()
        for t, l in self.ATTR_LABELS.items():
            if l == label: self.attr_subtype = t; break
        if self.draw_mode == "attr": self.mode_label.config(text=f"模式: 属性({label})")
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
        self.undo_mgr.snapshot(self.map_data)
        sub = self.attr_subtype
        if sub == "startpoint":
            self.map_data.start_pos = (r, c)
            if self.map_data.end_pos == (r, c): self.map_data.end_pos = None
            self.map_data.key_marks.discard((r, c)); self.map_data.portals.pop((r, c), None)
        elif sub == "endpoint":
            self.map_data.end_pos = (r, c)
            if self.map_data.start_pos == (r, c): self.map_data.start_pos = None
            self.map_data.key_marks.discard((r, c)); self.map_data.portals.pop((r, c), None)
        elif sub == "key":
            if (r, c) in self.map_data.key_marks: self.map_data.key_marks.remove((r, c))
            else: self.map_data.key_marks.add((r, c))
            if self.map_data.start_pos == (r, c): self.map_data.start_pos = None
            if self.map_data.end_pos == (r, c): self.map_data.end_pos = None
            self.map_data.portals.pop((r, c), None)
        elif sub == "portal":
            # 修复bug：已有portal则编辑，没有则新建
            old = self.map_data.portals.get((r, c))
            dlg = PortalEditDialog(self, old)
            self.wait_window(dlg)
            if dlg.result is None:
                self.undo_mgr.undo_stack.pop(); return
            self.map_data.portals[(r, c)] = dlg.result
            if self.map_data.start_pos == (r, c): self.map_data.start_pos = None
            if self.map_data.end_pos == (r, c): self.map_data.end_pos = None
            self.map_data.key_marks.discard((r, c))
        self.redraw_canvas()
    def _attr_right_click(self, r, c, event):
        """attr模式右键：弹出菜单，可编辑/删除该格子的标记"""
        menu = tk.Menu(self, tearoff=0)
        has = False
        if self.map_data.start_pos == (r, c):
            has = True; menu.add_command(label="删除起始点", command=lambda: self._del_mark("start", r, c))
        if self.map_data.end_pos == (r, c):
            has = True; menu.add_command(label="删除结束点", command=lambda: self._del_mark("end", r, c))
        if (r, c) in self.map_data.key_marks:
            has = True; menu.add_command(label="删除钥匙标记", command=lambda: self._del_mark("key", r, c))
        if (r, c) in self.map_data.portals:
            has = True
            menu.add_command(label="编辑跳转格", command=lambda: self._edit_portal(r, c))
            menu.add_command(label="删除跳转格", command=lambda: self._del_mark("portal", r, c))
        if not has:
            menu.add_command(label="(此格无标记)", command=lambda: None)
        menu.tk_popup(event.x_root, event.y_root)
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
                        self.canvas.create_text(px+sz//2, py+sz//2, text=txt, fill="#888", font=("Arial", fs))
                # 属性标记
                if self.show_start.get() and self.map_data.start_pos == (y, x):
                    self._dot(px+sz//2, py+sz//2, max(6,sz//2), (255,51,51,180))
                if self.show_end.get() and self.map_data.end_pos == (y, x):
                    self._dot(px+sz//2, py+sz//2, max(6,sz//2), (51,255,51,180))
                if self.show_key.get() and (y, x) in self.map_data.key_marks:
                    d = max(5, sz//3); self._dot(px+sz-d//2, py+d//2, d, (255,220,0,220))
                if self.show_portal.get() and (y, x) in self.map_data.portals:
                    p = self.map_data.portals[(y, x)]; col = "#" + p["color"]
                    self.canvas.create_rectangle(px+1, py+1, px+sz-1, py+sz-1, outline=col, width=2)
                    b = max(4, sz//4)
                    self.canvas.create_rectangle(px+2, py+2, px+2+b, py+2+b, fill=col, outline=col)
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
        name, r, c = dlg.result
        self.map_data = MapData(); self.map_data.map_name = name
        self.map_data.row_count = r; self.map_data.col_count = c
        self.map_data.tiles = ["air"] * (r*c); self.current_map_path = None
        self.undo_mgr.clear(); self.redraw_canvas(); self._update_status()
    def open_mdmap(self):
        p = filedialog.askopenfilename(filetypes=[("MDMap","*.mdmap")])
        if p: self._load_map_file(p)
    def _load_map_file(self, p):
        try:
            with open(p, "r", encoding="utf-8") as f: text = f.read()
            self.map_data = MapData.parse_text(text); self.current_map_path = p
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
        p = filedialog.askopenfilename(filetypes=[("MDTile","*.mdtile")])
        if not p: return
        try:
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
    def open_tile_editor(self):
        TileLibraryEditor(self, self.tile_library, self.tile_size, self.last_mdtile)

# ===================== 启动 =====================
if __name__ == "__main__":
    import sys
    import os
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
        elif ext == ".mdtile":
            # mdtile：临时加载，询问是否保存到config作为默认瓦片库
            app._load_mdtile_silent(launch_file)
            app._update_tile_label()
            res = messagebox.askyesno("瓦片库", f"已加载瓦片库:\n{launch_file}\n\n是否设为默认瓦片库(写入config.json)?")
            if res:
                app.cfg["last_mdtile"] = launch_file
                save_config(app.cfg)

    if not is_launch_editor_direct:
        app.mainloop()
