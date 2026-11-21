# -*- coding: utf-8 -*-
"""
ZA M次元ラッシュ v3.2
・開始前の設定画面を追加（Start を押すとモードと数値を選べる。config.json に保存可能）(v3.2)
・設定を config.json に外部化。モードごとの数値は別々に保存され、モードを切り替えても消えない (v3.2)
・Type1 の上下移動時間、Type3 の折り返し待機、ループ回数を設定できるように変更 (v3.2)
・PCME 0.2.0 対応（gui 引数、キャンセル時の後処理、Web UI・実行リストでは画面を出さない）(v3.2)
"""
import os
import json
import time
from datetime import datetime

from Commands.PythonCommandBase import PythonCommand, ImageProcPythonCommand
from Commands.Keys import KeyPress, Hat, Button, Direction, Stick

# 【バージョン】NAME（クラス内）と両方を書き換えること
VERSION = '3.2'

# 【設定ファイル】このスクリプトと同じフォルダの config.json を読む
CONFIG_FILE = 'config.json'
SCRIPT_DIR_ABS = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE_ABS = os.path.join(SCRIPT_DIR_ABS, CONFIG_FILE)

# 移動モード: (番号, 表示名, 説明)
MODES = [
    (0, 'Type1', 'ホロエレベーター往復'),
    (1, 'Type2', 'ホロエレベーター移動のみ'),
    (2, 'Type3', 'シャトルラン（上下移動）'),
    (3, 'Type4', 'Fastpass（高速移動）'),
]

DEFAULT_CONFIG = {
    # 共通
    'move_mode': 3,                 # 0: Type1 / 1: Type2 / 2: Type3 / 3: Type4
    'max_loop': 9999,               # ループ回数の上限
    # Type1 / Type2
    'wait_time': 0.2,               # ホロエレベーターの待機時間（秒）
    'elevator_move_time': 2.5,      # Type1: 上下それぞれに歩く時間（秒）
    # Type3（シャトルラン）
    'use_dash': True,               # Bダッシュを使う
    'duration': 3.2,                # 片道の移動時間（秒）
    'dash_delay': 0.05,             # 歩き出してから B を押すまで（秒）
    'shuttle_turn_wait': 0.5,       # 折り返しの待機（秒）
    # Type4（Fastpass）
    'fastpass_wait': 2.2,           # Fastpass 使用後の待機（秒）
    'fastpass_first_y': False,      # 1回目だけ最初に Y を押す
    # 設定画面
    'show_settings_ui': True,       # Start を押したときに設定画面を出す
    'settings_ui_timeout_seconds': 60,  # 操作がなければこの秒数で自動開始（0 = しない）
}

# 数値項目の範囲: キー -> (型, 最小, 最大, 画面の刻み)
NUMERIC_RANGES = {
    'move_mode': (int, 0, 3, 1),
    'max_loop': (int, 1, 999999, 1),
    'wait_time': (float, 0.0, 60.0, 0.1),
    'elevator_move_time': (float, 0.1, 10.0, 0.1),
    'duration': (float, 0.1, 30.0, 0.1),
    'dash_delay': (float, 0.0, 5.0, 0.01),
    'shuttle_turn_wait': (float, 0.0, 10.0, 0.1),
    'fastpass_wait': (float, 0.0, 30.0, 0.1),
    'settings_ui_timeout_seconds': (int, 0, 3600, 1),
}
BOOL_KEYS = ('use_dash', 'fastpass_first_y', 'show_settings_ui')


def _is_true(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == 'true'


def _is_main_thread():
    import threading
    return threading.current_thread() is threading.main_thread()


def normalize_config(cfg):
    """
    値を正しい型にそろえる。おかしい値・範囲外の値は警告を出して初期値に戻す。
    （知らないキーはそのまま残す）
    """
    out = dict(DEFAULT_CONFIG)
    out.update(cfg)
    for key, (typ, lo, hi, _) in NUMERIC_RANGES.items():
        raw = out.get(key)
        try:
            if isinstance(raw, bool):
                raise ValueError
            value = typ(float(raw)) if typ is int else float(raw)
            if value < lo or value > hi:
                raise ValueError
        except (TypeError, ValueError):
            print(f"[Warning] config.json の {key} = {raw!r} は使えません（{lo}〜{hi}）。初期値 {DEFAULT_CONFIG[key]} を使います。")
            value = DEFAULT_CONFIG[key]
        out[key] = value
    for key in BOOL_KEYS:
        out[key] = _is_true(out.get(key))
    return out


def load_config_file():
    """config.json を読んで初期値とまとめる。無い・壊れているときは初期値"""
    data = {}
    if os.path.exists(CONFIG_FILE_ABS):
        try:
            with open(CONFIG_FILE_ABS, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data = loaded
            else:
                print("[Warning] config.json の中身が { } の形ではありません。初期値を使います。")
        except Exception as e:
            print(f"[Warning] config.json を読めませんでした: {e}（初期値を使います）")
    else:
        print(f"[System] config.json が無いので初期値を使います: {CONFIG_FILE_ABS}")
    return normalize_config(data)


def save_config_file(cfg):
    """
    config.json に書き込む。ファイルにあるキーの順番はそのまま、無いキーは後ろに足す。
    （画面に無いキーや、知らないキーも消さない）
    """
    data = {}
    if os.path.exists(CONFIG_FILE_ABS):
        try:
            with open(CONFIG_FILE_ABS, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}
    for key, value in cfg.items():
        data[key] = value
    tmp_path = CONFIG_FILE_ABS + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(tmp_path, CONFIG_FILE_ABS)


class ZA_MDimensionRush(ImageProcPythonCommand):
    # PCME 0.2.0 以降は NAME をソースから構文解析だけで読む（実行しない）。
    # f 文字列や変数を使うとコマンド一覧に出なくなるので、必ず文字列リテラルで書く。
    # バージョンを上げるときは、上の VERSION とこの NAME の両方を書き換えること。
    NAME = 'ZA_M_Dimension_Rush_v3.2'

    def __init__(self, camera, gui=None):
        # PCME 0.2.0: 第2引数にプレビュー（CaptureArea）が渡される。設定画面の親ウィンドウに使う
        try:
            super().__init__(camera, gui)
        except TypeError:
            super().__init__(camera)
        if getattr(self, 'gui', None) is None:
            self.gui = gui

        # 内部変数
        self.start_time = None
        self._last_msg = None
        self.last_log_time = 0

        # 設定（config.json → 無ければ初期値）
        self.apply_config(load_config_file())

    # =========================================================================
    # 設定の反映
    # =========================================================================
    def apply_config(self, cfg):
        cfg = normalize_config(cfg)
        self.config = cfg
        self.move_mode = cfg['move_mode']
        self.max_loop = cfg['max_loop']
        # Type1, 2
        self.wait_time = cfg['wait_time']
        self.elevator_move_time = cfg['elevator_move_time']
        # Type3
        self.use_dash = cfg['use_dash']
        self.duration = cfg['duration']
        self.dash_delay = cfg['dash_delay']
        self.shuttle_turn_wait = cfg['shuttle_turn_wait']
        # Type4
        self.fastpass_wait = cfg['fastpass_wait']
        self.fastpass_first_y = cfg['fastpass_first_y']

    # GUIパラメータ設定（旧方式。渡されなかった項目は今の設定のまま）
    def set_params(self, params: dict):
        cfg = dict(self.config)
        mapping = {'mode': 'move_mode', 'wait': 'wait_time'}
        for key, value in params.items():
            cfg[mapping.get(key, key)] = value
        self.apply_config(cfg)

    # =========================================================================
    # 開始前の設定画面 (v3.2)
    # =========================================================================
    def _tk_root(self):
        """設定画面の親にする Tk のウィンドウ（Web ブラウザ版など、Tk の画面が無いときは None）"""
        gui = getattr(self, 'gui', None)
        if gui is None:
            return None
        try:
            import tkinter as tk
            if not isinstance(gui, tk.Misc):
                return None
            return gui.winfo_toplevel()
        except Exception:
            return None

    def _later(self, fn):
        """画面のスレッドで、今の処理が終わった後に fn を呼ぶ（キャンセル時の postProcess 用）"""
        if fn is None:
            return
        root = self._tk_root()
        try:
            if root is not None:
                root.after_idle(fn)
                return
        except Exception:
            pass
        fn()

    def start(self, ser, postProcess=None):
        """
        Start ボタンで呼ばれる（画面のスレッド）。設定画面を出して、選んだ設定で開始する。
        - PCME 0.2.0 の command_service.start は、この関数が戻った後に状態を「実行中」にする。
          そのため、キャンセル時の postProcess（ボタンを戻す処理）は after_idle で後から呼ぶ
        - 実行リストは start を通らず do を直接呼ぶので、画面は出ない（config.json の値で動く）
        """
        try:
            ok = self._prepare_settings()
        except Exception:
            import traceback
            traceback.print_exc()
            print("[Error] 設定画面でエラーが出たため、開始しませんでした。")
            ok = False
        if not ok:
            print("[System] 開始をキャンセルしました。")
            self._later(postProcess)
            return None
        return super().start(ser, postProcess)

    def _prepare_settings(self):
        """設定を決めて反映する。開始してよければ True、キャンセルなら False"""
        cfg = load_config_file()
        root = self._tk_root()
        if not cfg['show_settings_ui'] or root is None or not _is_main_thread():
            if cfg['show_settings_ui'] and root is None:
                print("[System] 設定画面を出せない画面（Web ブラウザ版など）なので、config.json の値で開始します。")
            self.apply_config(cfg)
            return True

        result = _SettingsDialog(root, cfg).show()
        if result is None:
            return False
        new_cfg, save = result
        if save:
            try:
                save_config_file(new_cfg)
                print(f"[System] 設定を保存しました: {CONFIG_FILE_ABS}")
            except Exception as e:
                print(f"[Warning] config.json に保存できませんでした（この回は画面の値で動きます）: {e}")
        self.apply_config(new_cfg)
        return True

    # =========================================================================
    # メイン処理
    # =========================================================================
    def do(self):
        # --- 開始処理 ---
        self.start_time = datetime.now()
        LOOP_COUNT = self.max_loop
        count = 0

        self.print_with_clock(f"【M次元ラッシュ厳選】開始 (v{VERSION})", force=True)
        self.print_with_clock(f"モード: {self.get_mode_text()}", force=True)
        self.print_with_clock(f"設定: {self.get_settings_text()}, 最大 {LOOP_COUNT} 回", force=True)

        # --- メインループ ---
        while self.checkIfAlive() and count < LOOP_COUNT:
            count += 1

            # ------------------------------------------
            # Type 1: ホロエレベーター往復
            # ------------------------------------------
            if self.move_mode == 0:
                self.print_with_clock(f"【{count}回目】Type1: エレベーター往復")
                self.press(Button.A, wait=0.2)
                self.wait(self.wait_time)

                self.press(Direction.UP, self.elevator_move_time, 0.4)
                self.press(Direction.DOWN, self.elevator_move_time, 0.4)

                self.press(Button.A, wait=0.2)
                self.wait(self.wait_time)

            # ------------------------------------------
            # Type 2: ホロエレベーター移動のみ
            # ------------------------------------------
            elif self.move_mode == 1:
                self.print_with_clock(f"【{count}回目】Type2: エレベーター移動のみ")
                self.press(Button.A, wait=0.2)
                self.wait(self.wait_time)

            # ------------------------------------------
            # Type 3: シャトルラン (上下移動)
            # ------------------------------------------
            elif self.move_mode == 2:
                self.print_with_clock(f"【{count}回目】Type3: シャトルラン")
                remaining_time = max(0, self.duration - self.dash_delay)

                for direction in (Direction.UP, Direction.DOWN):
                    self.hold(direction)
                    if self.use_dash:
                        self.wait(self.dash_delay)
                        self.press(Button.B, duration=0.05, wait=0)
                        self.wait(remaining_time)
                    else:
                        self.wait(self.duration)
                    self.holdEnd(direction)
                    self.wait(self.shuttle_turn_wait)

            # ------------------------------------------
            # Type 4: Fastpass (高速移動)
            # ------------------------------------------
            elif self.move_mode == 3:
                self.print_with_clock(f"【{count}回目】Type4: Fastpass")

                # 初回のみYボタンを実行
                if self.fastpass_first_y and count == 1:
                    self.print_with_clock("初回動作: Yボタン押下")
                    self.press(Button.Y, 0.2, 0.4)

                self.press(Button.PLUS, 0.2, 0.5)
                self.press(Button.A, 0.2, 0.4)
                self.press(Button.A, 0.2, 0.6)

                self.wait(self.fastpass_wait)

        # --- 終了処理 ---
        self.finish_sequence(count, LOOP_COUNT)

    # モード表示用テキスト
    def get_mode_text(self):
        for num, label, desc in MODES:
            if num == self.move_mode:
                return f"{label} ({desc})"
        return "不明"

    def get_settings_text(self):
        if self.move_mode == 0:
            return f"待機={self.wait_time}s, 上下移動={self.elevator_move_time}s"
        if self.move_mode == 1:
            return f"待機={self.wait_time}s"
        if self.move_mode == 2:
            return (f"Dash={self.use_dash}, 片道={self.duration}s, B遅延={self.dash_delay}s, "
                    f"折り返し={self.shuttle_turn_wait}s")
        return f"FP待機={self.fastpass_wait}s, 初回Y={self.fastpass_first_y}"

    # --- ログ・時間管理 ---
    def finish_sequence(self, count, max_loop):
        elapsed_time = self.get_elapsed_time()
        self.print_with_clock(f"【完了】総実行回数: {count}/{max_loop}", force=True)
        self.print_with_clock(f"経過時間: {elapsed_time}", force=True)
        self.finish()

    def get_current_time(self):
        return datetime.now().strftime("%H:%M:%S")

    def get_elapsed_time(self):
        if self.start_time is None: return "00:00:00"
        elapsed = datetime.now() - self.start_time
        hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def print_with_clock(self, text, force=False):
        current = self.get_current_time()
        elapsed = self.get_elapsed_time()
        msg = f"[{current} | 経過 {elapsed}] {text}"

        if not force and text == getattr(self, '_last_msg', None):
            if time.time() - self.last_log_time < 1.0: return
        try:
            if hasattr(self, 'print_tbs'): self.print_tbs("a", msg + "\n")
            elif hasattr(self, 'print_tb'): self.print_tb("w" if force else "a", msg + "\n")
            else: print(msg)
        except: print(msg)
        self._last_msg = text
        self.last_log_time = time.time()


# =============================================================================
# 設定画面 (v3.2)
# =============================================================================
class _SettingsDialog:
    """
    開始前にモードと数値を選ぶ画面（Tk の Toplevel。Start を押した画面のスレッドで開き、閉じるまで待つ）。
    モードを選ぶと、そのモードの設定だけを表示する。ほかのモードの値は残ったまま保存される。
    show() の戻り値: (設定の辞書, config.json に保存するか)。キャンセルなら None
    """

    def __init__(self, root, cfg):
        import tkinter as tk
        from tkinter import ttk, messagebox
        self.tk, self.ttk, self.messagebox = tk, ttk, messagebox
        self.root = root
        self.cfg = normalize_config(cfg)
        self.result = None
        self._countdown = None
        self._after_id = None
        self.colors = self._theme_colors(root)

    @staticmethod
    def _theme_colors(root):
        """PCME 0.2.0 のテーマの色（使えない色名のとき・テーマが無いときは、決まった色）"""
        colors = {'bg': None, 'muted': '#707070', 'danger': '#c0392b'}
        try:
            import Theme
            for role in colors:
                try:
                    value = Theme.color(role)
                    root.winfo_rgb(value)      # この OS で使える色か（"SystemGrayText" などは Windows だけ）
                    colors[role] = value
                except Exception:
                    pass
        except Exception:
            pass
        return colors

    # ---------------------------------------------------------------- 部品
    def _note(self, parent, text, **pack):
        lbl = self.ttk.Label(parent, text=text, wraplength=480, foreground=self.colors['muted'])
        lbl.pack(anchor='w', **pack)
        return lbl

    def _row(self, parent, label):
        f = self.ttk.Frame(parent)
        f.pack(fill='x', pady=2)
        self.ttk.Label(f, text=label, width=22).pack(side='left')
        return f

    def _spin(self, parent, label, key, note=''):
        typ, lo, hi, inc = NUMERIC_RANGES[key]
        f = self._row(parent, label)
        fmt = '%.0f' if typ is int else ('%.2f' if inc < 0.1 else '%.1f')
        sb = self.ttk.Spinbox(f, from_=lo, to=hi, increment=inc, textvariable=self.v[key], width=10, format=fmt)
        sb.pack(side='left')
        self.v[key].set(str(self.cfg[key]))  # format で値が丸められないように入れ直す
        self.ttk.Label(f, text=note or f'（{lo}〜{hi}）', foreground=self.colors['muted']).pack(side='left', padx=6)
        return f

    # ---------------------------------------------------------------- 画面
    def show(self):
        tk, ttk = self.tk, self.ttk
        c = self.cfg
        win = tk.Toplevel(self.root)
        self.win = win
        win.title(f"ZA M次元ラッシュ v{VERSION}: 設定")
        win.transient(self.root)
        win.resizable(False, False)
        if self.colors['bg']:
            try:
                win.configure(bg=self.colors['bg'])
            except tk.TclError:
                pass

        body = ttk.Frame(win, padding=12)
        body.pack(fill='both', expand=True)

        # --- 変数（数値は文字列で持ち、開始時に確かめる）
        self.v = {key: tk.StringVar(value=str(c[key])) for key in NUMERIC_RANGES if key != 'move_mode'}
        self.v_mode = tk.IntVar(value=c['move_mode'])
        self.v_dash = tk.BooleanVar(value=c['use_dash'])
        self.v_first_y = tk.BooleanVar(value=c['fastpass_first_y'])
        self.v_show_ui = tk.BooleanVar(value=c['show_settings_ui'])
        self.v_save = tk.BooleanVar(value=True)

        # --- モード
        mf = ttk.LabelFrame(body, text='移動モード', padding=8)
        mf.pack(fill='x')
        for num, label, desc in MODES:
            ttk.Radiobutton(mf, text=f'{label}: {desc}', value=num, variable=self.v_mode,
                            command=self._update_mode).pack(anchor='w')

        # --- モードごとの設定（選んだモードの枠だけ表示）
        self.opt_box = ttk.LabelFrame(body, text='モードの設定', padding=8)
        self.opt_box.pack(fill='x', pady=(8, 0))
        self.mode_frames = {}

        f = ttk.Frame(self.opt_box)
        self._spin(f, 'エレベーター待機', 'wait_time', '秒（A を押した後の待ち時間）')
        self._spin(f, '上下に歩く時間', 'elevator_move_time', '秒（上・下それぞれ）')
        self.mode_frames[0] = f

        f = ttk.Frame(self.opt_box)
        self._spin(f, 'エレベーター待機', 'wait_time', '秒（A を押した後の待ち時間）')
        self.mode_frames[1] = f

        f = ttk.Frame(self.opt_box)
        self._spin(f, '片道の移動時間', 'duration', '秒')
        ttk.Checkbutton(f, text='B ダッシュを使う', variable=self.v_dash,
                        command=self._update_dash).pack(anchor='w', pady=2)
        self.dash_row = self._spin(f, '　B を押すまでの遅延', 'dash_delay', '秒（歩き出してから）')
        self._spin(f, '折り返しの待機', 'shuttle_turn_wait', '秒（上下を切り替える間）')
        self.mode_frames[2] = f

        f = ttk.Frame(self.opt_box)
        self._spin(f, 'Fastpass 後の待機', 'fastpass_wait', '秒（ロード完了まで）')
        ttk.Checkbutton(f, text='1回目だけ最初に Y を押す（マップ画面の初期化）',
                        variable=self.v_first_y).pack(anchor='w', pady=2)
        self.mode_frames[3] = f

        self._note(self.opt_box, '※ 別のモードの値も残り、まとめて保存されます。', side='bottom', pady=(6, 0))

        # --- 共通
        cf = ttk.LabelFrame(body, text='共通', padding=8)
        cf.pack(fill='x', pady=(8, 0))
        self._spin(cf, 'ループ回数の上限', 'max_loop', '回')

        # --- この画面
        uf = ttk.LabelFrame(body, text='この画面', padding=8)
        uf.pack(fill='x', pady=(8, 0))
        ttk.Checkbutton(uf, text='Start を押したときに、この画面を出す', variable=self.v_show_ui).pack(anchor='w')
        self._note(uf, '外した場合は、次から config.json の値ですぐに開始します。'
                       'もう一度出すには config.json の "show_settings_ui" を true にしてください。')
        self._spin(uf, '何もしなければ自動で開始', 'settings_ui_timeout_seconds', '秒（0 = 自動で開始しない）')

        # --- 下のボタン
        bottom = ttk.Frame(body)
        bottom.pack(fill='x', pady=(10, 0))
        ttk.Checkbutton(bottom, text='この設定を config.json に保存する', variable=self.v_save).pack(side='left')
        ttk.Button(bottom, text='キャンセル', command=self._cancel).pack(side='right', padx=3)
        ttk.Button(bottom, text='開始', command=self._ok).pack(side='right', padx=3)
        self.countdown_label = ttk.Label(body, text='', foreground=self.colors['muted'])
        self.countdown_label.pack(anchor='e', pady=(4, 0))

        win.protocol('WM_DELETE_WINDOW', self._cancel)
        win.bind('<Escape>', lambda e: self._cancel())
        # 何か操作したら、自動で開始するのをやめる
        for seq in ('<Button>', '<Key>', '<MouseWheel>'):
            win.bind(seq, self._stop_countdown, add='+')

        self._update_mode()
        self._update_dash()
        self._start_countdown()

        win.update_idletasks()
        try:
            x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - win.winfo_width()) // 2)
            y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - win.winfo_height()) // 3)
            win.geometry(f'+{x}+{y}')
        except tk.TclError:
            pass
        try:
            win.grab_set()
        except tk.TclError:
            pass
        win.focus_set()
        self.root.wait_window(win)
        return self.result

    # ---------------------------------------------------------------- 表示の切り替え
    def _update_mode(self):
        mode = self.v_mode.get()
        for f in self.mode_frames.values():
            f.pack_forget()
        self.mode_frames.get(mode, self.mode_frames[3]).pack(fill='x')
        for num, label, desc in MODES:
            if num == mode:
                self.opt_box.configure(text=f'{label} の設定（{desc}）')

    def _update_dash(self):
        state = '!disabled' if self.v_dash.get() else 'disabled'
        for w in self.dash_row.winfo_children():
            try:
                w.state([state])
            except Exception:
                pass

    # ---------------------------------------------------------------- 自動で開始
    def _start_countdown(self):
        try:
            sec = int(float(self.v['settings_ui_timeout_seconds'].get()))
        except ValueError:
            sec = 0
        if sec <= 0:
            return
        self._countdown = sec
        self._tick()

    def _tick(self):
        if self._countdown is None:
            return
        if self._countdown <= 0:
            self.countdown_label.configure(text='')
            self._countdown = None
            self._ok(auto=True)
            return
        self.countdown_label.configure(text=f'あと {self._countdown} 秒操作がなければ、この設定で開始します（何か操作すると止まります）')
        self._countdown -= 1
        self._after_id = self.win.after(1000, self._tick)

    def _stop_countdown(self, event=None):
        if self._countdown is None:
            return
        self._countdown = None
        if self._after_id is not None:
            try:
                self.win.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self.countdown_label.configure(text='')

    # ---------------------------------------------------------------- 決定
    LABELS = {
        'max_loop': 'ループ回数の上限', 'wait_time': 'エレベーター待機', 'elevator_move_time': '上下に歩く時間',
        'duration': '片道の移動時間', 'dash_delay': 'B を押すまでの遅延', 'shuttle_turn_wait': '折り返しの待機',
        'fastpass_wait': 'Fastpass 後の待機', 'settings_ui_timeout_seconds': '自動で開始するまでの秒数',
    }

    def collect(self):
        """画面の値を、config.json と同じ形の辞書にする（入力がおかしいときは ValueError）"""
        cfg = dict(self.cfg)
        cfg['move_mode'] = int(self.v_mode.get())
        for key, var in self.v.items():
            typ, lo, hi, _ = NUMERIC_RANGES[key]
            label = self.LABELS.get(key, key)
            text = str(var.get()).strip()
            try:
                value = float(text)
            except ValueError:
                raise ValueError(f'{label}: 数字を入れてください（今の値: {text!r}）')
            if typ is int:
                if value != int(value):
                    raise ValueError(f'{label}: 整数を入れてください')
                value = int(value)
            else:
                value = round(value, 3)
            if value < lo or value > hi:
                raise ValueError(f'{label}: {lo}〜{hi} の範囲で入れてください')
            cfg[key] = value
        cfg['use_dash'] = bool(self.v_dash.get())
        cfg['fastpass_first_y'] = bool(self.v_first_y.get())
        cfg['show_settings_ui'] = bool(self.v_show_ui.get())
        if cfg['move_mode'] == 2 and cfg['use_dash'] and cfg['dash_delay'] > cfg['duration']:
            raise ValueError('B を押すまでの遅延: 片道の移動時間より短くしてください')
        return cfg

    def _ok(self, auto=False):
        try:
            cfg = self.collect()
        except ValueError as e:
            if auto:
                print(f"[Warning] 設定画面: {e}（自動では開始しませんでした）")
            self.messagebox.showinfo('ZA M次元ラッシュ', str(e), parent=self.win)
            return
        if auto:
            print('[System] 設定画面で操作がなかったので、表示していた設定で開始します。')
        self.result = (cfg, bool(self.v_save.get()))
        self._close()

    def _cancel(self):
        self.result = None
        self._close()

    def _close(self):
        self._stop_countdown()
        try:
            self.win.grab_release()
        except Exception:
            pass
        self.win.destroy()


# NAME（文字列リテラル）と VERSION の書き忘れに気づけるようにする
if ZA_MDimensionRush.NAME != f"ZA_M_Dimension_Rush_v{VERSION}":
    print(f"[Warning] NAME ({ZA_MDimensionRush.NAME}) と VERSION ({VERSION}) が合っていません。両方を同じ版に書き換えてください。")
