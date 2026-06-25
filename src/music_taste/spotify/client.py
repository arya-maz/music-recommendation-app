import os

from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth


load_dotenv()


SPOTIFY_SCOPES = "user-top-read user-library-read user-read-recently-played"


def get_spotify_client() -> spotipy.Spotify:
    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
            scope=SPOTIFY_SCOPES,
            open_browser=True,
        )
    )