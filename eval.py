import chess
import multiprocessing
from os import cpu_count

# Constants
INFINITY = 100000

# Material weights
material_weights = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
}


def evaluate_board(board: chess.Board) -> int:
    """Simplified evaluation function considering only material balance."""
    material = 0
    for piece in board.piece_map().values():
        value = material_weights.get(piece.piece_type, 0)
        if piece.color == chess.WHITE:
            material += value
        else:
            material -= value
    return material


def order_moves(board):
    """Simplified move ordering based on captures and promotions."""
    moves = list(board.legal_moves)

    def move_score(move):
        if move.promotion:
            return material_weights[chess.QUEEN]
        elif board.is_capture(move):
            return 1  # Assign a basic score to captures
        else:
            return 0

    moves.sort(key=move_score, reverse=True)
    return moves


def negamax(board, depth, alpha, beta, color):
    """Simplified Negamax search without advanced pruning techniques."""
    if depth == 0 or board.is_game_over():
        return color * evaluate_board(board)

    max_eval = -INFINITY
    for move in order_moves(board):
        board.push(move)
        eval = -negamax(board, depth - 1, -beta, -alpha, -color)
        board.pop()

        if eval > max_eval:
            max_eval = eval
        if max_eval > alpha:
            alpha = max_eval
        if alpha >= beta:
            break  # Alpha-beta cutoff

    return max_eval


def evaluate_move(args):
    move, board_fen, depth = args
    board = chess.Board(board_fen)
    board.push(move)
    eval = -negamax(board, depth - 1, -INFINITY, INFINITY, -1)
    return move, eval


def choose_best_move(board, max_depth):
    """Select the best move using multiprocessing to evaluate moves in parallel."""
    board_fen = board.fen()
    moves = order_moves(board)
    args = [(move, board_fen, max_depth) for move in moves]

    # Use all available CPU cores
    with multiprocessing.Pool(processes=cpu_count()) as pool:
        results = pool.map(evaluate_move, args)

    # Find the best move from the results
    best_move = None
    max_eval = -INFINITY
    for move, eval in results:
        if eval > max_eval:
            max_eval = eval
            best_move = move

    return best_move
