"""
Centralized constants for the Video Creator Platform.
"""

class LLMFeature:
    """Feature keys used for LLM routing."""
    LEADER_ANALYSIS = "leader_script_analysis"
    VIDEO_ORCHESTRATOR = "video_orchestrator"
    CHAT_ASSISTANT = "chat_assistant"
    
    # Add future features here
    # SEO_TITLES = "seo_titles"
    # IMAGE_ANALYSIS = "image_analysis"

    @classmethod
    def all(cls):
        return [cls.LEADER_ANALYSIS, cls.VIDEO_ORCHESTRATOR, cls.CHAT_ASSISTANT]
