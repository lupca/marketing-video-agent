import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Copy, Check, Sparkles, Loader2 } from "lucide-react";
import api from "../../../../lib/api";
import { cn } from "../../../../lib/utils";
import { useProjects } from "../../../../hooks/useProjects";

interface ModelConfig {
  id: string;
  name: string;
  model_name: string;
  base_url: string;
  api_key?: string;
}

interface Message {
  sender: "user" | "ai";
  text: string;
  timestamp: Date;
}

export default function AgentChatWidget() {
  const { projects } = useProjects();
  
  // Model & Projects State
  const [modelsList, setModelsList] = useState<ModelConfig[]>([
    { id: "qwen3.5:latest", name: "Ollama Qwen 3.5", model_name: "qwen3.5:latest", base_url: "http://localhost:11434" },
    { id: "gemma4:latest", name: "Ollama Gemma 4", model_name: "gemma4:latest", base_url: "http://localhost:11434" },
  ]);
  const [selectedModel, setSelectedModel] = useState("qwen3.5:latest");
  const [selectedProjectId, setSelectedProjectId] = useState("");

  // Chat State
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: "ai",
      text: "Xin chào! Tôi là Trợ lý AI hoạt động thông qua hệ thống Worker chạy nền. Tôi có thể giúp bạn viết kịch bản, đề xuất prompt ảnh FLUX, dịch thuật siêu tốc hoặc tư duy bối cảnh video marketing.\n\nHãy lựa chọn mô hình LLM ở phía trên để bắt đầu trò chuyện nhé!",
      timestamp: new Date()
    }
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch Ollama models from backend on mount
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const res = await api.get("/api/system/chat-models");
        if (res.data && res.data.length > 0) {
          setModelsList(res.data);
          // Set first model ID as default
          setSelectedModel(res.data[0].id);
        }
      } catch (err) {
        console.warn("Failed to fetch Ollama models, using default fallbacks:", err);
      }
    };
    fetchModels();
  }, []);

  // Set default project behind the scenes
  useEffect(() => {
    if (projects && projects.length > 0 && !selectedProjectId) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleCopyText = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleSendMessage = async (textToSend?: string) => {
    const query = textToSend || inputValue;
    if (!query.trim()) return;

    const projectId = selectedProjectId || (projects && projects.length > 0 ? projects[0].id : null);
    if (!projectId) {
      // If no project exists, we cannot post the job
      alert("Vui lòng tạo ít nhất một Project trước khi bắt đầu chat!");
      return;
    }

    // 1. Add user message to state
    const userMsg: Message = {
      sender: "user",
      text: query,
      timestamp: new Date()
    };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInputValue("");
    setIsTyping(true);

    try {
      // 2. Submit Chat Job to Celery Queue via API
      // We pass the conversation history in config_data so the LLM retains memory!
      const response = await api.post("/api/jobs", {
        job_type: "chat",
        project_id: projectId,
        config_data: {
          model: selectedModel,
          text: query,
          history: messages.slice(-10)  // Keep last 10 messages for memory context
        }
      });

      const jobId = response.data.id;
      
      // 3. Poll for Celery Job Success
      startPolling(jobId);

    } catch (err: any) {
      console.error("Failed to submit chat job:", err);
      const errorMsg: Message = {
        sender: "ai",
        text: `🔴 Lỗi hệ thống: ${err.response?.data?.detail || "Không thể gửi tin nhắn đến Chat Worker. Hãy kiểm tra lại kết nối server."}`,
        timestamp: new Date()
      };
      setMessages((prev) => [...prev, errorMsg]);
      setIsTyping(false);
    }
  };

  const startPolling = (jobId: number) => {
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/api/jobs/${jobId}`);
        const job = res.data;

        if (job.status === "SUCCESS") {
          // Read AI response from job's note field
          const aiResponseText = job.note || "Worker hoàn thành nhưng không nhận được câu trả lời từ LLM.";
          const aiMsg: Message = {
            sender: "ai",
            text: aiResponseText,
            timestamp: new Date()
          };
          setMessages((prev) => [...prev, aiMsg]);
          setIsTyping(false);
          clearInterval(interval);
        } else if (job.status === "FAILED") {
          const aiMsg: Message = {
            sender: "ai",
            text: `🔴 Chat Worker báo lỗi: ${job.error_message || "Đã xảy ra lỗi khi gọi LLM."}`,
            timestamp: new Date()
          };
          setMessages((prev) => [...prev, aiMsg]);
          setIsTyping(false);
          clearInterval(interval);
        }
      } catch (err) {
        console.error("Error polling chat job:", err);
      }
    }, 1500);

    // Safety Timeout after 3 minutes
    setTimeout(() => {
      clearInterval(interval);
      if (isTyping) {
        setIsTyping(false);
        const timeoutMsg: Message = {
          sender: "ai",
          text: "🔴 Quá thời gian phản hồi từ Chat Worker. Vui lòng kiểm tra lại tình trạng Ollama server.",
          timestamp: new Date()
        };
        setMessages((prev) => [...prev, timeoutMsg]);
      }
    }, 180000);
  };

  const quickPrompts = [
    { label: "💡 Kịch bản video Unbox", query: "Viết kịch bản video Unbox công nghệ ngắn 30s" },
    { label: "🎨 Prompt vẽ ảnh FLUX", query: "Gợi ý prompt vẽ ảnh FLUX cho sản phẩm công nghệ" },
    { label: "🌐 Dịch Việt - Anh", query: "Dịch câu quảng cáo này sang tiếng Anh: Chào mừng tới nền tảng video AI" }
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] bg-zinc-950/20 rounded-2xl border border-white/5 overflow-hidden">
      {/* Model Selector Header */}
      <div className="p-3 bg-black/40 border-b border-white/5 flex items-center justify-between gap-3 shrink-0">
        <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-widest flex items-center gap-1.5 shrink-0">
          <Bot className="w-3.5 h-3.5 text-primary animate-pulse" /> Mô hình
        </span>
        <select
          value={selectedModel}
          onChange={(e) => setSelectedModel(e.target.value)}
          disabled={isTyping}
          className="flex-1 max-w-[240px] bg-zinc-900 border border-white/10 rounded-xl px-2.5 py-1.5 text-[11px] text-white focus:outline-none focus:ring-1 focus:ring-primary font-sans font-medium"
        >
          {modelsList.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name} ({m.model_name})
            </option>
          ))}
        </select>
      </div>

      {/* Messages Window */}
      <div className="flex-1 p-4 overflow-y-auto space-y-4 custom-scrollbar">
        {messages.map((msg, index) => {
          const isAI = msg.sender === "ai";
          return (
            <div
              key={index}
              className={cn(
                "flex gap-3 max-w-[85%] animate-in fade-in slide-in-from-bottom-2 duration-300",
                isAI ? "self-start" : "self-end flex-row-reverse ml-auto"
              )}
            >
              {/* Avatar */}
              <div
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center border shrink-0",
                  isAI
                    ? "bg-primary/20 border-primary/40 text-primary"
                    : "bg-white/10 border-white/20 text-white"
                )}
              >
                {isAI ? <Bot className="w-4 h-4" /> : <User className="w-4 h-4" />}
              </div>

              {/* Message Bubble */}
              <div className="space-y-1 group relative">
                <div
                  className={cn(
                    "p-3.5 rounded-2xl text-xs leading-relaxed border whitespace-pre-wrap font-sans",
                    isAI
                      ? "bg-white/5 border-white/10 text-white/95 rounded-tl-none"
                      : "bg-primary/10 border-primary/30 text-white rounded-tr-none"
                  )}
                >
                  {msg.text}
                </div>

                {/* AI Copy Button */}
                {isAI && (
                  <button
                    onClick={() => handleCopyText(msg.text, index)}
                    className="absolute right-2 -bottom-7 p-1.5 bg-black/60 hover:bg-black/90 text-muted-foreground hover:text-white border border-white/10 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider cursor-pointer"
                    title="Sao chép câu trả lời"
                  >
                    {copiedIndex === index ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-400" />
                        <span className="text-emerald-400">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        <span>Copy</span>
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          );
        })}

        {/* AI Typing Indicator */}
        {isTyping && (
          <div className="flex gap-3 max-w-[80%] self-start animate-pulse">
            <div className="w-8 h-8 rounded-full bg-primary/20 border border-primary/40 text-primary flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-white/5 border border-white/10 p-4 rounded-2xl rounded-tl-none flex flex-col gap-2 min-w-[200px]">
              <p className="text-[10px] text-muted-foreground font-semibold flex items-center gap-1.5 animate-pulse">
                <Loader2 className="w-3 h-3 animate-spin text-primary" />
                Chat Worker đang suy nghĩ...
              </p>
              <div className="flex items-center gap-1.5 pt-0.5">
                <span className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce delay-75"></span>
                <span className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce delay-150"></span>
                <span className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce delay-225"></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick Suggestions */}
      {messages.length === 1 && !isTyping && (
        <div className="px-4 pb-2 space-y-2 shrink-0">
          <p className="text-[10px] uppercase font-bold text-muted-foreground tracking-widest flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-primary animate-pulse" /> Đề xuất nhanh
          </p>
          <div className="flex flex-col gap-1.5">
            {quickPrompts.map((p, i) => (
              <button
                key={i}
                onClick={() => handleSendMessage(p.query)}
                className="w-full text-left p-2.5 bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/10 text-[11px] font-medium text-white/90 rounded-xl transition-all hover:translate-x-1 cursor-pointer"
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input Form Box */}
      <div className="p-3 border-t border-white/5 bg-zinc-950/40 shrink-0">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            disabled={isTyping}
            placeholder="Đặt câu hỏi, viết kịch bản..."
            className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-xs text-white placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-primary/40 focus:border-primary/40"
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || isTyping}
            className={cn(
              "p-3 rounded-xl flex items-center justify-center transition-all",
              inputValue.trim() && !isTyping
                ? "bg-primary text-white hover:scale-105 active:scale-95 cursor-pointer shadow-[0_0_15px_rgba(124,58,237,0.3)]"
                : "bg-white/5 text-muted-foreground/40 cursor-not-allowed"
            )}
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
