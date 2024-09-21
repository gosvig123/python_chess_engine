import chess
import sys
import requests
import json
import os
import time
from eval import choose_best_move
from dotenv import load_dotenv

load_dotenv()


class ChessEngine:
    def __init__(self):
        self.board = chess.Board()

    def make_move(self, fen):
        self.board.set_fen(fen)
        return choose_best_move(self.board, 7)


class LichessBot:
    def __init__(self, api_token):
        self.api_token = api_token
        self.base_url = "https://lichess.org/api"
        self.engine = ChessEngine()
        self.username = None  # Will be set in get_account_info()

    def get_account_info(self):
        try:
            response = requests.get(
                f"{self.base_url}/account", headers=self._get_headers()
            )
            response.raise_for_status()
            account_info = response.json()
            self.username = account_info["id"]
            return account_info
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print(
                    "Error: Invalid API token. Please check your Lichess API token and try again."
                )
                sys.exit(1)
            else:
                print(f"An error occurred while getting account info: {e}")
                sys.exit(1)

    def accept_challenge(self, challenge_id):
        try:
            response = requests.post(
                f"{self.base_url}/challenge/{challenge_id}/accept",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            print(f"Accepted challenge {challenge_id}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to accept challenge {challenge_id}: {e}")

    def stream_incoming_events(self):
        print("Starting to stream incoming events")
        while True:
            try:
                response = requests.get(
                    f"{self.base_url}/stream/event",
                    headers=self._get_headers(),
                    stream=True,
                )
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        event = json.loads(line.decode("utf-8"))
                        print(f"Received event: {event}")
                        if event["type"] == "challenge":
                            self.accept_challenge(event["challenge"]["id"])
                        elif event["type"] == "gameStart":
                            self.handle_game_start(event["game"])
                    else:
                        print("Received empty line, continuing...")
            except requests.exceptions.RequestException as e:
                print(f"An error occurred while streaming events: {e}")
                print("Retrying in 10 seconds...")
                time.sleep(10)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                print("Continuing to next line...")

    def handle_game_start(self, game):
        game_id = game["id"]
        print(f"Game started: {game_id}")
        self.stream_game(game_id)

    def stream_game(self, game_id):
        try:
            response = requests.get(
                f"{self.base_url}/bot/game/stream/{game_id}",
                headers=self._get_headers(),
                stream=True,
            )
            response.raise_for_status()
            board = chess.Board()
            my_color = None
            for line in response.iter_lines():
                if line:
                    game_state = json.loads(line.decode("utf-8"))
                    print(f"Game state update: {game_state}")

                    if game_state.get("type") == "gameFull":
                        # Determine the bot's color
                        if game_state["white"]["id"] == self.username:
                            my_color = "white"
                        elif game_state["black"]["id"] == self.username:
                            my_color = "black"
                        else:
                            print("Error: Bot is neither white nor black in this game.")
                            return

                        # Initialize the board with the existing moves
                        moves = game_state["state"].get("moves", "")
                        if moves:
                            moves = moves.split()
                            for move in moves:
                                board.push_uci(move)

                        # Check if it's the bot's turn
                        if "isMyTurn" in game_state["state"]:
                            is_bot_turn = game_state["state"]["isMyTurn"]
                        else:
                            # Fallback to checking the board turn
                            is_bot_turn = (
                                board.turn == chess.WHITE and my_color == "white"
                            ) or (board.turn == chess.BLACK and my_color == "black")

                        if is_bot_turn:
                            self.make_move(game_id, board)
                    elif game_state.get("type") == "gameState":
                        # Apply new moves to the board
                        moves = game_state.get("moves", "")
                        if moves:
                            moves = moves.split()
                            board = chess.Board()  # Reset the board
                            for move in moves:
                                board.push_uci(move)

                        # Check if it's the bot's turn
                        if "isMyTurn" in game_state:
                            is_bot_turn = game_state["isMyTurn"]
                        else:
                            # Fallback to checking the board turn
                            is_bot_turn = (
                                board.turn == chess.WHITE and my_color == "white"
                            ) or (board.turn == chess.BLACK and my_color == "black")

                        if game_state["status"] == "started":
                            if is_bot_turn:
                                self.make_move(game_id, board)
                        else:
                            print(
                                f"Game {game_id} ended with status: {game_state['status']}"
                            )
                            return
                    else:
                        print(f"Unhandled game state type: {game_state.get('type')}")
                else:
                    print("Received empty line in game stream, continuing...")
        except requests.exceptions.RequestException as e:
            print(f"Error streaming game {game_id}: {e}")

    def make_move(self, game_id, board):
        try:
            # Get a valid move from the engine
            move = self.engine.make_move(board.fen())
            print(f"Suggested move: {move}")

            if move:
                move_response = requests.post(
                    f"{self.base_url}/bot/game/{game_id}/move/{move}",
                    headers=self._get_headers(),
                )
                move_response.raise_for_status()
                print(f"Move {move} successfully made in game {game_id}")
            else:
                print(f"No valid moves available for game {game_id}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to make move: {e}")
            print(
                f"Response content: {e.response.content if hasattr(e, 'response') else 'No response content'}"
            )

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }


def main():
    api_token = os.getenv("LICHESS_API_TOKEN")
    bot = LichessBot(api_token)

    try:
        account_info = bot.get_account_info()
        print("Account Info:", account_info)
        print("Listening for incoming games and challenges...")
        bot.stream_incoming_events()
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except requests.exceptions.RequestException as e:
        print(f"API or network error: {e}")
    print(
        "\nBot has stopped. If this was unexpected, please check the error messages above."
    )
    print(
        "If you encounter any bugs, please report them at: https://github.com/yourusername/python_chess_engine/issues"
    )


if __name__ == "__main__":
    main()
