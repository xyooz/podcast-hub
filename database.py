#!/usr/bin/env python3
"""
Podcast Hub Database Models
SQLite + Peewee ORM with optimizations
"""

from peewee import *
from datetime import datetime
import os

# Database path
DATABASE_PATH = os.environ.get('DATABASE_PATH', 'podcasts.db')

# Optimized SQLite configuration
db = SqliteDatabase(
    DATABASE_PATH,
    pragmas={
        'journal_mode': 'wal',          # Write-Ahead Logging for better concurrency
        'cache_size': -64000,           # 64MB cache
        'foreign_keys': 1,              # Enable foreign key constraints
        'synchronous': 'normal',        # Balance between safety and speed
        'mmap_size': 268435456,         # 256MB memory-mapped I/O
    }
)


class BaseModel(Model):
    class Meta:
        database = db


class Podcast(BaseModel):
    """Podcast model"""
    id = AutoField()
    title = CharField(max_length=200)
    description = TextField(null=True)
    image_url = CharField(max_length=500, null=True)
    rss_url = CharField(max_length=500)
    feed_url = CharField(max_length=500)
    author = CharField(max_length=100, null=True)
    category = CharField(max_length=50, null=True)
    episode_count = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    is_subscribed = BooleanField(default=True)
    
    class Meta:
        indexes = (
            (('rss_url',), False),      # Index for RSS URL lookups
            (('is_subscribed',), False), # Index for subscribed podcasts
        )


class Episode(BaseModel):
    """Episode model"""
    id = AutoField()
    podcast = ForeignKeyField(Podcast, backref='episodes', on_delete='CASCADE')
    title = CharField(max_length=300)
    description = TextField(null=True)
    audio_url = CharField(max_length=500)
    duration = IntegerField(default=0)
    pub_date = DateTimeField(null=True, index=True)  # Index for date sorting
    episode_num = IntegerField(null=True)
    created_at = DateTimeField(default=datetime.now)
    is_played = BooleanField(default=False)
    progress = IntegerField(default=0)
    played_at = DateTimeField(null=True)
    
    class Meta:
        indexes = (
            (('podcast', 'pub_date'), False),  # Composite index
            (('audio_url',), False),            # Index for audio URL lookups
        )


class Favorite(BaseModel):
    """Favorite podcast model"""
    id = AutoField()
    podcast = ForeignKeyField(Podcast, backref='favorites', on_delete='CASCADE')
    created_at = DateTimeField(default=datetime.now)
    
    class Meta:
        indexes = (
            (('podcast',), True),  # Unique index to prevent duplicates
        )


class PlayHistory(BaseModel):
    """Playback history model"""
    id = AutoField()
    episode = ForeignKeyField(Episode, backref='history', on_delete='CASCADE')
    podcast = ForeignKeyField(Podcast, backref='history', on_delete='CASCADE')
    played_at = DateTimeField(default=datetime.now, index=True)
    progress = IntegerField(default=0)
    duration = IntegerField(default=0)
    
    class Meta:
        indexes = (
            (('podcast', 'played_at'), False),  # For podcast history queries
        )


def init_db():
    """Initialize database with optimizations"""
    db.connect()
    
    # Enable WAL mode (already set in pragmas, but ensure it's applied)
    db.execute_sql('PRAGMA journal_mode=WAL')
    
    # Create tables
    db.create_tables([
        Podcast,
        Episode,
        Favorite,
        PlayHistory,
    ])
    
    # Create indexes
    _create_indexes()
    
    print("Database initialized with optimizations")
    db.close()


def _create_indexes():
    """Create additional indexes if not exists"""
    indexes = [
        'CREATE INDEX IF NOT EXISTS idx_episode_podcast_date ON episode(podcast_id, pub_date DESC)',
        'CREATE INDEX IF NOT EXISTS idx_podcast_subscribed ON podcast(is_subscribed)',
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_favorite_podcast ON favorite(podcast_id)',
        'CREATE INDEX IF NOT EXISTS idx_history_played_at ON playhistory(played_at DESC)',
    ]
    
    for sql in indexes:
        try:
            db.execute_sql(sql)
        except Exception as e:
            # Index might already exist
            pass


def optimize_db():
    """Database maintenance and optimization"""
    db.connect()
    
    # Analyze tables for query optimization
    db.execute_sql('ANALYZE')
    
    # Reindex all indexes
    db.execute_sql('REINDEX')
    
    # Vacuum to reclaim space
    db.execute_sql('VACUUM')
    
    print("Database optimized")
    db.close()


def get_db():
    """Get database connection"""
    if db.is_closed():
        db.connect()
    return db


if __name__ == "__main__":
    init_db()
    optimize_db()
