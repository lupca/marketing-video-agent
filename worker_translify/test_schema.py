import sys
import os

# Add root project path to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worker_translify.model.video_schema import VideoProject, Scene, SpeakerData, AudioData, VisualData, BgmData, OcrItem

def test_schema():
    print("🧪 Running Video-as-Data Pydantic Schema Unit Test...")
    
    # Create mock OcrItem
    ocr = OcrItem(
        bbox=[[10, 20], [100, 20], [100, 50], [10, 50]],
        text_zh="抖音美好生活",
        text_vi="Đời sống tốt đẹp Douyin"
    )
    
    # Create mock Scene
    scene = Scene(
        id="scene_1",
        start=0.0,
        end=3.5,
        speaker=SpeakerData(id="A", face_bbox=[], emotion_src="happy"),
        audio=AudioData(
            zh_text="你好",
            vi_text="Xin chào",
            duration=3.5
        ),
        visual=VisualData(ocr_text=[ocr]),
        bgm=BgmData(type="custom", volume=0.4)
    )
    
    # Create mock VideoProject
    project = VideoProject(
        video_id="test_video_123",
        scenes=[scene]
    )
    
    # Serialize to JSON string
    json_data = project.model_dump_json()
    print("✅ Serialization successful!")
    print(f"JSON Output:\n{project.model_dump_json(indent=2)}")
    
    # Deserialize back from JSON
    reloaded = VideoProject.model_validate_json(json_data)
    assert reloaded.video_id == "test_video_123"
    assert len(reloaded.scenes) == 1
    assert reloaded.scenes[0].audio.zh_text == "你好"
    assert reloaded.scenes[0].visual.ocr_text[0].text_vi == "Đời sống tốt đẹp Douyin"
    
    print("✅ Deserialization & validation successful! All assertions passed!")

if __name__ == "__main__":
    test_schema()
