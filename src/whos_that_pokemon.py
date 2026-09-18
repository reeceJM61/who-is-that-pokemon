"""
Who's That Pokémon?
--------------------
A silhouette guessing game using live sprite data from PokéAPI.

Requirements:
    pip install requests pillow

Run:
    python whos_that_pokemon.py

How it works:
    - Picks a random Pokémon (by national dex number) from a configurable range.
    - Downloads its official artwork/sprite from PokéAPI.
    - Converts the sprite into a solid black silhouette (alpha-preserved).
    - You type a guess; on correct guess (or "reveal") the true sprite is shown.
    - Score and streak are tracked across rounds.
"""

import io
import random
import tkinter as tk
from tkinter import messagebox

import requests
from PIL import Image, ImageTk

POKEAPI_SPECIES_URL = "https://pokeapi.co/api/v2/pokemon-species/{id}/"
POKEAPI_POKEMON_URL = "https://pokeapi.co/api/v2/pokemon/{id}/"

# Range of national dex numbers to pull from. 1-151 = Gen 1 only.
# Change to e.g. (1, 1025) for all currently known Pokémon.
DEX_RANGE = (1, 151)

SPRITE_DISPLAY_SIZE = (300, 300)


class PokemonRound:
    """Holds the data for a single round: id, name, and image bytes."""

    def __init__(self, dex_id: int, name: str, image_bytes: bytes):
        self.dex_id = dex_id
        self.name = name
        self.image_bytes = image_bytes


def fetch_random_pokemon() -> PokemonRound:
    """Fetch a random Pokémon's English name and official artwork bytes."""
    dex_id = random.randint(*DEX_RANGE)

    species_resp = requests.get(POKEAPI_SPECIES_URL.format(id=dex_id), timeout=10)
    species_resp.raise_for_status()
    species_data = species_resp.json()

    english_name = next(
        entry["name"]
        for entry in species_data["names"]
        if entry["language"]["name"] == "en"
    )

    pokemon_resp = requests.get(POKEAPI_POKEMON_URL.format(id=dex_id), timeout=10)
    pokemon_resp.raise_for_status()
    pokemon_data = pokemon_resp.json()

    artwork_url = pokemon_data["sprites"]["other"]["official-artwork"]["front_default"]
    if not artwork_url:
        artwork_url = pokemon_data["sprites"]["front_default"]

    image_resp = requests.get(artwork_url, timeout=10)
    image_resp.raise_for_status()

    return PokemonRound(dex_id, english_name, image_resp.content)


def make_silhouette(image_bytes: bytes) -> Image.Image:
    """Turn a sprite's non-transparent pixels solid black, keep alpha channel."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img = img.resize(SPRITE_DISPLAY_SIZE, Image.LANCZOS)

    r, g, b, a = img.split()
    black = Image.new("RGBA", img.size, (0, 0, 0, 255))
    black.putalpha(a)
    return black


def make_reveal(image_bytes: bytes) -> Image.Image:
    """Return the true-color sprite at display size."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    return img.resize(SPRITE_DISPLAY_SIZE, Image.LANCZOS)


class GuessingGameApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Who's That Pokémon?")
        self.root.geometry("420x560")
        self.root.resizable(False, False)

        self.score = 0
        self.streak = 0
        self.current_round: PokemonRound | None = None
        self.revealed = False
        self.tk_image = None  # keep a reference so it isn't garbage collected

        self._build_ui()
        self.next_round()

    def _build_ui(self):
        title = tk.Label(self.root, text="Who's That Pokémon?", font=("Helvetica", 20, "bold"))
        title.pack(pady=(15, 5))

        self.score_label = tk.Label(self.root, text="Score: 0   Streak: 0", font=("Helvetica", 12))
        self.score_label.pack()

        self.status_label = tk.Label(self.root, text="Loading...", font=("Helvetica", 11), fg="gray")
        self.status_label.pack(pady=(2, 10))

        self.image_label = tk.Label(self.root, bg="#f0f0f0", width=300, height=300)
        self.image_label.pack()

        entry_frame = tk.Frame(self.root)
        entry_frame.pack(pady=15)

        self.guess_entry = tk.Entry(entry_frame, font=("Helvetica", 13), width=20)
        self.guess_entry.pack(side=tk.LEFT, padx=5)
        self.guess_entry.bind("<Return>", lambda event: self.submit_guess())

        submit_btn = tk.Button(entry_frame, text="Guess", command=self.submit_guess)
        submit_btn.pack(side=tk.LEFT)

        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=5)

        reveal_btn = tk.Button(button_frame, text="Reveal", command=self.reveal_answer)
        reveal_btn.pack(side=tk.LEFT, padx=5)

        next_btn = tk.Button(button_frame, text="Next Pokémon", command=self.next_round)
        next_btn.pack(side=tk.LEFT, padx=5)

        self.feedback_label = tk.Label(self.root, text="", font=("Helvetica", 13, "bold"))
        self.feedback_label.pack(pady=10)

    def _set_image(self, pil_image: Image.Image):
        self.tk_image = ImageTk.PhotoImage(pil_image)
        self.image_label.config(image=self.tk_image)

    def next_round(self):
        self.status_label.config(text="Loading...")
        self.feedback_label.config(text="")
        self.guess_entry.delete(0, tk.END)
        self.revealed = False
        self.root.update_idletasks()

        try:
            self.current_round = fetch_random_pokemon()
        except requests.RequestException as exc:
            messagebox.showerror("Network error", f"Couldn't fetch a Pokémon:\n{exc}")
            self.status_label.config(text="Failed to load. Try Next Pokémon again.")
            return

        silhouette = make_silhouette(self.current_round.image_bytes)
        self._set_image(silhouette)
        self.status_label.config(text="Type your guess and press Enter")
        self.guess_entry.focus_set()

    def submit_guess(self):
        if self.current_round is None or self.revealed:
            return

        guess = self.guess_entry.get().strip().lower()
        answer = self.current_round.name.lower()

        if not guess:
            return

        if guess == answer:
            self.score += 1
            self.streak += 1
            self.feedback_label.config(text=f"Correct! It's {self.current_round.name}!", fg="green")
            self._reveal_image()
        else:
            self.streak = 0
            self.feedback_label.config(text="Nope, try again!", fg="red")

        self._update_score_label()

    def reveal_answer(self):
        if self.current_round is None or self.revealed:
            return
        self.streak = 0
        self.feedback_label.config(text=f"It was {self.current_round.name}!", fg="blue")
        self._reveal_image()
        self._update_score_label()

    def _reveal_image(self):
        self.revealed = True
        reveal_img = make_reveal(self.current_round.image_bytes)
        self._set_image(reveal_img)
        self.status_label.config(text="Click 'Next Pokémon' to continue")

    def _update_score_label(self):
        self.score_label.config(text=f"Score: {self.score}   Streak: {self.streak}")


def main():
    root = tk.Tk()
    GuessingGameApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()