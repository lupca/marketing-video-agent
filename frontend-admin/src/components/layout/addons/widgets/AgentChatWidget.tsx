import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Copy, Check, Sparkles, Loader2, Plus, MessageSquare, Trash2 } from "lucide-react";
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

interface ChatSession {
  id: string;
  title: string;
  selected_model_id: string;
  created_at: string;
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

  // Sessions and History States
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [showHistorySidebar, setShowHistorySidebar] = useState(false);

  // Chat State
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: "ai",
      text: "Xin chào! Tôi là Trợ lý AI hoạt động thời gian thực. Tôi có thể giúp bạn viết kịch bản, đề xuất prompt ảnh FLUX, dịch thuật siêu tốc hoặc tư duy bối cảnh video marketing.\n\nHãy lựa chọn mô hình LLM ở phía trên để bắt đầu trò chuyện nhé!",
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

  // Load chat sessions when project is changed
  const fetchSessions = async (projId: string) => {
    try {
      const res = await api.get(`/api/chat/sessions?project_id=${projId}`);
      setSessions(res.data);
      if (res.data.length > 0) {
        // Load messages for the most recent session
        handleSelectSession(res.data[0].id, res.data[0].selected_model_id);
      } else {
        // Create first default session
        handleCreateSession(projId);
      }
    } catch (err) {
      console.error("Failed to fetch chat sessions:", err);
    }
  };

  useEffect(() => {
    if (selectedProjectId) {
      fetchSessions(selectedProjectId);
    }
  }, [selectedProjectId]);

  const handleSelectSession = async (sessionId: string, modelId?: string) => {
    setActiveSessionId(sessionId);
    if (modelId) setSelectedModel(modelId);
    setShowHistorySidebar(false);
    
    try {
      const res = await api.get(`/api/chat/sessions/${sessionId}/messages`);
      if (res.data && res.data.length > 0) {
        setMessages(res.data.map((m: any) => ({
          sender: m.sender === "user" ? "user" : "ai",
          text: m.content,
          timestamp: new Date(m.created_at)
        })));
      } else {
        setMessages([
          {
            sender: "ai",
            text: "Cuộc trò chuyện mới đã bắt đầu. Hãy lựa chọn mô hình ở trên và đặt câu hỏi cho tôi nhé!",
            timestamp: new Date()
          }
        ]);
      }
    } catch (err) {
      console.error("Failed to load messages:", err);
    }
  };

  const handleCreateSession = async (projId?: string) => {
    const pId = projId || selectedProjectId;
    if (!pId) return;

    try {
      const res = await api.post("/api/chat/sessions", {
        project_id: pId,
        title: `Hội thoại #${sessions.length + 1}`,
        selected_model_id: selectedModel
      });
      setSessions((prev) => [res.data, ...prev]);
      setActiveSessionId(res.data.id);
      setMessages([
        {
          sender: "ai",
          text: "Cuộc hội thoại mới đã được khởi tạo thành công. Hãy đặt câu hỏi ở ô nhập liệu phía dưới!",
          timestamp: new Date()
        }
      ]);
      setShowHistorySidebar(false);
    } catch (err) {
      console.error("Failed to create chat session:", err);
    }
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Bạn có chắc chắn muốn xóa cuộc hội thoại này không?")) return;

    try {
      await api.delete(`/api/chat/sessions/${sessionId}`);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeSessionId === sessionId) {
        const remaining = sessions.filter((s) => s.id !== sessionId);
        if (remaining.length > 0) {
          handleSelectSession(remaining[0].id, remaining[0].selected_model_id);
        } else {
          setActiveSessionId(null);
          setMessages([]);
        }
      }
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  // Sync selected model back to active session
  const handleModelChange = async (modelId: string) => {
    setSelectedModel(modelId);
    if (activeSessionId) {
      try {
        await api.put(`/api/chat/sessions/${activeSessionId}`, {
          selected_model_id: modelId
        });
        // Sync inside state list
        setSessions((prev) => prev.map((s) => s.id === activeSessionId ? { ...s, selected_model_id: modelId } : s));
      } catch (err) {
        console.warn("Failed to sync selected model to active session:", err);
      }
    }
  };

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
    if (!query.trim() || !activeSessionId) return;

    // 1. Add user message to state immediately
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
      const token = localStorage.getItem("token");
      const baseURL = api.defaults.baseURL || "http://localhost:9100";
      const response = await fetch(`${baseURL}/api/chat/sessions/${activeSessionId}/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { "Authorization": `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ content: query })
      });

      if (!response.ok) {
        throw new Error(`Server returned HTTP error ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder("utf-8");

      let aiResponseText = "";
      const aiMsgIndex = updatedMessages.length;
      
      // Inject blank message for AI typing visual update
      setMessages((prev) => [...prev, { sender: "ai", text: "", timestamp: new Date() }]);

      while (true) {
        const { value, done } = await reader!.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");
        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("data: ")) {
            try {
              const data = JSON.parse(trimmed.substring(6));
              if (data.token) {
                aiResponseText += data.token;
                setMessages((prev) => {
                  const copy = [...prev];
                  copy[aiMsgIndex] = { ...copy[aiMsgIndex], text: aiResponseText };
                  return copy;
                });
              } else if (data.error) {
                aiResponseText += `\n\n🔴 Lỗi: ${data.error}`;
                setMessages((prev) => {
                  const copy = [...prev];
                  copy[aiMsgIndex] = { ...copy[aiMsgIndex], text: aiResponseText };
                  return copy;
                });
              }
            } catch (err) {
              // Ignore incomplete json chunks
            }
          }
        }
      }
      setIsTyping(false);

    } catch (err: any) {
      console.error("Failed to run streaming completions:", err);
      const errorMsg: Message = {
        sender: "ai",
        text: `🔴 Lỗi kết nối trực tiếp: ${err.message || "Không thể kết nối đến máy chủ."}`,
        timestamp: new Date()
      };
      setMessages((prev) => [...prev, errorMsg]);
      setIsTyping(false);
    }
  };

  const quickPrompts = [
    { label: "💡 Kịch bản video Unbox", query: "Viết kịch bản video Unbox công nghệ ngắn 30s" },
    { label: "🎨 Prompt vẽ ảnh FLUX", query: "Gợi ý prompt vẽ ảnh FLUX cho sản phẩm công nghệ" },
    { label: "🌐 Dịch Việt - Anh", query: "Dịch câu quảng cáo này sang tiếng Anh: Chào mừng tới nền tảng video AI" }
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] bg-zinc-950/20 rounded-2xl border border-white/5 overflow-hidden relative">
      
      {/* Drawer Title & Session Controls */}
      <div className="p-3 bg-black/40 border-b border-white/5 flex items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <button 
            onClick={() => setShowHistorySidebar(!showHistorySidebar)}
            className="p-1.5 hover:bg-white/5 rounded-lg text-muted-foreground hover:text-white transition-colors"
            title="Lịch sử hội thoại"
          >
            <MessageSquare className="w-4 h-4" />
          </button>
          <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-widest flex items-center gap-1.5">
            <Bot className="w-3.5 h-3.5 text-primary animate-pulse" /> Trợ Lý
          </span>
        </div>

        {/* Dynamic Model Dropdown */}
        <select
          value={selectedModel}
          onChange={(e) => handleModelChange(e.target.value)}
          disabled={isTyping}
          className="flex-1 max-w-[160px] bg-zinc-900 border border-white/10 rounded-xl px-2.5 py-1.5 text-[11px] text-white focus:outline-none focus:ring-1 focus:ring-primary font-sans font-medium"
        >
          {modelsList.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>

        <button 
          onClick={() => handleCreateSession()}
          className="p-1.5 bg-primary/20 hover:bg-primary/40 rounded-lg text-primary border border-primary/20 hover:scale-105 active:scale-95 transition-all"
          title="Tạo cuộc hội thoại mới"
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* History Sidebar Panel Overlay */}
      {showHistorySidebar && (
        <div className="absolute inset-0 z-20 flex">
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowHistorySidebar(false)} />
          
          {/* History drawer list */}
          <div className="w-64 bg-zinc-950 border-r border-white/10 p-4 relative z-10 flex flex-col justify-between h-full animate-in slide-in-from-left duration-200">
            <div className="space-y-4">
              <div className="flex items-center justify-between border-b border-white/5 pb-2">
                <span className="text-xs font-bold text-white tracking-wide">Lịch sử hội thoại</span>
                <button 
                  onClick={() => handleCreateSession()} 
                  className="flex items-center gap-1 text-[10px] bg-primary/20 hover:bg-primary/30 border border-primary/30 text-primary px-2 py-1 rounded-lg"
                >
                  <Plus className="w-3 h-3" /> New
                </button>
              </div>
              <div className="space-y-1.5 overflow-y-auto max-h-[calc(100vh-18rem)] custom-scrollbar">
                {sessions.map((s) => (
                  <div 
                    key={s.id}
                    onClick={() => handleSelectSession(s.id, s.selected_model_id)}
                    className={cn(
                      "flex items-center justify-between p-2.5 rounded-xl cursor-pointer transition-colors group",
                      activeSessionId === s.id ? "bg-white/10 text-white" : "hover:bg-white/5 text-muted-foreground"
                    )}
                  >
                    <span className="text-xs truncate font-medium flex-1 pr-2">{s.title}</span>
                    <button 
                      onClick={(e) => handleDeleteSession(s.id, e)}
                      className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 text-muted-foreground hover:text-red-400 rounded-lg transition-all"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

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

        {isTyping && messages[messages.length - 1]?.sender === "user" && (
          <div className="flex gap-3 max-w-[80%] self-start animate-pulse">
            <div className="w-8 h-8 rounded-full bg-primary/20 border border-primary/40 text-primary flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-white/5 border border-white/10 p-4 rounded-2xl rounded-tl-none flex flex-col gap-2 min-w-[200px]">
              <p className="text-[10px] text-muted-foreground font-semibold flex items-center gap-1.5 animate-pulse">
                <Loader2 className="w-3 h-3 animate-spin text-primary" />
                Chat stream đang kết nối...
              </p>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick Suggestions */}
      {messages.length <= 1 && !isTyping && (
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
            placeholder={activeSessionId ? "Đặt câu hỏi, viết kịch bản..." : "Đang khởi tạo kết nối hội thoại..."}
            className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-xs text-white placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-primary/40 focus:border-primary/40"
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || isTyping || !activeSessionId}
            className={cn(
              "p-3 rounded-xl flex items-center justify-center transition-all",
              inputValue.trim() && !isTyping && activeSessionId
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
