import os

from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth


load_dotenv()


SPOTIFY_SCOPES = "user-top-read user-library-read user-read-recently-played"


def get_spotify_oauth(*, cache_handler=None, open_browser: bool = False) -> SpotifyOAuth:
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
        scope=SPOTIFY_SCOPES,
        cache_handler=cache_handler,
        open_browser=open_browser,
    )


def get_spotify_client(*, cache_handler=None, open_browser: bool = True) -> spotipy.Spotify:
    return spotipy.Spotify(
        auth_manager=get_spotify_oauth(cache_handler=cache_handler, open_browser=open_browser)
    )
