"""
YouTube Search Tool for video research.
Uses yt-dlp to search YouTube, extract metadata, and score videos.
Filters for shorts ONLY as requested by the user.
"""

import math
import logging
from typing import List, Dict, Any
import yt_dlp

logger = logging.getLogger(__name__)

def search_youtube_shorts(keyword: str, count: int = 10, exclude_ids: List[str] = None) -> List[Dict[str, Any]]:
    """
    Search for YouTube Shorts using yt-dlp.
    Appends '#shorts' to the query and filters by duration <= 60s.
    Scores results based on views and engagement.
    """
    if exclude_ids is None:
        exclude_ids = []

    # Target finding more than `count` initially to account for filtering/excludes
    search_count = count * 3
    search_query = f"ytsearch{search_count}:{keyword} #shorts"
    
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'extract_flat': True,
    }

    results = []
    
    logger.info(f"Searching YouTube Shorts for query: '{search_query}'")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(search_query, download=False)
            entries = info.get('entries', [])
            
            for entry in entries:
                if entry is None:
                    continue
                    
                vid_id = entry.get('id')
                if not vid_id or vid_id in exclude_ids:
                    continue
                    
                # Shorts filtering
                duration = entry.get('duration')
                # If duration is unknown, we might include or exclude it. 
                # Let's include if it's explicitly a short (url contains /shorts/) or duration is short
                url = entry.get('url', '')
                is_short_url = '/shorts/' in url
                
                if duration is not None and duration > 65:
                    if not is_short_url:
                        continue # Skip non-shorts
                
                # Basic info
                title = entry.get('title', '')
                view_count = entry.get('view_count', 0)
                
                # Score viral potential mainly based on view count for simplicity,
                # as extract_flat doesn't always provide full like_count/upload_date.
                score = _calculate_viral_score(view_count, duration)
                
                results.append({
                    "id": vid_id,
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={vid_id}",
                    "view_count": view_count,
                    "duration": duration,
                    "score": score
                })
                
        except Exception as e:
            logger.error(f"Error during YouTube search: {e}")
            
    # Sort by score descending
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # Return top N
    return results[:count]

def search_youtube_audio(keyword: str, count: int = 5) -> List[Dict[str, Any]]:
    """
    Search for YouTube videos specifically for background music.
    Appends 'background music no copyright' to the query.
    """
    search_query = f"ytsearch{count}:{keyword} background music no copyright"
    
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'extract_flat': True,
    }

    results = []
    
    logger.info(f"Searching YouTube Audio for query: '{search_query}'")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(search_query, download=False)
            entries = info.get('entries', [])
            
            for entry in entries:
                if entry is None:
                    continue
                    
                vid_id = entry.get('id')
                if not vid_id:
                    continue
                
                title = entry.get('title', '')
                duration = entry.get('duration')
                
                results.append({
                    "id": vid_id,
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={vid_id}",
                    "duration": duration
                })
                
        except Exception as e:
            logger.error(f"Error during YouTube audio search: {e}")
            
    return results

def _calculate_viral_score(view_count: int, duration: float) -> float:
    """Simple scoring heuristic for viral potential."""
    if not view_count:
        return 0.0
        
    score = math.log10(view_count) if view_count > 0 else 0
    
    # Bonus for shorts sweet spot (15-50s)
    if duration and 15 <= duration <= 50:
        score += 1.0
        
    return round(score, 2)
