#!/usr/bin/env python3
"""
黑白棋（Reversi/Othello）游戏
支持：人机对战 / 双人对战 × 简单/中等/困难 × 单局/三局两胜/五局三胜
"""

import tkinter as tk
from tkinter import font as tkfont
import copy
import math
import os
from enum import Enum
from typing import List, Tuple, Optional

# PIL 用于加载 JPG 背景图（可选）
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ============================================================================
#  棋盘逻辑
# ============================================================================

class Stone(Enum):
    EMPTY = 0
    BLACK = 1
    WHITE = 2

    def opponent(self):
        if self == Stone.BLACK:
            return Stone.WHITE
        elif self == Stone.WHITE:
            return Stone.BLACK
        return Stone.EMPTY


# 八个方向
DIRECTIONS = [(-1, -1), (-1, 0), (-1, 1),
              (0, -1),           (0, 1),
              (1, -1),  (1, 0),  (1, 1)]

# 位置权重表（用于中等/困难模式评估）
WEIGHT_BOARD = [
    [100, -20,  10,   5,   5,  10, -20, 100],
    [-20, -50,  -2,  -2,  -2,  -2, -50, -20],
    [ 10,  -2,   1,   1,   1,   1,  -2,  10],
    [  5,  -2,   1,   0,   0,   1,  -2,   5],
    [  5,  -2,   1,   0,   0,   1,  -2,   5],
    [ 10,  -2,   1,   1,   1,   1,  -2,  10],
    [-20, -50,  -2,  -2,  -2,  -2, -50, -20],
    [100, -20,  10,   5,   5,  10, -20, 100],
]


class OthelloGame:
    """黑白棋核心逻辑"""

    def __init__(self):
        self.board: List[List[Stone]] = []
        self.current_player = Stone.BLACK
        self.reset()

    def reset(self):
        """初始化棋盘：中央 4 枚棋子"""
        self.board = [[Stone.EMPTY for _ in range(8)] for _ in range(8)]
        self.board[3][3] = Stone.WHITE
        self.board[3][4] = Stone.BLACK
        self.board[4][3] = Stone.BLACK
        self.board[4][4] = Stone.WHITE
        self.current_player = Stone.BLACK

    def copy(self) -> 'OthelloGame':
        g = OthelloGame()
        g.board = [row[:] for row in self.board]
        g.current_player = self.current_player
        return g

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < 8 and 0 <= c < 8

    def is_valid_move(self, r: int, c: int, player: Stone) -> bool:
        """检查 (r,c) 是否是 player 的合法落子"""
        if not self.in_bounds(r, c) or self.board[r][c] != Stone.EMPTY:
            return False
        opponent = player.opponent()
        for dr, dc in DIRECTIONS:
            nr, nc = r + dr, c + dc
            has_opponent_between = False
            while self.in_bounds(nr, nc) and self.board[nr][nc] == opponent:
                nr += dr
                nc += dc
                has_opponent_between = True
            if has_opponent_between and self.in_bounds(nr, nc) and self.board[nr][nc] == player:
                return True
        return False

    def get_valid_moves(self, player: Stone) -> List[Tuple[int, int]]:
        """返回 player 的所有合法落子坐标"""
        moves = []
        for r in range(8):
            for c in range(8):
                if self.is_valid_move(r, c, player):
                    moves.append((r, c))
        return moves

    def flipped_stones(self, r: int, c: int, player: Stone) -> List[Tuple[int, int]]:
        """模拟在 (r,c) 落子后翻转的棋子列表"""
        flipped = []
        opponent = player.opponent()
        for dr, dc in DIRECTIONS:
            nr, nc = r + dr, c + dc
            line = []
            while self.in_bounds(nr, nc) and self.board[nr][nc] == opponent:
                line.append((nr, nc))
                nr += dr
                nc += dc
            if line and self.in_bounds(nr, nc) and self.board[nr][nc] == player:
                flipped.extend(line)
        return flipped

    def apply_move(self, r: int, c: int):
        """在 (r,c) 落子并翻转，然后切换玩家"""
        player = self.current_player
        self.board[r][c] = player
        for fr, fc in self.flipped_stones(r, c, player):
            self.board[fr][fc] = player
        self.current_player = self.current_player.opponent()

    def count(self) -> dict:
        """统计各色棋子数"""
        black = sum(row.count(Stone.BLACK) for row in self.board)
        white = sum(row.count(Stone.WHITE) for row in self.board)
        return {Stone.BLACK: black, Stone.WHITE: white, 'empty': 64 - black - white}

    def is_game_over(self) -> bool:
        """双方都无法落子时游戏结束"""
        if self.get_valid_moves(Stone.BLACK):
            return False
        if self.get_valid_moves(Stone.WHITE):
            return False
        return True

    def winner(self) -> Optional[Stone]:
        """返回胜方，平局返回 None"""
        cnt = self.count()
        if cnt[Stone.BLACK] > cnt[Stone.WHITE]:
            return Stone.BLACK
        elif cnt[Stone.WHITE] > cnt[Stone.BLACK]:
            return Stone.WHITE
        return None


# ============================================================================
#  AI 策略
# ============================================================================

class AIPlayer:
    """AI 基类"""

    def choose_move(self, game: OthelloGame, player: Stone) -> Optional[Tuple[int, int]]:
        moves = game.get_valid_moves(player)
        return moves[0] if moves else None


class GreedyAI(AIPlayer):
    """简单：贪心策略 -- 选择翻转棋子数最多的位置"""

    def choose_move(self, game: OthelloGame, player: Stone) -> Optional[Tuple[int, int]]:
        moves = game.get_valid_moves(player)
        if not moves:
            return None
        best_move = moves[0]
        best_flips = -1
        for r, c in moves:
            flips = len(game.flipped_stones(r, c, player))
            if flips > best_flips:
                best_flips = flips
                best_move = (r, c)
        return best_move


class HeuristicAI(AIPlayer):
    """中等：启发式策略 -- 综合考虑位置权重、行动力、稳定子"""

    @staticmethod
    def evaluate(game: OthelloGame, player: Stone) -> float:
        """对 player 的局势评估"""
        opponent = player.opponent()
        score = 0.0

        # 位置权重
        for r in range(8):
            for c in range(8):
                if game.board[r][c] == player:
                    score += WEIGHT_BOARD[r][c]
                elif game.board[r][c] == opponent:
                    score -= WEIGHT_BOARD[r][c]

        # 行动力（合法走法数）
        my_moves = len(game.get_valid_moves(player))
        op_moves = len(game.get_valid_moves(opponent))
        score += (my_moves - op_moves) * 5.0

        # 角落
        corners = [(0, 0), (0, 7), (7, 0), (7, 7)]
        for r, c in corners:
            if game.board[r][c] == player:
                score += 50
            elif game.board[r][c] == opponent:
                score -= 50

        return score

    def choose_move(self, game: OthelloGame, player: Stone) -> Optional[Tuple[int, int]]:
        moves = game.get_valid_moves(player)
        if not moves:
            return None

        best_move = moves[0]
        best_score = -float('inf')
        for r, c in moves:
            sim = game.copy()
            sim.board[r][c] = player
            for fr, fc in sim.flipped_stones(r, c, player):
                sim.board[fr][fc] = player
            # 考虑对手能获得的最好局面
            op_moves = sim.get_valid_moves(player.opponent())
            if op_moves:
                worst_for_us = float('inf')
                for opr, opc in op_moves:
                    op_sim = sim.copy()
                    op_sim.board[opr][opc] = player.opponent()
                    for fr, fc in op_sim.flipped_stones(opr, opc, player.opponent()):
                        op_sim.board[fr][fc] = player.opponent()
                    worst_for_us = min(worst_for_us, self.evaluate(op_sim, player))
                score = worst_for_us
            else:
                score = self.evaluate(sim, player)

            if score > best_score:
                best_score = score
                best_move = (r, c)

        return best_move


class MinimaxAI(AIPlayer):
    """困难：带 Alpha-Beta 剪枝的极大极小搜索"""

    MAX_DEPTH = 5

    @staticmethod
    def evaluate(game: OthelloGame, player: Stone) -> float:
        """与中等策略共用静态评估（棋局末期可改为棋子数差值）"""
        cnt = game.count()
        total = cnt[Stone.BLACK] + cnt[Stone.WHITE]
        if total > 54:  # 终局阶段直接数子
            return cnt[player] - cnt[player.opponent()]
        return HeuristicAI.evaluate(game, player)

    def minimax(self, game: OthelloGame, depth: int, alpha: float, beta: float,
                maximizing: bool, player: Stone) -> float:
        if depth == 0 or game.is_game_over():
            return self.evaluate(game, player)

        current = player if maximizing else player.opponent()
        moves = game.get_valid_moves(current)

        if not moves:
            # 无合法走法，跳过回合
            return self.minimax(game, depth - 1, alpha, beta, not maximizing, player)

        if maximizing:
            max_eval = -float('inf')
            for r, c in moves:
                sim = game.copy()
                sim.apply_move(r, c)
                val = self.minimax(sim, depth - 1, alpha, beta, False, player)
                max_eval = max(max_eval, val)
                alpha = max(alpha, val)
                if beta <= alpha:
                    break
            return max_eval
        else:
            min_eval = float('inf')
            for r, c in moves:
                sim = game.copy()
                sim.apply_move(r, c)
                val = self.minimax(sim, depth - 1, alpha, beta, True, player)
                min_eval = min(min_eval, val)
                beta = min(beta, val)
                if beta <= alpha:
                    break
            return min_eval

    def choose_move(self, game: OthelloGame, player: Stone) -> Optional[Tuple[int, int]]:
        moves = game.get_valid_moves(player)
        if not moves:
            return None

        best_move = moves[0]
        best_score = -float('inf')
        alpha = -float('inf')
        beta = float('inf')

        # 按翻转数预排序加速剪枝
        moves_sorted = sorted(moves, key=lambda m: len(game.flipped_stones(m[0], m[1], player)),
                              reverse=True)

        for r, c in moves_sorted:
            sim = game.copy()
            sim.apply_move(r, c)
            val = self.minimax(sim, self.MAX_DEPTH - 1, alpha, beta, False, player)
            if val > best_score:
                best_score = val
                best_move = (r, c)
            alpha = max(alpha, val)

        return best_move


# ============================================================================
#  GUI 主程序
# ============================================================================

# ── 暖色调色板 ──
COLOR_BG = '#3e2723'           # 深暖棕背景
COLOR_BOARD = '#c49a3c'        # 暖金棋盘面
COLOR_BOARD_DARK = '#b8902c'   # 棋盘深格（交替纹理）
COLOR_BOARD_LIGHT = '#d0a84c'  # 棋盘浅格（交替纹理）
COLOR_LINE = '#5d3a1a'         # 深木色网格线
COLOR_BLACK_STONE = '#1a1a1a'  # 黑子
COLOR_WHITE_STONE = '#faf0dc'  # 暖奶油白子
COLOR_HIGHLIGHT = '#e8a840'    # 暖金高亮
COLOR_LAST_MOVE = '#ff6d3a'    # 暖珊瑚色上一步标记
COLOR_VALID_HINT = '#ffb347'   # 暖琥珀色合法走法提示
COLOR_TEXT = '#f5e6cc'         # 暖奶油色文字
COLOR_TITLE = '#ffa726'        # 暖橙金标题
COLOR_INFO_BG = '#2c1a0e'      # 深暖棕信息栏
COLOR_FRAME_OUTER = '#2a1506'  # 外框深棕色
COLOR_FRAME_MID = '#4e342e'    # 中框暖棕色
COLOR_FRAME_INNER = '#6d4c41'  # 内框浅棕
COLOR_SHADOW = '#1a0e06'       # 棋子阴影色

# ── 像素风格字体 ──
FONT_FAMILY = 'Courier'        # 等宽像素风格（跨平台可用）

# ── 布局常量 ──
BOARD_GRID = 560               # 棋盘网格像素
BOARD_MARGIN = 48              # 棋盘四周留白（装饰+坐标+边框）
CELL_SIZE = BOARD_GRID // 8    # 每格 70px
CANVAS_SIZE = BOARD_GRID + BOARD_MARGIN * 2  # 656
WINDOW_W = 1280
WINDOW_H = 900

# ── 背景图片路径 ──
BG_IMAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'othello_bg.jpg')


class OthelloApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title('黑白棋 Othello')
        self.root.geometry(f'{WINDOW_W}x{WINDOW_H}')
        self.root.configure(bg=COLOR_BG)
        self.root.resizable(False, False)

        # 游戏状态
        self.game = OthelloGame()
        self.game_mode: str = ''          # 'pvp' | 'pve'
        self.difficulty: str = ''         # 'easy' | 'medium' | 'hard'
        self.match_format: str = ''       # 'best1' | 'best3' | 'best5'
        self.wins_needed: int = 1
        self.ai_player: Optional[AIPlayer] = None

        # 赛制状态
        self.scores = {Stone.BLACK: 0, Stone.WHITE: 0}
        self.games_played = 0
        self.current_match_over = False

        # 用户选择
        self.human_side = Stone.BLACK     # PvE 模式下人类执黑

        # 上一步落子位置（用于高亮）
        self.last_move: Optional[Tuple[int, int]] = None

        # GUI 元素引用
        self.canvas: Optional[tk.Canvas] = None
        self.info_frame: Optional[tk.Frame] = None
        self._overlay_active: bool = False  # 结果覆盖层是否显示中

        self.show_menu()

    # ------------------------------------------------------------------
    #  菜单 / 导航
    # ------------------------------------------------------------------

    def clear_window(self):
        """清除所有控件，但保留背景图标签"""
        bg = getattr(self, '_bg_label', None)
        for w in self.root.winfo_children():
            if bg is not None and w is bg:
                continue  # 跳过背景标签
            w.destroy()

    def _make_btn(self, text, bg_color, command, width=24):
        """统一样式的按钮工厂（创建在 self.canvas 上）"""
        return tk.Button(self.canvas, text=text,
                         font=tkfont.Font(family=FONT_FAMILY, size=14, weight='bold'),
                         bg=bg_color, fg='white', activebackground=bg_color,
                         activeforeground='white', bd=0, padx=20, pady=10,
                         width=width, cursor='hand2', command=command)

    def _canvas_menu_header(self, title, subtitle=None):
        """在 Canvas 上绘制菜单标题（无背景矩形，文字直接浮在背景图上）"""
        cx = WINDOW_W // 2
        y = 80
        self.canvas.create_text(cx, y, text=title,
                                font=tkfont.Font(family=FONT_FAMILY, size=26, weight='bold'),
                                fill=COLOR_TITLE, tags='menu')
        y += 40
        self.canvas.create_line(cx - 150, y, cx + 150, y,
                                fill=COLOR_TITLE, width=2, tags='menu')
        y += 20
        if subtitle:
            self.canvas.create_text(cx, y, text=subtitle,
                                    font=tkfont.Font(family=FONT_FAMILY, size=12),
                                    fill=COLOR_TEXT, tags='menu')
            y += 32
        return y + 8  # 返回下一个元素的 y 坐标

    def _make_back_btn(self):
        """统一样式的返回按钮（创建在 self.canvas 上）"""
        return tk.Button(self.canvas, text='<< 返回菜单',
                         font=tkfont.Font(family=FONT_FAMILY, size=12, weight='bold'),
                         bg='#6d4c41', fg='white', activebackground='#8d6e63',
                         activeforeground='white', bd=0, padx=16, pady=8,
                         cursor='hand2', command=self.show_menu)

    def show_menu(self):
        self.clear_window()
        self.root.geometry(f'{WINDOW_W}x{WINDOW_H}')

        # ── 全窗口 Canvas ──
        self.canvas = tk.Canvas(self.root, width=WINDOW_W, height=WINDOW_H,
                                bg=COLOR_BG, highlightthickness=0)
        self.canvas.pack()
        self._draw_canvas_bg()

        y = self._canvas_menu_header('::  O T H E L L O  ::', '黑白棋 - 多阶梯 - 多赛制')

        cx = WINDOW_W // 2
        for text, color, cmd in [
            ('[VS]  人 机 对 战', '#c75b39', self.select_pve),
            ('[2P]  双 人 对 战', '#8d6e63', self.select_pvp),
            ('[X]  退 出 游 戏', '#a04030', self.root.quit),
        ]:
            btn = self._make_btn(text, color, cmd)
            self.canvas.create_window(cx, y, window=btn)
            y += 56

    # ------ 模式选择 ------

    def select_pve(self):
        self.game_mode = 'pve'
        self.choose_side()

    def select_pvp(self):
        self.game_mode = 'pvp'
        self.difficulty = ''       # PvP 不使用 AI，无需难度
        self.ai_player = None
        self.choose_format()       # 跳过难度选择，直接进入赛制

    def choose_side(self):
        self.clear_window()
        self.root.geometry(f'{WINDOW_W}x{WINDOW_H}')

        # ── 全窗口 Canvas ──
        self.canvas = tk.Canvas(self.root, width=WINDOW_W, height=WINDOW_H,
                                bg=COLOR_BG, highlightthickness=0)
        self.canvas.pack()
        self._draw_canvas_bg()

        y = self._canvas_menu_header('选择棋子颜色', '黑子先行 - 白子后手')

        cx = WINDOW_W // 2
        # 黑子按钮
        btn_black = self._make_btn('[B]  执 黑 先 行', COLOR_BLACK_STONE,
                                    lambda: self.set_human_side(Stone.BLACK))
        self.canvas.create_window(cx, y, window=btn_black)
        y += 56

        # 白子按钮（深色文字）
        btn_white = tk.Button(self.canvas, text='[W]  执 白 后 手',
                              font=tkfont.Font(family=FONT_FAMILY, size=14, weight='bold'),
                              bg=COLOR_WHITE_STONE, fg='#3e2723',
                              activebackground=COLOR_WHITE_STONE,
                              activeforeground='#3e2723', bd=0, padx=20, pady=10,
                              width=24, cursor='hand2',
                              command=lambda: self.set_human_side(Stone.WHITE))
        self.canvas.create_window(cx, y, window=btn_white)
        y += 56

        btn_back = self._make_back_btn()
        self.canvas.create_window(cx, y, window=btn_back)

    def set_human_side(self, side: Stone):
        self.human_side = side
        self.choose_difficulty()

    # ------ 难度选择 ------

    def choose_difficulty(self):
        self.clear_window()
        self.root.geometry(f'{WINDOW_W}x{WINDOW_H}')

        # ── 全窗口 Canvas ──
        self.canvas = tk.Canvas(self.root, width=WINDOW_W, height=WINDOW_H,
                                bg=COLOR_BG, highlightthickness=0)
        self.canvas.pack()
        self._draw_canvas_bg()

        y = self._canvas_menu_header('选择 AI 难度', '贪心策略 - 启发式 - 极大极小')

        cx = WINDOW_W // 2
        for text, color, diff in [
            ('[E]  简 单  -  贪 心 策 略', '#6b8e5a', 'easy'),
            ('[M]  中 等  -  启 发 式 策 略', '#d4843a', 'medium'),
            ('[H]  困 难  -  极 大 极 小 算 法', '#b5452c', 'hard'),
        ]:
            btn = self._make_btn(text, color, lambda d=diff: self.set_difficulty(d))
            self.canvas.create_window(cx, y, window=btn)
            y += 56

        btn_back = self._make_back_btn()
        self.canvas.create_window(cx, y, window=btn_back)

    def set_difficulty(self, difficulty: str):
        self.difficulty = difficulty
        # 初始化 AI
        if self.game_mode == 'pve':
            if difficulty == 'easy':
                self.ai_player = GreedyAI()
            elif difficulty == 'medium':
                self.ai_player = HeuristicAI()
            else:
                self.ai_player = MinimaxAI()
        else:
            self.ai_player = None
        self.choose_format()

    # ------ 赛制选择 ------

    def choose_format(self):
        self.clear_window()
        self.root.geometry(f'{WINDOW_W}x{WINDOW_H}')

        # ── 全窗口 Canvas ──
        self.canvas = tk.Canvas(self.root, width=WINDOW_W, height=WINDOW_H,
                                bg=COLOR_BG, highlightthickness=0)
        self.canvas.pack()
        self._draw_canvas_bg()

        y = self._canvas_menu_header('选择赛制', '单局决胜 - 三局两胜 - 五局三胜')

        cx = WINDOW_W // 2
        for text, fmt, wins in [
            ('[1]  单 局 胜 负', 'best1', 1),
            ('[3]  三 局 两 胜', 'best3', 2),
            ('[5]  五 局 三 胜', 'best5', 3),
        ]:
            btn = self._make_btn(text, '#5d4037', lambda f=fmt, w=wins: self.set_format(f, w))
            self.canvas.create_window(cx, y, window=btn)
            y += 56

        btn_back = self._make_back_btn()
        self.canvas.create_window(cx, y, window=btn_back)

    def set_format(self, fmt: str, wins: int):
        self.match_format = fmt
        self.wins_needed = wins
        self.start_match()

    # ------------------------------------------------------------------
    #  赛程管理
    # ------------------------------------------------------------------

    def start_match(self):
        """开始整个赛程（可能包含多局）"""
        self.scores = {Stone.BLACK: 0, Stone.WHITE: 0}
        self.games_played = 0
        self.current_match_over = False
        self.start_new_game()

    def start_new_game(self):
        """开始新的一局"""
        self.game.reset()
        self.current_match_over = False
        self.last_move = None   # 重置高亮
        self.games_played += 1
        self.build_game_ui()
        self.after_move_check()

    def end_game(self, winner: Optional[Stone]):
        """一局结束"""
        if winner is not None:
            self.scores[winner] += 1
        self.current_match_over = True

        # 检查赛程是否结束
        if self.scores[Stone.BLACK] >= self.wins_needed:
            self.finish_match(Stone.BLACK)
        elif self.scores[Stone.WHITE] >= self.wins_needed:
            self.finish_match(Stone.WHITE)
        else:
            # 还有下一局
            self.ask_next_game()

    def ask_next_game(self):
        cnt = self.game.count()
        self._show_result_overlay(
            title='本局结束',
            lines=[
                f'黑子 {cnt[Stone.BLACK]}  :  {cnt[Stone.WHITE]}  白子',
                f'当前比分 — 黑方 {self.scores[Stone.BLACK]}  :  {self.scores[Stone.WHITE]}  白方',
                f'（赛制：{self._format_label()}）',
            ],
            buttons=[
                ('下一局', '#c75b39', self.start_new_game),
                ('返回菜单', '#6d4c41', self.show_menu),
            ],
        )

    def finish_match(self, winner: Stone):
        """整个赛程结束"""
        name = '黑方' if winner == Stone.BLACK else '白方'
        total = self.games_played
        self._show_result_overlay(
            title='赛程结束！',
            lines=[
                f'获胜方：{name}',
                f'最终比分 — 黑方 {self.scores[Stone.BLACK]}  :  {self.scores[Stone.WHITE]}  白方',
                f'总对局数：{total}    赛制：{self._format_label()}',
            ],
            buttons=[
                ('返回菜单', '#c75b39', self.show_menu),
            ],
        )

    def _format_label(self) -> str:
        return {'best1': '单局胜负', 'best3': '三局两胜', 'best5': '五局三胜'}.get(
            self.match_format, '未知')

    # ------------------------------------------------------------------
    #  结果覆盖层（替代 messagebox 弹窗）
    # ------------------------------------------------------------------

    def _show_result_overlay(self, title: str, lines: list, buttons: list):
        """在游戏 Canvas 上显示结果覆盖层。
        lines: 消息行列表（每行一条 create_text）
        buttons: [(文字, 颜色, 回调)] 列表
        """
        c = self.canvas
        if c is None:
            return

        self._overlay_active = True
        c.delete('overlay')

        # ── 暗色遮罩 ──
        c.create_rectangle(0, 0, WINDOW_W, WINDOW_H,
                           fill='#0a0a0a', stipple='gray25', outline='', tags='overlay')

        # ── 对话框背景 ──
        dw, dh = 520, max(240, 140 + len(lines) * 22)
        dx = (WINDOW_W - dw) // 2
        dy = (WINDOW_H - dh) // 2
        c.create_rectangle(dx, dy, dx + dw, dy + dh,
                           fill=COLOR_INFO_BG, outline=COLOR_TITLE,
                           width=3, tags='overlay')

        # ── 标题 ──
        c.create_text(WINDOW_W // 2, dy + 38, text=title,
                      font=tkfont.Font(family=FONT_FAMILY, size=18, weight='bold'),
                      fill=COLOR_TITLE, tags='overlay')

        # ── 分隔线 ──
        c.create_line(dx + 60, dy + 62, dx + dw - 60, dy + 62,
                      fill=COLOR_TITLE, width=1, tags='overlay')

        # ── 消息行 ──
        y = dy + 90
        for line in lines:
            c.create_text(WINDOW_W // 2, y, text=line,
                          font=tkfont.Font(family=FONT_FAMILY, size=12),
                          fill=COLOR_TEXT, tags='overlay')
            y += 24

        # ── 按钮 ──
        y = dy + dh - 50
        btn_w = 130
        spacing = btn_w + 20
        total_w = len(buttons) * btn_w + (len(buttons) - 1) * 20
        start_x = WINDOW_W // 2 - total_w // 2 + btn_w // 2

        for i, (text, color, cmd) in enumerate(buttons):
            bx = start_x + i * spacing
            btn = tk.Button(c, text=text,
                            font=tkfont.Font(family=FONT_FAMILY, size=12, weight='bold'),
                            bg=color, fg='white', activebackground=color,
                            activeforeground='white', bd=0, padx=16, pady=8,
                            cursor='hand2',
                            command=lambda cb=cmd: self._dismiss_overlay(cb))
            c.create_window(bx, y, window=btn, tags='overlay')

    def _dismiss_overlay(self, callback=None):
        """关闭覆盖层，可选的执行回调"""
        self._overlay_active = False
        if self.canvas:
            self.canvas.delete('overlay')
        if callback:
            callback()

    # ------------------------------------------------------------------
    #  游戏界面
    # ------------------------------------------------------------------

    def after_move_check(self):
        """落子后检查：跳过无合法走法的玩家、检查游戏结束"""
        if self.current_match_over:
            return

        current = self.game.current_player

        # 检查当前玩家是否有合法走法
        if not self.game.get_valid_moves(current):
            # 跳过该玩家
            self.flash_message(f'{self._stone_name(current)}无合法走法，跳过回合', 1500)
            self.game.current_player = current.opponent()
            # 再检查对手
            if not self.game.get_valid_moves(self.game.current_player):
                # 双方都无法走，游戏结束
                self.flash_message('双方均无合法走法，本局结束', 2000)
                self.root.after(2200, lambda: self.end_game(self.game.winner()))
                return
            self.root.after(100, self.update_board)
            self.root.after(150, self.after_move_check)
            return

        # 检查游戏是否已结束
        if self.game.is_game_over():
            self.update_board()
            self.root.after(500, lambda: self.end_game(self.game.winner()))
            return

        self.update_board()

        # 如果是 AI 回合，自动执行
        if self.game_mode == 'pve':
            ai_side = self.human_side.opponent()
            if self.game.current_player == ai_side and not self.current_match_over:
                self.root.after(400, self.ai_turn)

    def ai_turn(self):
        if self.current_match_over:
            return
        if self.ai_player is None:
            return
        move = self.ai_player.choose_move(self.game, self.game.current_player)
        if move:
            self.place_stone(*move)

    def place_stone(self, r: int, c: int):
        """执行落子"""
        if self.current_match_over:
            return

        player = self.game.current_player
        if not self.game.is_valid_move(r, c, player):
            return

        self.game.apply_move(r, c)
        self.last_move = (r, c)  # 记录上一步落子
        self.update_board()
        self.root.after(100, self.after_move_check)

    def flash_message(self, text: str, duration_ms: int):
        """在棋盘上方短暂显示消息"""
        if hasattr(self, '_flash_id') and self.canvas:
            self.canvas.itemconfig(self._flash_id, text=text)
        if hasattr(self, 'flash_label'):
            self.flash_label.config(text=text)
        self.root.after(duration_ms, lambda: self._clear_flash())

    def _clear_flash(self):
        if hasattr(self, '_flash_id') and self.canvas:
            self.canvas.itemconfig(self._flash_id, text='')
        if hasattr(self, 'flash_label'):
            self.flash_label.config(text='')

    def build_game_ui(self):
        """构建游戏主界面 - 全窗口画布 + 透明文字"""
        self.clear_window()
        self.root.geometry(f'{WINDOW_W}x{WINDOW_H}')

        # ── 全窗口画布 ──
        self.canvas = tk.Canvas(self.root, width=WINDOW_W, height=WINDOW_H,
                                bg=COLOR_BG, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind('<Button-1>', self.on_canvas_click)

        self.cell_size = CELL_SIZE
        self.board_ox = (WINDOW_W - BOARD_GRID) // 2   # 360
        self.board_oy = 80                               # 顶部留空

        # ── 背景图 / 渐变 ──
        self._draw_canvas_bg()

        # ── 棋盘 ──
        self.draw_board()

        # ── 顶部文字（透明，直接画在 canvas 上）──
        font_top = tkfont.Font(family=FONT_FAMILY, size=12, weight='bold')
        font_tag = tkfont.Font(family=FONT_FAMILY, size=10, weight='bold')
        font_score_sm = tkfont.Font(family=FONT_FAMILY, size=11, weight='bold')
        cx = WINDOW_W // 2
        top_y = 22

        # 标题
        self.canvas.create_text(cx, top_y, text=':: OTHELLO ::',
                                 fill=COLOR_TITLE, font=font_top, tags='ui_text')

        # 模式/难度/赛制 标签
        mode_text = 'PvE' if self.game_mode == 'pve' else 'PvP'
        diff_text = {'easy': 'EASY', 'medium': 'MED', 'hard': 'HARD'}.get(self.difficulty, '-')
        fmt_text = self._format_label()
        tag_y = top_y + 22
        tx = cx - 120
        for txt, clr in [(mode_text, '#ffcc80'), (diff_text, '#ffab40'), (fmt_text, '#efebe9')]:
            self.canvas.create_text(tx, tag_y, text=txt, fill=clr,
                                     font=font_tag, tags='ui_text')
            tx += 80
            self.canvas.create_text(tx, tag_y, text='|', fill=COLOR_TITLE,
                                     font=font_tag, tags='ui_text')
            tx += 20

        # 快速比分（右上）
        qx = WINDOW_W - 40
        self._quick_score_id = self.canvas.create_text(
            qx, top_y, text='', fill=COLOR_TITLE, font=font_score_sm,
            anchor='ne', tags='ui_text')

        # 闪烁消息
        self._flash_id = self.canvas.create_text(
            cx, tag_y + 24, text='', fill='#ffab40',
            font=tkfont.Font(family=FONT_FAMILY, size=10, weight='bold'), tags='ui_text')

        # ── 底部信息文字（透明，canvas 绘制）──
        info_y = self.board_oy + BOARD_GRID + 40  # board bottom + gap

        # 装饰线
        ly = info_y
        self.canvas.create_line(cx - 200, ly, cx + 200, ly,
                                 fill=COLOR_TITLE, width=2, tags='ui_text')

        # 大号比分
        score_y = ly + 36
        font_big = tkfont.Font(family=FONT_FAMILY, size=32, weight='bold')
        self._black_score_id = self.canvas.create_text(
            cx - 70, score_y, text='2', fill='#cccccc', font=font_big, tags='ui_text')
        self.canvas.create_text(cx, score_y, text=':', fill=COLOR_TITLE,
                                 font=font_big, tags='ui_text')
        self._white_score_id = self.canvas.create_text(
            cx + 70, score_y, text='2', fill='#faf0dc', font=font_big, tags='ui_text')

        # 回合指示器（Canvas 圆点）
        turn_y = score_y + 42
        self._turn_dot_id = self.canvas.create_oval(
            cx - 80, turn_y - 8, cx - 64, turn_y + 8,
            fill=COLOR_BLACK_STONE, outline='', tags='ui_text')
        self._turn_text_id = self.canvas.create_text(
            cx - 20, turn_y, text='Black',
            fill=COLOR_TEXT, font=tkfont.Font(family=FONT_FAMILY, size=14, weight='bold'),
            anchor='w', tags='ui_text')

        # 赛程比分
        match_y = turn_y + 24
        self._match_score_id = self.canvas.create_text(
            cx + 60, match_y, text='',
            fill=COLOR_TITLE, font=tkfont.Font(family=FONT_FAMILY, size=10, weight='bold'),
            anchor='w', tags='ui_text')

        # ── 按钮（浮在 canvas 上方）──
        btn_frame = tk.Frame(self.root, bg=COLOR_BG)
        btn_frame.place(relx=0.5, y=match_y + 36, anchor='n')
        btn_font = tkfont.Font(family=FONT_FAMILY, size=10, weight='bold')

        tk.Button(btn_frame, text='[*] RESTART', font=btn_font,
                  bg='#c75b39', fg='white', width=12,
                  bd=0, padx=10, pady=5, activebackground='#e85d3a',
                  command=self.restart_game).pack(side='left', padx=6)

        tk.Button(btn_frame, text='[H] MENU', font=btn_font,
                  bg='#6d4c41', fg='white', width=12,
                  bd=0, padx=10, pady=5, activebackground='#8d6e63',
                  command=self.show_menu).pack(side='left', padx=6)

        # ── 闪信 label（备用）──
        self.flash_label = tk.Label(self.root, text='',
                                     font=tkfont.Font(family=FONT_FAMILY, size=10, weight='bold'),
                                     fg='#ffab40', bg=COLOR_BG)
        self.flash_label.place(relx=0.5, y=tag_y + 24, anchor='n')

        self.update_board()

    def _set_window_background(self):
        """确保窗口有背景（JPG 或渐变）。已存在则跳过加载，仅确保置底。"""
        # 已加载过 JPG 背景 → 只需确保它在最底层
        if hasattr(self, '_bg_label') and self._bg_label is not None:
            self._bg_label.lower()
            return

        import sys

        if HAS_PIL and os.path.isfile(BG_IMAGE_PATH):
            try:
                img = Image.open(BG_IMAGE_PATH)
                img = img.resize((WINDOW_W, WINDOW_H), Image.LANCZOS)
                self._bg_image_tk = ImageTk.PhotoImage(img)
                self._bg_label = tk.Label(self.root, image=self._bg_image_tk, bg=COLOR_BG)
                self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)
                self._bg_label.lower()
                return
            except Exception as e:
                print(f'[BG] Failed to load JPG: {e}')

        if not HAS_PIL:
            print(f'[BG] PIL not installed. Run: "{sys.executable}" -m pip install Pillow')

    def _draw_canvas_bg(self):
        """在全窗口 Canvas 上绘制背景：优先 JPG，回退到渐变"""
        c = self.canvas
        if c is None:
            return
        c.delete('bg')

        # 尝试加载 JPG
        if HAS_PIL and os.path.isfile(BG_IMAGE_PATH):
            try:
                img = Image.open(BG_IMAGE_PATH)
                img = img.resize((WINDOW_W, WINDOW_H), Image.LANCZOS)
                self._bg_image_tk = ImageTk.PhotoImage(img)
                c.create_image(0, 0, anchor='nw', image=self._bg_image_tk, tags='bg')
                return
            except Exception:
                pass

        # 回退：径向渐变（全窗口）
        steps = 100
        cw, ch = WINDOW_W, WINDOW_H
        ccx, ccy = cw // 2, ch // 2
        max_r = int((cw ** 2 + ch ** 2) ** 0.5 / 2) + 30

        for i in range(steps, -1, -1):
            t = i / steps
            r = int(max_r * t)
            rc = int(0x3e + (0x6b - 0x3e) * (1 - t))
            gc = int(0x27 + (0x8a - 0x27) * (1 - t))
            bc = int(0x23 + (0x60 - 0x23) * (1 - t))
            color = f'#{rc:02x}{gc:02x}{bc:02x}'
            c.create_rectangle(ccx - r, ccy - r, ccx + r, ccy + r,
                               fill=color, outline='', tags='bg')

        # 棋盘区域四角装饰（仅对局页面有此属性）
        if not hasattr(self, 'board_ox') or not hasattr(self, 'board_oy'):
            return
        ox, oy = self.board_ox, self.board_oy
        b = BOARD_GRID
        for corner_x, corner_y, dx, dy in [
            (ox - 16, oy - 16, 1, 1), (ox + b + 16, oy - 16, -1, 1),
            (ox - 16, oy + b + 16, 1, -1), (ox + b + 16, oy + b + 16, -1, -1)]:
            for r, clr in [(12, '#5d4037'), (8, '#8d6e63')]:
                c.create_arc(corner_x - r, corner_y - r, corner_x + r, corner_y + r,
                             start=45 if dx > 0 else 135 if dy > 0 else 225,
                             extent=90, style='arc', outline=clr, width=2, tags='bg')
            c.create_oval(corner_x - 2, corner_y - 2, corner_x + 2, corner_y + 2,
                          fill=COLOR_TITLE, outline='', tags='bg')

    def restart_game(self):
        """放弃当前局并重新开始"""
        if not self.current_match_over:
            self._show_result_overlay(
                title='确认',
                lines=['确定要放弃当前对局重新开始吗？'],
                buttons=[
                    ('确定', '#c75b39', self.start_new_game),
                    ('取消', '#6d4c41', None),
                ],
            )
            return
        self.start_new_game()

    # ------------------------------------------------------------------
    #  棋盘绘制
    # ------------------------------------------------------------------

    def draw_board(self):
        """绘制精致棋盘：木框 + 交替纹理 + 网格 + 星位 + 坐标"""
        if self.canvas is None:
            return
        self.canvas.delete('grid')
        ox, oy = self.board_ox, self.board_oy
        b = BOARD_GRID

        # ── 外框阴影 ──
        self.canvas.create_rectangle(ox - 6, oy - 6, ox + b + 6, oy + b + 6,
                                      fill=COLOR_SHADOW, outline='', tags='grid')
        # ── 三层木框 ──
        for i, (w, clr) in enumerate([(5, COLOR_FRAME_OUTER), (4, COLOR_FRAME_MID), (3, COLOR_FRAME_INNER)]):
            self.canvas.create_rectangle(ox - 4 - i*2 - w, oy - 4 - i*2 - w,
                                          ox + b + 4 + i*2 + w, oy + b + 4 + i*2 + w,
                                          fill=clr, outline='', tags='grid')

        # ── 棋盘底色 ──
        self.canvas.create_rectangle(ox - 1, oy - 1, ox + b + 1, oy + b + 1,
                                      fill=COLOR_BOARD, outline=COLOR_LINE, width=2, tags='grid')

        # ── 交替格子纹理（木纹感）──
        for r in range(8):
            for c in range(8):
                if (r + c) % 2 == 0:
                    clr = COLOR_BOARD_LIGHT
                else:
                    clr = COLOR_BOARD_DARK
                x1 = ox + c * self.cell_size + 1
                y1 = oy + r * self.cell_size + 1
                x2 = ox + (c + 1) * self.cell_size
                y2 = oy + (r + 1) * self.cell_size
                self.canvas.create_rectangle(x1, y1, x2, y2,
                                              fill=clr, outline='', tags='grid')

        # ── 网格线 ──
        for i in range(9):
            x = ox + i * self.cell_size
            self.canvas.create_line(x, oy, x, oy + b, fill=COLOR_LINE, width=2, tags='grid')
            y = oy + i * self.cell_size
            self.canvas.create_line(ox, y, ox + b, y, fill=COLOR_LINE, width=2, tags='grid')

        # ── 星位标记 ──
        for r, c in [(2, 2), (2, 5), (5, 2), (5, 5)]:
            cx = ox + c * self.cell_size + self.cell_size // 2
            cy = oy + r * self.cell_size + self.cell_size // 2
            self.canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5,
                                     fill=COLOR_LINE, outline='', tags='grid')

        # ── 坐标标签 ──
        lbl_font = tkfont.Font(family=FONT_FAMILY, size=9, weight='bold')
        cols = 'ABCDEFGH'
        for i in range(8):
            # 上方字母
            cx = ox + i * self.cell_size + self.cell_size // 2
            self.canvas.create_text(cx, oy - 14, text=cols[i], fill=COLOR_TEXT,
                                     font=lbl_font, tags='grid')
            # 下方字母
            self.canvas.create_text(cx, oy + b + 14, text=cols[i], fill=COLOR_TEXT,
                                     font=lbl_font, tags='grid')
            # 左侧数字
            cy = oy + i * self.cell_size + self.cell_size // 2
            self.canvas.create_text(ox - 14, cy, text=str(i + 1), fill=COLOR_TEXT,
                                     font=lbl_font, tags='grid')
            # 右侧数字
            self.canvas.create_text(ox + b + 14, cy, text=str(i + 1), fill=COLOR_TEXT,
                                     font=lbl_font, tags='grid')

    def update_board(self):
        """刷新棋盘上的棋子与提示"""
        if self.canvas is None:
            return

        self.canvas.delete('stones')
        self.canvas.delete('hint')
        self.canvas.delete('last_move')

        ox, oy = self.board_ox, self.board_oy
        current = self.game.current_player
        is_ai_turn = (self.game_mode == 'pve' and current == self.human_side.opponent())

        # 绘制棋子
        for r in range(8):
            for c in range(8):
                stone = self.game.board[r][c]
                if stone != Stone.EMPTY:
                    self._draw_stone(r, c, stone)

        # 高亮上一步落子位置
        if self.last_move is not None:
            lr, lc = self.last_move
            x1 = ox + lc * self.cell_size + 2
            y1 = oy + lr * self.cell_size + 2
            x2 = ox + (lc + 1) * self.cell_size - 2
            y2 = oy + (lr + 1) * self.cell_size - 2
            self.canvas.create_rectangle(x1, y1, x2, y2,
                                         outline=COLOR_LAST_MOVE, width=3, tags='last_move')

        # 合法走法提示（小圆点 + 细圈）
        if not is_ai_turn and not self.current_match_over:
            moves = self.game.get_valid_moves(current)
            for r, c in moves:
                cx = ox + c * self.cell_size + self.cell_size // 2
                cy = oy + r * self.cell_size + self.cell_size // 2
                self.canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5,
                                         fill=COLOR_VALID_HINT, outline='', tags='hint')
                self.canvas.create_oval(cx - 8, cy - 8, cx + 8, cy + 8,
                                         fill='', outline=COLOR_VALID_HINT,
                                         width=2, tags='hint')

        # ── 更新 canvas 文字（透明，直接画在背景上）──
        cnt = self.game.count()
        current_name = 'Black' if current == Stone.BLACK else 'White'
        c = self.canvas

        # 大号比分
        if hasattr(self, '_black_score_id'):
            c.itemconfig(self._black_score_id, text=str(cnt[Stone.BLACK]))
        if hasattr(self, '_white_score_id'):
            c.itemconfig(self._white_score_id, text=str(cnt[Stone.WHITE]))

        # 回合指示圆点
        if hasattr(self, '_turn_dot_id'):
            dot_x = WINDOW_W // 2 - 80
            turn_y = self.board_oy + BOARD_GRID + 118
            dot_color = COLOR_BLACK_STONE if current == Stone.BLACK else COLOR_WHITE_STONE
            c.delete(self._turn_dot_id)
            self._turn_dot_id = c.create_oval(dot_x, turn_y - 8, dot_x + 16, turn_y + 8,
                                               fill=dot_color, outline='', tags='ui_text')
        # 回合文字
        if hasattr(self, '_turn_text_id'):
            c.itemconfig(self._turn_text_id, text=current_name,
                         fill='#cccccc' if current == Stone.BLACK else '#faf0dc')

        # 快速比分（右上）
        if hasattr(self, '_quick_score_id'):
            c.itemconfig(self._quick_score_id,
                         text=f'# {cnt[Stone.BLACK]} : {cnt[Stone.WHITE]} O')

        # 赛程比分
        if hasattr(self, '_match_score_id'):
            c.itemconfig(self._match_score_id, text=self._score_text())

    def _draw_stone(self, r: int, c: int, stone: Stone):
        """3D 立体棋子：径向渐变（10层）+ 阴影 + 高光斑"""
        ox, oy = self.board_ox, self.board_oy
        pad = 3
        x1 = ox + c * self.cell_size + pad
        y1 = oy + r * self.cell_size + pad
        x2 = ox + (c + 1) * self.cell_size - pad
        y2 = oy + (r + 1) * self.cell_size - pad

        cx = ox + c * self.cell_size + self.cell_size // 2
        cy = oy + r * self.cell_size + self.cell_size // 2
        r_max = (self.cell_size - pad * 2) // 2

        # ── 阴影 ──
        shadow_off = 3
        self.canvas.create_oval(x1 + shadow_off, y1 + shadow_off,
                                 x2 + shadow_off, y2 + shadow_off,
                                 fill=COLOR_SHADOW, outline='', tags='stones')

        if stone == Stone.BLACK:
            # 黑子径向渐变（外深 → 内亮灰）
            layers = [
                (1.00, '#0d0d0d'), (0.94, '#151515'), (0.87, '#1e1e1e'),
                (0.78, '#282828'), (0.67, '#333333'), (0.55, '#3f3f3f'),
                (0.42, '#4d4d4d'), (0.28, '#5c5c5c'), (0.15, '#6e6e6e'),
            ]
            for frac, clr in layers:
                rr = int(r_max * frac)
                self.canvas.create_oval(cx - rr, cy - rr, cx + rr, cy + rr,
                                         fill=clr, outline='', tags='stones')
            # 描边
            self.canvas.create_oval(x1, y1, x2, y2, fill='', outline='#222222',
                                     width=1, tags='stones')
            # 主高光斑
            self.canvas.create_oval(cx - 5, cy - 9, cx + 1, cy - 3,
                                     fill='#909090', outline='', tags='stones')
            # 次高光斑
            self.canvas.create_oval(cx - 3, cy - 11, cx - 1, cy - 8,
                                     fill='#aaaaaa', outline='', tags='stones')
        else:
            # 白子径向渐变（外暖灰 → 内纯白）
            layers = [
                (1.00, '#c4b896'), (0.94, '#cfc5a8'), (0.87, '#dbd2bb'),
                (0.78, '#e5ddca'), (0.67, '#ede6d6'), (0.55, '#f3eee2'),
                (0.42, '#f7f3ea'), (0.28, '#faf7f0'), (0.15, '#fdfbf7'),
            ]
            for frac, clr in layers:
                rr = int(r_max * frac)
                self.canvas.create_oval(cx - rr, cy - rr, cx + rr, cy + rr,
                                         fill=clr, outline='', tags='stones')
            # 描边
            self.canvas.create_oval(x1, y1, x2, y2, fill='', outline='#b8a880',
                                     width=1, tags='stones')
            # 主高光斑
            self.canvas.create_oval(cx - 4, cy - 8, cx + 1, cy - 3,
                                     fill='#ffffff', outline='', tags='stones')
            # 次高光斑
            self.canvas.create_oval(cx - 2, cy - 10, cx + 1, cy - 8,
                                     fill='#ffffff', outline='', tags='stones')

    def _stone_name(self, stone: Stone) -> str:
        return 'Black' if stone == Stone.BLACK else 'White'

    def _score_text(self) -> str:
        return (f'Match: # {self.scores[Stone.BLACK]} : {self.scores[Stone.WHITE]} O'
                f'  ({self._format_label()}, first to {self.wins_needed})')

    # ------------------------------------------------------------------
    #  交互
    # ------------------------------------------------------------------

    def on_canvas_click(self, event):
        """点击棋盘落子"""
        if self.current_match_over:
            return
        if self._overlay_active:
            return  # 覆盖层显示中，阻止棋盘点击

        current = self.game.current_player

        # 双人对战时人人可落；人机对战时只有人类回合可落
        if self.game_mode == 'pve':
            if current != self.human_side:
                return
        # else: PvP - 双方都是人类

        if not self.game.get_valid_moves(current):
            return

        col = (event.x - self.board_ox) // self.cell_size
        row = (event.y - self.board_oy) // self.cell_size

        if not self.game.in_bounds(row, col):
            return

        if not self.game.is_valid_move(row, col, current):
            return

        self.place_stone(row, col)


# ============================================================================
#  入口
# ============================================================================

if __name__ == '__main__':
    root = tk.Tk()
    app = OthelloApp(root)
    root.mainloop()
