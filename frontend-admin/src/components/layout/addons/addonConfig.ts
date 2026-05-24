import React from "react";
import { Sparkles, Volume2, DownloadCloud, Bot } from "lucide-react";
import AgentChatWidget from "./widgets/AgentChatWidget";
import ImageStudioWidget from "./widgets/ImageStudioWidget";
import SpeechStudioWidget from "./widgets/SpeechStudioWidget";
import VideoDownloadWidget from "./widgets/VideoDownloadWidget";

export interface AIAddon {
  id: string;
  name: string;
  icon: React.ComponentType<any>;
  description: string;
  component: React.ComponentType<any>;
}

// Mảng đăng ký trung tâm cho toàn bộ AI Addons hỗ trợ
export const AI_ADDONS: AIAddon[] = [
  {
    id: "ai_chat",
    name: "Trợ Lý AI",
    icon: Bot,
    description: "Hỏi đáp kịch bản, đề xuất prompt ảnh FLUX, dịch thuật siêu tốc",
    component: AgentChatWidget
  },
  {
    id: "image_studio",
    name: "Image Studio",
    icon: Sparkles,
    description: "Sáng tạo ảnh nghệ thuật AI minh họa bằng mô hình FLUX",
    component: ImageStudioWidget
  },
  {
    id: "speech_studio",
    name: "Speech Studio",
    icon: Volume2,
    description: "Biến văn bản kịch bản thành giọng thuyết minh tiếng Việt",
    component: SpeechStudioWidget
  },
  {
    id: "video_download",
    name: "Sưu tầm Video",
    icon: DownloadCloud,
    description: "Tải video/tư liệu gốc chất lượng cao từ Youtube, Tiktok",
    component: VideoDownloadWidget
  }
];
