// Temporary local recording override. Set to false after filming.
export const RECORDING_DEMO_ENABLED = false

// Metadata and artwork verified against the public Spotify album pages.
const recordingAlbums = [
  {
    "album_name": "SAVE ME",
    "artist_name": "Future",
    "release_year": "2019",
    "spotify_url": "https://open.spotify.com/album/65hRa80KDworqyE8242rLN",
    "album_image_url": "https://image-cdn-ak.spotifycdn.com/image/ab67616d0000b2735cd6070603a9f2e5dcb01d0c"
  },
  {
    "album_name": "That's The Spirit",
    "artist_name": "Bring Me The Horizon",
    "release_year": "2015",
    "spotify_url": "https://open.spotify.com/album/7FqHuAvmREiIwVXVpZ9ooP",
    "album_image_url": "https://image-cdn-ak.spotifycdn.com/image/ab67616d0000b27390b88187a9831d91f2438927"
  },
  {
    "album_name": "WOR$T GIRL IN AMERICA",
    "artist_name": "Slayyyter",
    "release_year": "2026",
    "spotify_url": "https://open.spotify.com/album/5siV9C6eK0NpAqER2FfCVA",
    "album_image_url": "https://image-cdn-fa.spotifycdn.com/image/ab67616d0000b2734c6a0c9499470002aa8ba96f"
  },
  {
    "album_name": "Sailing Soul(s)",
    "artist_name": "Jhené Aiko",
    "release_year": "2021",
    "spotify_url": "https://open.spotify.com/album/12EKtZXQtaicyObOUP16on",
    "album_image_url": "https://image-cdn-fa.spotifycdn.com/image/ab67616d0000b273abc1638020598957402c588d"
  },
  {
    "album_name": "BODIES X",
    "artist_name": "Thornhill",
    "release_year": "2025",
    "spotify_url": "https://open.spotify.com/album/4tl8pIcwtTJxPkywYfapNv",
    "album_image_url": "https://image-cdn-fa.spotifycdn.com/image/ab67616d0000b273b4511d0913d448a6c912406d"
  },
  {
    "album_name": "Minecraft - Volume Beta",
    "artist_name": "C418",
    "release_year": "2013",
    "spotify_url": "https://open.spotify.com/album/7CYDRyFCKtAYJBSpfovLyX",
    "album_image_url": "https://image-cdn-fa.spotifycdn.com/image/ab67616d0000b2734cf0b29eb06a92aa96acae64"
  },
  {
    "album_name": "The Cold Sun",
    "artist_name": "Loathe",
    "release_year": "2017",
    "spotify_url": "https://open.spotify.com/album/7gXMeoA54ckYqKUWKPIINJ",
    "album_image_url": "https://image-cdn-fa.spotifycdn.com/image/ab67616d0000b273394871f10feb6f0bffc26aab"
  },
  {
    "album_name": "Errorzone",
    "artist_name": "Vein.fm",
    "release_year": "2018",
    "spotify_url": "https://open.spotify.com/album/5KSIgVF5lx4JURkS50jRS9",
    "album_image_url": "https://image-cdn-fa.spotifycdn.com/image/ab67616d0000b273af89ca043be8fd7637b54df5"
  },
  {
    "album_name": "Magma",
    "artist_name": "Gojira",
    "release_year": "2016",
    "spotify_url": "https://open.spotify.com/album/7D7V6M05UIOTjLdqbwRX0w",
    "album_image_url": "https://image-cdn-ak.spotifycdn.com/image/ab67616d0000b273422c622517ea0bd7eda33e08"
  },
  {
    "album_name": "SWALLOW!",
    "artist_name": "Shygirl",
    "release_year": "2026",
    "spotify_url": "https://open.spotify.com/album/3dQzmmWFcow0z84wGW6RpD",
    "album_image_url": "https://image-cdn-fa.spotifycdn.com/image/ab67616d0000b273386f243bc8f40a2669ba7aa6"
  }
]

export function albumsForRecordingRoll(roll, authenticAlbums) {
  if (!import.meta.env.DEV || !RECORDING_DEMO_ENABLED) return authenticAlbums
  if (roll !== 1 && roll !== 2) return authenticAlbums
  return recordingAlbums.slice((roll - 1) * 5, roll * 5)
}
