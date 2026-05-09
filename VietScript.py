import tkinter as tk
from tkinter import scrolledtext
import re
import sys
import threading
import queue

class VietScriptEngine:
    KEYWORDS = {
        'bin': 'print', 'nhap': 'input', 'neu': 'if', 'nguoc': 'else',
        'khac': 'elif', 'lap': 'for', 'khi': 'while', 'trong': 'in',
        'ham': 'def', 'tra_ve': 'return', 'dung': 'True', 'sai': 'False',
        'nhap_vien': 'import', 'va': 'and', 'hoac': 'or', 'la': 'is',
        'khong': 'not', 'lop': 'class', 'voi': 'with', 'nhu': 'as',
        'in_ra': 'print' 
    }

    @classmethod
    def compile(cls, source):
        pattern = r'(\".*?\"|\'.*?\'|\b' + r'\b|\b'.join(cls.KEYWORDS.keys()) + r'\b)'
        
        def replace(match):
            token = match.group(0)
            if token.startswith(('"', "'")):
                return token
            return cls.KEYWORDS.get(token, token)

        return re.sub(pattern, replace, source)

class AutocompleteBox:
    def __init__(self, editor):
        self.editor = editor
        self.words = sorted(list(VietScriptEngine.KEYWORDS.keys()))
        self.top = None
        self.listbox = None
        self.active = False

    def show(self, suggestions, x, y):
        if self.active: self.hide()
        
        self.top = tk.Toplevel(self.editor)
        self.top.wm_overrideredirect(True)
        self.top.wm_geometry(f"+{x}+{y}")
        
        self.listbox = tk.Listbox(self.top, font=("Consolas", 11), bg="#2d2d2d", fg="#d4d4d4", 
                                  selectbackground="#0e639c", borderwidth=0, highlightthickness=0)
        self.listbox.pack()
        
        for word in suggestions:
            self.listbox.insert(tk.END, word)
        
        self.listbox.selection_set(0)
        self.active = True

    def hide(self):
        if self.top:
            self.top.destroy()
            self.top = None
        self.active = False

    def get_selection(self):
        if self.active:
            return self.listbox.get(tk.ACTIVE)
        return None

class LineNumbers(tk.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text_widget = None

    def redraw(self):
        self.delete("all")
        if not self.text_widget: return
        i = self.text_widget.index("@0,0")
        while True:
            dline = self.text_widget.dlineinfo(i)
            if dline is None: break
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.create_text(35, y, anchor="ne", text=linenum, fill="#858585", font=("Consolas", 12))
            i = self.text_widget.index("%s+1line" % i)

class ModernTerminal(scrolledtext.ScrolledText):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.input_queue = queue.Queue()
        self.config(state=tk.DISABLED, insertbackground="white")
        self.bind("<Return>", self._on_enter)
        self.bind("<Key>", self._filter_keys)
        self.input_start_index = "1.0"

    def _filter_keys(self, event):
        if self.cget("state") == tk.DISABLED: return "break"
        if event.keysym in ("BackSpace", "Left"):
            if self.compare(tk.INSERT, "<=", self.input_start_index):
                return "break"

    def _on_enter(self, event):
        content = self.get(self.input_start_index, tk.END).strip()
        self.insert(tk.END, "\n")
        self.input_queue.put(content)
        self.config(state=tk.DISABLED)
        return "break"

    def read_input(self):
        self.after(0, self._prepare_for_input)
        return self.input_queue.get()

    def _prepare_for_input(self):
        self.config(state=tk.NORMAL)
        self.mark_set("insert", tk.END)
        self.input_start_index = self.index("insert")
        self.focus_set()

    def write_output(self, text, tag=None):
        self.after(0, self._unsafe_write, text, tag)

    def _unsafe_write(self, text, tag):
        self.config(state=tk.NORMAL)
        self.insert(tk.END, text, tag)
        self.see(tk.END)
        self.config(state=tk.DISABLED)

class StdOutRedirect:
    def __init__(self, terminal_widget):
        self.terminal = terminal_widget
    def write(self, s):
        self.terminal.write_output(s)
    def flush(self):
        pass

class StdInRedirect:
    def __init__(self, terminal_widget):
        self.terminal = terminal_widget
    def readline(self):
        return self.terminal.read_input() + "\n"

class VietScriptIDE:
    def __init__(self, root):
        self.root = root
        self.root.title("VietScript IDE v1.0 Unstable Release")
        self.root.geometry("1100x850")
        self.root.configure(bg="#1e1e1e")
        self.setup_ui()
        self.suggestion_engine = AutocompleteBox(self.editor)
        
    def setup_ui(self):
        self.toolbar = tk.Frame(self.root, bg="#252526", height=45)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        
        self.run_btn = tk.Button(self.toolbar, text="CHẠY CODE (F5)", bg="#0e639c", fg="white",
                                 command=self.execute_engine, font=("Segoe UI", 9, "bold"),
                                 padx=20, relief=tk.FLAT)
        self.run_btn.pack(side=tk.LEFT, padx=10, pady=7)

        container = tk.Frame(self.root, bg="#1e1e1e")
        container.pack(expand=True, fill="both", padx=10, pady=(5, 0))

        self.line_nums = LineNumbers(container, width=45, bg="#1e1e1e", highlightthickness=0)
        self.line_nums.pack(side=tk.LEFT, fill=tk.Y)

        self.editor = scrolledtext.ScrolledText(container, font=("Cascadia Code", 12),
                                                bg="#1e1e1e", fg="#d4d4d4",
                                                insertbackground="white", undo=True, borderwidth=0)
        self.editor.pack(side=tk.LEFT, expand=True, fill="both")
        self.line_nums.text_widget = self.editor

        self.terminal = ModernTerminal(self.root, height=12, font=("Consolas", 11),
                                       bg="#000000", fg="#cccccc", borderwidth=0)
        self.terminal.pack(fill=tk.X, padx=10, pady=10)
        self.terminal.tag_config("error", foreground="#f48771")
        self.terminal.tag_config("success", foreground="#89d185")

        self.editor.bind("<KeyRelease>", self.on_key_release)
        self.editor.bind("<Tab>", self.handle_tab)
        self.editor.bind("<FocusIn>", lambda e: self.suggestion_engine.hide())
        self.root.bind("<F5>", lambda e: self.execute_engine())

    def on_key_release(self, event):
        self.line_nums.redraw()
        
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return

        cursor_pos = self.editor.index(tk.INSERT)
        line, col = map(int, cursor_pos.split('.'))
        current_line = self.editor.get(f"{line}.0", cursor_pos)
        match = re.search(r"(\w+)$", current_line)
        
        if match:
            typed_word = match.group(1)
            suggestions = [w for w in self.suggestion_engine.words if w.startswith(typed_word)]
            
            if suggestions:
                bbox = self.editor.bbox(tk.INSERT)
                if bbox:
                    x = self.editor.winfo_rootx() + bbox[0]
                    y = self.editor.winfo_rooty() + bbox[1] + bbox[3]
                    self.suggestion_engine.show(suggestions, x, y)
            else:
                self.suggestion_engine.hide()
        else:
            self.suggestion_engine.hide()

    def handle_tab(self, event):
        if self.suggestion_engine.active:
            selected = self.suggestion_engine.get_selection()
            if selected:
                cursor_pos = self.editor.index(tk.INSERT)
                line, col = map(int, cursor_pos.split('.'))
                line_content = self.editor.get(f"{line}.0", cursor_pos)
                match = re.search(r"(\w+)$", line_content)
                
                if match:
                    start_col = match.start()
                    self.editor.delete(f"{line}.{start_col}", cursor_pos)
                    self.editor.insert(f"{line}.{start_col}", selected)
                
                self.suggestion_engine.hide()
                return "break"
        
        self.editor.insert(tk.INSERT, "    ")
        return "break"

    def execute_engine(self):
        source = self.editor.get("1.0", tk.END)
        if not source.strip(): return
        
        python_code = VietScriptEngine.compile(source)
        
        self.terminal.config(state=tk.NORMAL)
        self.terminal.delete("1.0", tk.END)
        self.terminal.config(state=tk.DISABLED)
        
        self.run_btn.config(state=tk.DISABLED, text="ĐANG CHẠY...")
        threading.Thread(target=self._worker, args=(python_code,), daemon=True).start()

    def _worker(self, code):
        stdout_ref = StdOutRedirect(self.terminal)
        stdin_ref = StdInRedirect(self.terminal)
        
        old_stdout, old_stdin = sys.stdout, sys.stdin
        sys.stdout = stdout_ref
        sys.stdin = stdin_ref
        
        try:
            exec_globals = {"__builtins__": __builtins__}
            exec(code, exec_globals)
            self.terminal.write_output("\n>>> Tiến trình kết thúc thành công.", "success")
        except Exception as e:
            self.terminal.write_output(f"\n[LỖI]: {str(e)}", "error")
        finally:
            sys.stdout, sys.stdin = old_stdout, old_stdin
            self.root.after(0, lambda: self.run_btn.config(state=tk.NORMAL, text="CHẠY CODE (F5)"))

if __name__ == "__main__":
    root = tk.Tk()
    app = VietScriptIDE(root)
    root.mainloop()