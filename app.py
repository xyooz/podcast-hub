#!/usr/bin/env python3
"""
Podcast Hub - 播客聚合平台 API
Flask + SQLite + Peewee
"""

import os
import sys
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_compress import Compress
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache

from database import db, Podcast, Episode, Favorite, PlayHistory, init_db
from crawler import PodcastParser

# ============ Configuration ============
class Config:
    """Application configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'podcast-hub-2024')
    DEBUG = os.environ.get('ENV') == 'development'
    
    # Static file caching (7 days)
    SEND_FILE_MAX_AGE_DEFAULT = 86400
    
    # Gzip compression
    COMPRESS_MIN_SIZE = 500
    COMPRESS_LEVEL = 6
    
    # Rate limiting
    RATELIMIT_DEFAULT = "100 per hour"
    RATELIMIT_STORAGE_URL = "memory://"


# ============ App Initialization ============
app = Flask(__name__)
app.config.from_object(Config)

# Security headers
@app.after_request
def add_security_headers(response):
    """Add security headers"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# CORS
CORS(app)

# Compression
Compress(app)

# Rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[Config.RATELIMIT_DEFAULT],
    storage_uri=Config.RATELIMIT_STORAGE_URL,
    strategy="fixed-window"
)

# Cache configuration
cache = Cache(config={
    'CACHE_TYPE': 'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT': 300,  # 5 minutes
    'CACHE_THRESHOLD': 100,
})

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Server config
SERVER_HOST = os.environ.get('HOST', '0.0.0.0')
SERVER_PORT = int(os.environ.get('PORT', 5000))


# ============ Routes ============

@app.route("/")
def index():
    """Homepage"""
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), "templates"),
        "simple.html"
    )


@app.route("/static/<path:path>")
def static_files(path):
    """Static files"""
    static_folder = os.path.join(os.path.dirname(__file__), "static")
    return send_from_directory(static_folder, path)


# ---------- Podcasts ----------

@app.route("/api/podcast", methods=["GET"])
@limiter.limit("60 per minute")
@cache.cached(timeout=60, query_string=True)  # Cache for 60 seconds
def get_podcasts():
    """Get subscribed podcasts"""
    try:
        podcasts = (Podcast.select()
                   .where(Podcast.is_subscribed == True)
                   .order_by(Podcast.updated_at.desc()))
        
        return jsonify({
            "success": True,
            "data": [p.to_dict() for p in podcasts]
        })
    except Exception as e:
        logger.error(f"Failed to get podcasts: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route("/api/podcast", methods=["POST"])
@limiter.limit("10 per minute")
def add_podcast():
    """Add podcast via URL"""
    try:
        data = request.get_json(force=True, silent=True)
        if not data or "url" not in data:
            return jsonify({"success": False, "error": "Missing url parameter"}), 400
        
        url = data["url"]
        platform, info = PodcastParser.parse_url(url)
        logger.info(f"Parsed podcast: {info['title']}")
        
        # Check if exists
        existing = Podcast.select().where(Podcast.rss_url == info["rss_url"]).first()
        if existing:
            return jsonify({
                "success": True,
                "message": "Podcast already exists",
                "data": existing.to_dict()
            })
        
        # Create podcast
        podcast = Podcast.create(
            title=info["title"],
            description=info.get("description", ""),
            image_url=info.get("image_url", ""),
            rss_url=info["rss_url"],
            feed_url=info.get("feed_url", ""),
            author=info.get("author", ""),
            category=info.get("category", platform),
            episode_count=info.get("episode_count", 0),
        )
        
        # Sync episodes
        raw_episodes = info.get("_raw_episodes", [])
        _sync_episodes(podcast.id, info["rss_url"], raw_episodes)
        
        return jsonify({
            "success": True,
            "message": "Added successfully",
            "data": podcast.to_dict()
        })
        
    except ValueError as e:
        cache.clear()  # Clear cache on error

        logger.warning(f"Invalid input: {e}")
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to add podcast: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route("/api/podcast/<int:podcast_id>", methods=["DELETE"])
@limiter.limit("30 per minute")
def delete_podcast(podcast_id):
    """Delete podcast (unsubscribe)"""
    try:
        podcast = Podcast.get_by_id(podcast_id)
        
        # Delete related data
        Episode.delete().where(Episode.podcast == podcast_id).execute()
        Favorite.delete().where(Favorite.podcast == podcast_id).execute()
        PlayHistory.delete().where(PlayHistory.podcast == podcast_id).execute()
        
        podcast.delete_instance()
        
        return jsonify({"success": True, "message": "Unsubscribed"})
        
    except Podcast.DoesNotExist:
        cache.clear()  # Clear cache
        return jsonify({"success": False, "error": "Podcast not found"}), 404
    except Exception as e:
        logger.error(f"Failed to delete podcast: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route("/api/podcast/<int:podcast_id>/refresh", methods=["POST"])
@limiter.limit("5 per minute")
def refresh_podcast(podcast_id):
    """Refresh podcast episodes"""
    try:
        podcast = Podcast.get_by_id(podcast_id)
        
        raw_episodes = []
        
        # Xiaoyuzhou
        if "xiaoyuzhoufm.com" in podcast.feed_url:
            raw_episodes = PodcastParser._get_xiaoyuzhou_episodes(podcast.feed_url)
        # RSS feeds
        elif (podcast.category == "rss" or 
              "xyzfm" in podcast.rss_url or 
              "danliren" in podcast.rss_url):
            raw_episodes = PodcastParser._get_rss_episodes(podcast.rss_url)
        
        _sync_episodes(podcast_id, podcast.rss_url, raw_episodes)
        
        podcast = Podcast.get_by_id(podcast_id)
        return jsonify({
            "success": True,
            "message": "Refreshed",
            "episode_count": podcast.episode_count
        })
        
    except Podcast.DoesNotExist:
        cache.clear()  # Clear cache
        return jsonify({"success": False, "error": "Podcast not found"}), 404
    except Exception as e:
        logger.error(f"Failed to refresh podcast: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------- Episodes ----------

@app.route("/api/podcast/<int:podcast_id>/episodes", methods=["GET"])
@limiter.limit("60 per minute")
@cache.cached(timeout=120, query_string=True)  # Cache for 2 minutes
def get_episodes(podcast_id):
    """Get podcast episodes"""
    try:
        podcast = Podcast.get_by_id(podcast_id)
        episodes = (Episode.select()
                   .where(Episode.podcast == podcast_id)
                   .order_by(Episode.pub_date.desc()))
        
        return jsonify({
            "success": True,
            "data": [{
                "id": e.id,
                "podcast_id": e.podcast_id,
                "title": e.title[:200] if e.title else "",
                "audio_url": e.audio_url,
                "duration": e.duration,
                "duration_str": _format_duration(e.duration),
                "pub_date": e.pub_date.isoformat() if hasattr(e.pub_date, 'isoformat') else str(e.pub_date) if e.pub_date else None,
                "progress": e.progress or 0,
            } for e in episodes]
        })
        
    except Podcast.DoesNotExist:
        return jsonify({"success": False, "error": "Podcast not found"}), 404
    except Exception as e:
        logger.error(f"Failed to get episodes: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------- Playback ----------

@app.route("/api/play/<int:episode_id>", methods=["POST"])
@limiter.limit("100 per minute")
def play_episode(episode_id):
    """Record playback"""
    try:
        episode = Episode.get_by_id(episode_id)
        
        episode.is_played = True
        episode.save()
        
        PlayHistory.create(
            episode=episode_id,
            podcast=episode.podcast_id,
            progress=0,
            duration=episode.duration,
        )
        
        return jsonify({
            "success": True,
            "data": {
                "audio_url": episode.audio_url,
                "title": episode.title,
                "podcast_title": episode.podcast.get().title,
                "image_url": episode.podcast.get().image_url,
            }
        })
        
    except Episode.DoesNotExist:
        return jsonify({"success": False, "error": "Episode not found"}), 404
    except Exception as e:
        logger.error(f"Failed to play episode: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route("/api/history", methods=["GET"])
@limiter.limit("30 per minute")
@cache.cached(timeout=60, query_string=True)
def get_history():
    """Get playback history"""
    try:
        history = (PlayHistory.select()
                   .order_by(PlayHistory.played_at.desc())
                   .limit(50))
        
        return jsonify({
            "success": True,
            "data": [h.to_dict() for h in history]
        })
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route("/api/stats", methods=["GET"])
@limiter.limit("30 per minute")
@cache.cached(timeout=300, query_string=True)  # Cache for 5 minutes
def get_stats():
    """Get playback statistics"""
    try:
        from peewee import fn
        
        total_plays = PlayHistory.select().count()
        total_duration = PlayHistory.select(fn.SUM(PlayHistory.duration)).scalar() or 0
        
        # Podcast stats
        podcast_stats = []
        query = (PlayHistory
                 .select(PlayHistory.podcast_id, fn.COUNT(PlayHistory.id).alias('count'))
                 .where(PlayHistory.podcast_id.is_null(False))
                 .group_by(PlayHistory.podcast_id)
                 .order_by(fn.COUNT(PlayHistory.id).desc())
                 .limit(5))
        
        for h in query:
            try:
                podcast = Podcast.get_by_id(h.podcast_id)
                podcast_stats.append({
                    "id": h.podcast_id,
                    "title": podcast.title,
                    "count": h.count
                })
            except Podcast.DoesNotExist:
                continue
        
        hours = total_duration // 3600
        minutes = (total_duration % 3600) // 60
        
        return jsonify({
            "success": True,
            "data": {
                "total_plays": total_plays,
                "total_duration": total_duration,
                "total_duration_str": f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m",
                "podcasts": podcast_stats
            }
        })
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route("/api/progress/<int:episode_id>", methods=["POST"])
@limiter.limit("60 per minute")
def update_progress(episode_id):
    """Update playback progress"""
    try:
        data = request.get_json(silent=True) or {}
        progress = data.get("progress", 0)
        
        episode = Episode.get_by_id(episode_id)
        episode.progress = progress
        episode.played_at = datetime.now()
        episode.save()
        
        return jsonify({"success": True})
        
    except Episode.DoesNotExist:
        return jsonify({"success": False, "error": "Episode not found"}), 404
    except Exception as e:
        logger.error(f"Failed to update progress: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------- Favorites ----------

@app.route("/api/favorite", methods=["GET"])
@limiter.limit("30 per minute")
@cache.cached(timeout=120, query_string=True)
def get_favorites():
    """Get favorites"""
    try:
        favorites = (Favorite.select()
                    .join(Podcast)
                    .order_by(Favorite.created_at.desc())
                    .limit(100))
        
        return jsonify({
            "success": True,
            "data": [f.podcast.to_dict() for f in favorites]
        })
    except Exception as e:
        logger.error(f"Failed to get favorites: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route("/api/favorite/<int:podcast_id>", methods=["POST"])
@limiter.limit("30 per minute")
def add_favorite(podcast_id):
    """Add to favorites"""
    try:
        Podcast.get_by_id(podcast_id)
        
        existing = Favorite.select().where(Favorite.podcast == podcast_id).first()
        if existing:
            return jsonify({"success": True, "message": "Already favorited"})
        
        Favorite.create(podcast=podcast_id)
        return jsonify({"success": True, "message": "Added to favorites"})
        
    except Podcast.DoesNotExist:
        cache.clear()
        return jsonify({"success": False, "error": "Podcast not found"}), 404
    except Exception as e:
        logger.error(f"Failed to add favorite: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route("/api/favorite/<int:podcast_id>", methods=["DELETE"])
@limiter.limit("30 per minute")
def remove_favorite(podcast_id):
    """Remove from favorites"""
    try:
        favorite = Favorite.select().where(Favorite.podcast == podcast_id).first()
        if favorite:
            favorite.delete_instance()
            return jsonify({"success": True, "message": "Removed from favorites"})
        return jsonify({"success": False, "error": "Not favorited"}), 404
    except Exception as e:
        cache.clear()
        logger.error(f"Failed to remove favorite: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------- Health Check ----------

@app.route("/api/cache/clear", methods=["POST"])
@limiter.limit("10 per minute")
def clear_cache():
    """Clear all caches"""
    try:
        cache.clear()
        return jsonify({"success": True, "message": "Cache cleared"})
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/health")
def health_check():
    """Health check endpoint"""
    try:
        db.execute_sql("SELECT 1")
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "cache": "enabled"
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 503


# ============ Helper Functions ============

def _sync_episodes(podcast_id: int, rss_url: str, raw_episodes: list = None):
    """Sync podcast episodes"""
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
                pub_date = datetime.now()
                if entry.get("pub_date"):
                    try:
                        pub_date = datetime.fromisoformat(
                            entry["pub_date"].replace("Z", "+00:00").replace("+00:00", "")
                        )
                    except ValueError:
                        pub_date = datetime.now()
                
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


def _format_duration(seconds: int) -> str:
    """Format duration in seconds to HH:MM:SS or MM:SS"""
    if not seconds:
        return "00:00"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes >= 60:
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


# ============ Model Extensions ============

class PodcastMixin:
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "image_url": self.image_url,
            "rss_url": self.rss_url,
            "author": self.author,
            "category": self.category,
            "episode_count": self.episode_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_subscribed": self.is_subscribed,
        }


class EpisodeMixin:
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "audio_url": self.audio_url,
            "duration": self.duration,
            "duration_str": _format_duration(self.duration),
            "pub_date": self.pub_date.isoformat() if self.pub_date else None,
            "episode_num": self.episode_num,
            "is_played": self.is_played,
        }


class PlayHistoryMixin:
    def to_dict(self):
        return {
            "id": self.id,
            "episode_id": self.episode_id,
            "podcast_id": self.podcast_id,
            "title": self.episode.get().title if self.episode else "",
            "podcast_title": self.podcast.get().title if self.podcast else "",
            "played_at": self.played_at.isoformat() if self.played_at else None,
        }


# Bind methods
Podcast.to_dict = PodcastMixin.to_dict
Episode.to_dict = EpisodeMixin.to_dict
PlayHistory.to_dict = PlayHistoryMixin.to_dict


# ============ Cache Control ============

@app.after_request
def add_cache_control(response):
    """Cache control headers"""
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    elif request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=604800'
    return response


# ============ Application Entry Point ============

if __name__ == "__main__":
    # Initialize database
    db_file = os.path.join(os.path.dirname(__file__), "podcasts.db")
    if not os.path.exists(db_file):
        init_db()
    
    # Initialize cache
    cache.init_app(app)
    
    logger.info(f"Starting Podcast Hub on {SERVER_HOST}:{SERVER_PORT}")
    
    # Production mode check
    if os.environ.get('ENV') == 'production':
        logger.info("Running in production mode")
    
    app.run(
        host=SERVER_HOST,
        port=SERVER_PORT,
        debug=Config.DEBUG,
        threaded=True
    )
