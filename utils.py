"""Shared helpers for Podcast Hub."""

import logging
from datetime import datetime

from crawler import PodcastParser
from database import Podcast, Episode

logger = logging.getLogger(__name__)


def format_duration(seconds: int) -> str:
    """Format duration in seconds to HH:MM:SS or MM:SS."""
    if not seconds:
        return "00:00"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes >= 60:
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_pub_date(value) -> str | None:
    """Format a pub_date value as ISO string or fallback string."""
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def parse_entry_pub_date(value) -> datetime:
    """Parse a raw pub_date value into datetime."""
    if not value:
        return datetime.now()
    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00").replace("+00:00", "")
        )
    except ValueError:
        return datetime.now()


def sync_episodes(podcast_id: int, rss_url: str, raw_episodes: list | None = None) -> None:
    """Sync podcast episodes."""
    try:
        if raw_episodes:
            entries = raw_episodes
        else:
            entries = PodcastParser.get_episodes(rss_url)

        Podcast.update(episode_count=len(entries)).where(Podcast.id == podcast_id).execute()

        existing_urls = {ep.audio_url for ep in
                        Episode.select(Episode.audio_url).where(Episode.podcast == podcast_id)}

        for entry in entries:
            audio_url = entry["audio_url"]
            if audio_url not in existing_urls:
                pub_date = parse_entry_pub_date(entry.get("pub_date"))

                Episode.create(
                    podcast=podcast_id,
                    title=entry["title"],
                    description=entry.get("description", ""),
                    audio_url=audio_url,
                    duration=entry.get("duration", 0),
                    pub_date=pub_date,
                    episode_num=0
                )
                existing_urls.add(audio_url)

        logger.info(f"Synced episodes: podcast_id={podcast_id}, count={len(entries)}")

    except Exception as e:
        logger.error(f"Failed to sync episodes: {e}")
