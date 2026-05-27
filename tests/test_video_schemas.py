"""
Unit tests for shared_core/video_schemas.py — VideoComposition and Healers.
"""

from shared_core.video_schemas import (
    extract_clean_sentences,
    Scene,
    VideoComposition,
    heal_video_composition
)

def test_extract_clean_sentences():
    script = (
        "Chào mừng các bạn đến với sản phẩm mới.\n"
        "Đây là một sản phẩm vô cùng tuyệt vời.\n"
        "Khám phá các tính năng vượt trội ngay.\n"
        "Hãy mua ngay hôm nay để nhận ưu đãi hấp dẫn!"
    )
    sentences = extract_clean_sentences(script, "Test Project")
    assert "Chào mừng các bạn đến với sản phẩm mới" in sentences
    assert "Đây là một sản phẩm vô cùng tuyệt vời" in sentences
    assert "Khám phá các tính năng vượt trội ngay" in sentences
    assert "Hãy mua ngay hôm nay để nhận ưu đãi hấp dẫn!" in sentences

def test_heal_video_composition_from_legacy_review():
    legacy_review = {
        "timeline_script": [
            {
                "segment": "seg_1",
                "time_range": [0, 4.5],
                "video_source": "1",
                "text_overlay": "Giới thiệu sản phẩm xịn sò",
                "visual_effects": ["zoom_in"],
                "highlight_words": ["sản phẩm"]
            }
        ],
        "assets": {
            "video_folders": {
                "1": "https://assets.com/video1.mp4"
            }
        },
        "bgm_path": "https://assets.com/bgm.mp3",
        "voice_name": "vi-VN-NamMinhNeural"
    }
    script = "Dòng 1. Dòng 2."
    healed = heal_video_composition("review", legacy_review, script, "Title")
    assert healed["bgm_path"] == "https://assets.com/bgm.mp3"
    assert healed["voice_name"] == "vi-VN-NamMinhNeural"
    assert len(healed["scenes"]) == 1
    
    scene = healed["scenes"][0]
    assert scene["scene_id"] == "seg_1"
    assert scene["clip_url"] == "https://assets.com/video1.mp4"
    assert scene["text_overlay"] == "Giới thiệu sản phẩm xịn sò"
    assert scene["duration"] == 4.5
    assert "zoom_in" in scene["effects"]
    assert "camera_shake" in scene["effects"] # Auto added camera_shake for the first scene if not there
    assert "sản phẩm" in scene["highlight_words"]

def test_heal_video_composition_from_legacy_unbox():
    legacy_unbox = {
        "text_events": [
            {"text": "Đập hộp quà cực chất!", "effect": "hook"},
            {"text": "Bên trong có gì nào?", "effect": "normal"}
        ],
        "clips": ["https://assets.com/unbox1.mp4"],
        "audio": "https://assets.com/unbox_bgm.mp3"
    }
    healed = heal_video_composition("unbox", legacy_unbox, "Câu 1. Câu 2.", "Unbox Title")
    assert healed["bgm_path"] == "https://assets.com/unbox_bgm.mp3"
    assert len(healed["scenes"]) == 2
    
    s1 = healed["scenes"][0]
    assert s1["scene_id"] == "scene_1"
    assert s1["clip_url"] == "https://assets.com/unbox1.mp4"
    assert s1["text_overlay"] == "Đập hộp quà cực chất!"
    assert "camera_shake" in s1["effects"]

def test_heal_video_composition_from_slideshow():
    legacy_slideshow = {
        "input_json": {
            "products": [
                {"image": "img1.jpg", "text": "Sản phẩm 1"},
                {"image": "img2.jpg", "text": "Sản phẩm 2"}
            ]
        }
    }
    healed = heal_video_composition("slideshow", legacy_slideshow, "Giới thiệu.", "Slideshow Title")
    assert len(healed["scenes"]) == 2
    assert healed["scenes"][0]["scene_id"] == "product_1"
    assert healed["scenes"][0]["clip_url"] == "img1.jpg"
    assert healed["scenes"][0]["text_overlay"] == "Sản phẩm 1"
