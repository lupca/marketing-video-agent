import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import json

# Add root and worker_translify folders to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../worker_translify")))

from model.video_schema import VideoProject, Scene, SpeakerData, AudioData, VisualData, BgmData, OcrItem
from worker_translify.agent import translify_graph
from worker_translify.agent.nodes import extract_json_from_text
from worker_translify.celery_worker import analyze_video

class TestTranslifyGraph(unittest.TestCase):
    
    def test_extract_json_from_text(self):
        # Case 1: Simple JSON
        text1 = '{"key": "value"}'
        self.assertEqual(extract_json_from_text(text1), {"key": "value"})
        
        # Case 2: Thinking blocks & markdown
        text2 = '<think>some thought</think>\n```json\n{"key": "value"}\n```'
        self.assertEqual(extract_json_from_text(text2), {"key": "value"})
        
        # Case 3: Outer brackets
        text3 = 'Here is the result:\n{"key": "value"}\nHope it helps!'
        self.assertEqual(extract_json_from_text(text3), {"key": "value"})

    @patch("worker_translify.agent.nodes.ChatOpenAI")
    @patch("worker_translify.agent.nodes.resolve_llm_config")
    @patch("shared_core.database.SessionLocal")
    @patch("shared_core.minio_utils.upload_file_to_minio")
    @patch("shared_core.worker_base.get_or_create_job_folders")
    @patch("shared_core.minio_utils.is_minio_path")
    def test_translify_graph_execution(
        self,
        mock_is_minio_path,
        mock_get_folders,
        mock_upload_minio,
        mock_session_local,
        mock_resolve_llm,
        mock_chat_openai
    ):
        # Mock settings and LLM configuration
        mock_resolve_llm.return_value = {
            "base_url": "http://localhost:11434",
            "model_name": "qwen2.5:14b",
            "api_key": "dummy",
            "provider": "ollama"
        }
        mock_is_minio_path.return_value = False
        mock_upload_minio.return_value = "http://minio/jobs/1/vocal.wav"
        mock_get_folders.return_value = ("folder_parent", "folder_output", "proj_1")
        
        # Mock DB session and VideoJob query
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_job = MagicMock()
        mock_job.id = 42
        mock_job.project = MagicMock(user_id="user_123")
        mock_job.config_data = {}
        mock_job.status = "PENDING"
        mock_job.progress_percent = 0
        mock_db.query().filter().first.return_value = mock_job

        # Setup Mock LLM invoke answers
        mock_llm_instance = MagicMock()
        mock_chat_openai.return_value = mock_llm_instance
        
        # We need mock responses for glossary extraction, sliding translations, OCR, adaptations, and trimming.
        # Let's write a side_effect function to return different mock AI outputs based on the node prompts.
        def mock_llm_invoke(messages):
            sys_msg = messages[0].content
            user_msg = messages[1].content
            
            # 1. Glossary Node
            if "glossary" in sys_msg.lower() and "theme_summary" in sys_msg.lower():
                return MagicMock(content=json.dumps({
                    "theme_summary": "Tóm tắt chủ đề video marketing.",
                    "glossary": [
                        {"src": "产品", "tgt": "Sản phẩm", "note": "Product"}
                    ]
                }))
            
            # 2. OCR translation in sliding translation node
            if "translations" in sys_msg.lower() and "zh" in sys_msg.lower():
                return MagicMock(content=json.dumps({
                    "translations": [
                        {"zh": "特价", "vi": "GIÁ SIÊU RẺ"}
                    ]
                }))
                
            # 3. Sliding Dialogue Translation
            if "direct_translation" in sys_msg.lower():
                # check if scene 1 or scene 2
                if "你好，世界" in user_msg:
                    return MagicMock(content=json.dumps({
                        "direct_translation": "Xin chào thế giới."
                    }))
                else:
                    return MagicMock(content=json.dumps({
                        "direct_translation": "Đây là một câu dịch sát nghĩa siêu siêu siêu dài và chi tiết."
                    }))
            
            # 4. Reflective Adaptation Node
            if "reflective adaptation" in sys_msg.lower() or "free_translation" in sys_msg.lower():
                if "Xin chào thế giới." in user_msg:
                    return MagicMock(content=json.dumps({
                        "reflection": "Bản dịch tốt",
                        "free_translation": "Xin chào cả nhà thân yêu."
                    }))
                else:
                    # Let's return a long adapted string to trigger pacing validation
                    return MagicMock(content=json.dumps({
                        "reflection": "Cần thêm chi tiết",
                        "free_translation": "Đây là một bản dịch Việt hóa vô cùng dài dòng lê thê dài dòng lê thê dài dòng lê thê dài dòng lê thê dài dòng lê thê"
                    }))
            
            # 5. Subtitle Trimming Node (self-healing)
            if "rút gọn" in sys_msg.lower() or "result" in sys_msg.lower():
                return MagicMock(content=json.dumps({
                    "analysis": "Loại bỏ từ thừa",
                    "result": "Dịch siêu ngắn gọn."
                }))
                
            return MagicMock(content="{}")
            
        mock_llm_instance.invoke.side_effect = mock_llm_invoke
        
        # 6. Build test VideoProject
        # Scene 1: OK pace (duration = 5s, words = 5)
        # Scene 2: Violating pace (duration = 1s, words = 16)
        scene1 = Scene(
            id="scene_1",
            start=0.0,
            end=5.0,
            speaker=SpeakerData(id="A"),
            audio=AudioData(
                zh_text="你好，世界。",
                duration=5.0
            ),
            visual=VisualData(ocr_text=[OcrItem(bbox=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], text_zh="特价")]),
            bgm=BgmData()
        )
        
        scene2 = Scene(
            id="scene_2",
            start=5.0,
            end=6.0,
            speaker=SpeakerData(id="A"),
            audio=AudioData(
                zh_text="这是一段...文字内容需要被翻译和縮短。",
                duration=1.0
            ),
            visual=VisualData(),
            bgm=BgmData()
        )
        
        project = VideoProject(
            video_id="test_project_1",
            scenes=[scene1, scene2],
            vocal_url="local_vocal.wav",
            bgm_url="local_bgm.wav"
        )
        
        # 7. Run Celery Task analyze_video synchronously
        with patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=100), \
             patch("worker_translify.celery_worker.download_translify_assets") as mock_download, \
             patch("worker_translify.celery_worker.AnalysisEngine") as mock_engine_cls:
             
             mock_download.return_value = {"video": "raw_video.mp4"}
             
             mock_engine = MagicMock()
             mock_engine.analyze.return_value = project
             mock_engine_cls.return_value = mock_engine
             
             from worker_translify.celery_worker import analyze_video
             analyze_video(42, {"campaign_tone": "trẻ trung"})
            
        # Assertions
        # Verify that project_data was serialized into mock_job.config_data
        self.assertIn("project_data", mock_job.config_data)
        project_data_res = mock_job.config_data["project_data"]
        
        # Verify that scene 1 is translated correctly
        scene1_final = project_data_res["scenes"][0]
        self.assertEqual(scene1_final["audio"]["vi_text"], "Xin chào cả nhà thân yêu.")
        self.assertEqual(scene1_final["visual"]["ocr_text"][0]["text_vi"], "GIÁ SIÊU RẺ")
        
        # Verify that scene 2 has been trimmed correctly because of pacing validation
        scene2_final = project_data_res["scenes"][1]
        self.assertEqual(scene2_final["audio"]["vi_text"], "Dịch siêu ngắn gọn.")
        
        # Verify DB updates are made inside the celery task persistence layer
        mock_db.commit.assert_called()
        self.assertEqual(mock_job.status, "WAITING_FOR_REVIEW")
        self.assertEqual(mock_job.progress_percent, 100)
        
        print("🎉 All translify LangGraph tests passed flawlessly!")

if __name__ == "__main__":
    unittest.main()
