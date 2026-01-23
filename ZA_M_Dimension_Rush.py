# -*- coding: utf-8 -*-
from Commands.PythonCommandBase import PythonCommand, ImageProcPythonCommand
from Commands.Keys import KeyPress, Hat, Button, Direction, Stick
from datetime import datetime
import time

class ZA_MDimensionRush(ImageProcPythonCommand):
    NAME = 'ZA_M_Dimension_Rush_v3.1'

    def __init__(self, camera, preview=None):
        super().__init__(camera, preview)
        # --- デフォルト設定 ---
        # 0: Type1 (エレベーター往復)
        # 1: Type2 (エレベーター移動のみ)
        # 2: Type3 (シャトルラン)
        # 3: Type4 (Fastpass)
        self.move_mode = 3      
        
        # Type1, 2用設定
        self.wait_time = 0.2    # ホロエレベーター待機時間

        # Type3 (シャトルラン)用設定
        self.use_dash = True    # Bダッシュを使用するか
        self.duration = 3.2     # 片道の移動時間
        self.dash_delay = 0.05  # Bボタンを押すまでの遅延

        # Type4 (Fastpass)用設定
        self.fastpass_wait = 2.2 # Fastpass使用後の待機時間
        self.fastpass_first_y = False # 追加: 初回Yボタン押下オプション

        # 内部変数
        self.start_time = None
        self._last_msg = None
        self.last_log_time = 0

    # GUIパラメータ設定
    def set_params(self, params: dict):
        self.move_mode = params.get('mode', 0)
        self.wait_time = params.get('wait', 3.0)
        
        # シャトルラン用
        self.use_dash = params.get('use_dash', True)
        self.duration = params.get('duration', 3.2)
        self.dash_delay = params.get('dash_delay', 0.05)

        # Fastpass用
        self.fastpass_wait = params.get('fastpass_wait', 2.5)
        self.fastpass_first_y = params.get('fastpass_first_y', False) # 追加: GUI設定値読み込み

    def do(self):
        # --- 開始処理 ---
        self.start_time = datetime.now()
        LOOP_COUNT = 9999
        count = 0

        self.print_with_clock("【M次元ラッシュ厳選】開始", force=True)
        self.print_with_clock(f"モード: {self.get_mode_text()}", force=True)

        # 設定値のログ表示
        if self.move_mode == 3:
            # 追加: Yボタン設定の状態をログ表示
            self.print_with_clock(f"設定: FP待機={self.fastpass_wait}s, 初回Y={self.fastpass_first_y}", force=True)
        elif self.move_mode == 2:
            self.print_with_clock(f"設定: Dash={self.use_dash}, 時間={self.duration}s", force=True)
        else:
            self.print_with_clock(f"設定: Wait={self.wait_time}s", force=True)

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
                
                self.press(Direction.UP, 2.5, 0.4)
                self.press(Direction.DOWN, 2.5, 0.4)
                
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

                # 上方向
                self.hold(Direction.UP)
                if self.use_dash:
                    self.wait(self.dash_delay)
                    self.press(Button.B, duration=0.05, wait=0)
                    self.wait(remaining_time)
                else:
                    self.wait(self.duration)
                self.holdEnd(Direction.UP)
                self.wait(0.5)

                # 下方向
                self.hold(Direction.DOWN)
                if self.use_dash:
                    self.wait(self.dash_delay)
                    self.press(Button.B, duration=0.05, wait=0)
                    self.wait(remaining_time)
                else:
                    self.wait(self.duration)
                self.holdEnd(Direction.DOWN)
                self.wait(0.5)

            # ------------------------------------------
            # Type 4: Fastpass (高速移動)
            # ------------------------------------------
            elif self.move_mode == 3:
                self.print_with_clock(f"【{count}回目】Type4: Fastpass")
                
                # --- 追加: 初回のみYボタンを実行 ---
                if self.fastpass_first_y and count == 1:
                    self.print_with_clock("初回動作: Yボタン押下")
                    self.press(Button.Y, 0.2, 0.4)
                # -----------------------------------

                self.press(Button.PLUS, 0.2, 0.5)
                #self.wait(0.5)
                self.press(Button.A, 0.2, 0.4)
                self.press(Button.A, 0.2, 0.6)
                
                # 環境変数で指定された時間待機
                self.wait(self.fastpass_wait)

        # --- 終了処理 ---
        self.finish_sequence(count, LOOP_COUNT)

    # モード表示用テキスト
    def get_mode_text(self):
        if self.move_mode == 0: return "Type1 (エレベーター往復)"
        if self.move_mode == 1: return "Type2 (エレベーターのみ)"
        if self.move_mode == 2: return "Type3 (シャトルラン)"
        if self.move_mode == 3: return "Type4 (Fastpass)"
        return "不明"

    # --- ログ・時間管理 ---
    def finish_sequence(self, count, max_loop):
        end_time_str = self.get_current_time()
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