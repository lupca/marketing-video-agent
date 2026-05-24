import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Copy, Check, Sparkles } from "lucide-react";
import { cn } from "../../../../lib/utils";

interface Message {
  sender: "user" | "ai";
  text: string;
  timestamp: Date;
}

export default function AgentChatWidget() {
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: "ai",
      text: "Xin chào! Tôi là Trợ lý AI sáng tạo. Tôi có thể giúp bạn viết kịch bản, biên tập tiêu đề, dịch thuật hoặc thiết kế Prompt ảnh FLUX ngay tại đây. Bạn cần hỗ trợ gì hôm nay?",
      timestamp: new Date()
    }
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

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

  const getAIResponse = (input: string): string => {
    const text = input.toLowerCase();
    if (text.includes("unbox") || text.includes("kịch bản unbox")) {
      return `### 📝 KỊCH BẢN VIDEO UNBOX GỢI Ý (Độ dài: 30s - 45s)

**Phân cảnh 1 [0-5s]**: Cận cảnh tay bóc hộp sản phẩm cực kỳ nhanh và dứt khoát. Tiếng xé băng dính sắc sảo (ASMR).
*Hiệu ứng*: Zoom nhẹ 1.2x, chèn nhạc beat đập mạnh.
*Voiceover*: "Bóc hộp cực phẩm công nghệ hot nhất tuần này. Liệu có đáng đồng tiền bát gạo?"

**Phân cảnh 2 [5-15s]**: Show trọn vẹn sản phẩm dưới ánh đèn studio. Xoay các góc cạnh đẹp mắt.
*Voiceover*: "Ấn tượng đầu tiên là thiết kế nhôm nguyên khối siêu mờ lì. Cầm cực đầm tay và cao cấp!"

**Phân cảnh 3 [15-30s]**: Trải nghiệm nhanh một tính năng đắt giá nhất của sản phẩm.
*Voiceover*: "Điểm ăn tiền nằm ở tốc độ xử lý nhanh gấp 2 lần bản cũ nhờ chip AI mới. Gen ảnh, dựng video trong chớp mắt!"

**Phân cảnh 4 [30-45s]**: Kêu gọi hành động (Call to action).
*Voiceover*: "Click ngay giỏ hàng bên dưới để nhận ưu đãi giảm 20% trong hôm nay!"`;
    }

    if (text.includes("prompt") || text.includes("vẽ ảnh") || text.includes("flux")) {
      return `### 🎨 BỘ PROMPTS VẼ ẢNH FLUX AI CỰC ĐẸP CHO MARKETING:

**1. Phong cách Sản phẩm Tương lai (Cyberpunk Tech):**
\`\`\`text
A futuristic wireless headphone floating in mid-air, dark cyberpunk background with neon purple and cyan lasers, cinematic lighting, highly detailed 3D render, octane render, photorealistic, 8k resolution
\`\`\`

**2. Phong cách Nhân vật sáng tạo (Creator Avatar):**
\`\`\`text
A friendly AI robot holding a professional cinema camera, working inside a neon glowing high-tech video production studio, cinematic shot, beautiful colors, Pixar style 3D render, soft lighting
\`\`\`

**3. Phong cách Bối cảnh bán hàng (E-commerce Banner):**
\`\`\`text
Premium cosmetic bottle standing on a sleek clean water surface with gentle ripples, pink and gold pastel background, studio lighting, hyperrealistic, elegant minimal aesthetics, commercial photography
\`\`\`

*Mẹo: Bạn có thể copy một trong các prompt trên, mở tab **Image Studio** ở Dock bên phải và dán vào để gen ảnh ngay lập tức!*`;
    }

    if (text.includes("dịch") || text.includes("translate") || text.includes("english")) {
      return `### 🌐 BẢN DỊCH SONG NGỮ VIỆT - ANH GỢI Ý:

**Tiếng Việt:**
"Chào mừng bạn đến với VidGenius - Nền tảng tự động sản xuất video marketing bằng AI hàng đầu hiện nay. Hãy cùng tạo ra những thước phim viral đỉnh cao!"

**Tiếng Anh (English):**
"Welcome to VidGenius - The leading AI-powered marketing video automation platform today. Let's create ultimate viral videos together!"`;
    }

    return `Tôi đã ghi nhận yêu cầu của bạn về: "${input}". 

Dưới đây là một số ý tưởng đề xuất để tối ưu hóa video marketing:
1. **Tiêu đề giật gân (Hook):** Sử dụng các từ khóa kích thích như "Bí mật...", "Tại sao bạn không nên mua...", "Sự thật về..."
2. **Hình ảnh thu hút (Thumbnail):** Hãy dùng **Image Studio Addon** để tạo một bức ảnh nhân vật thể hiện cảm xúc ngạc nhiên kèm theo sản phẩm dưới ánh sáng tương phản cao (neon blue/red).
3. **Nhịp điệu video (Pacing):** Đối với các dòng video Shorts/Reels, hãy đảm bảo chuyển cảnh tối thiểu 2-3 giây/lần để giữ chân người xem lâu nhất.

Bạn có muốn tôi viết chi tiết kịch bản cụ thể cho sản phẩm nào của bạn không?`;
  };

  const handleSendMessage = (textToSend?: string) => {
    const query = textToSend || inputValue;
    if (!query.trim()) return;

    // Add user message
    const userMsg: Message = {
      sender: "user",
      text: query,
      timestamp: new Date()
    };
    setMessages((prev) => [...prev, userMsg]);
    setInputValue("");
    setIsTyping(true);

    // Simulate AI response delay
    setTimeout(() => {
      const aiResponse = getAIResponse(query);
      const aiMsg: Message = {
        sender: "ai",
        text: aiResponse,
        timestamp: new Date()
      };
      setMessages((prev) => [...prev, aiMsg]);
      setIsTyping(false);
    }, 1200);
  };

  const quickPrompts = [
    { label: "💡 Kịch bản video Unbox", query: "Viết kịch bản video Unbox công nghệ ngắn 30s" },
    { label: "🎨 Prompt vẽ ảnh FLUX", query: "Gợi ý prompt vẽ ảnh FLUX cho sản phẩm công nghệ" },
    { label: "🌐 Dịch Việt - Anh", query: "Dịch câu quảng cáo này sang tiếng Anh: Chào mừng tới nền tảng video AI" }
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] bg-zinc-950/20 rounded-2xl border border-white/5 overflow-hidden">
      {/* Khung tin nhắn */}
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

              {/* Bong bóng tin nhắn */}
              <div className="space-y-1 group relative">
                <div
                  className={cn(
                    "p-3.5 rounded-2xl text-xs leading-relaxed border whitespace-pre-wrap",
                    isAI
                      ? "bg-white/5 border-white/10 text-white/95 rounded-tl-none"
                      : "bg-primary/10 border-primary/30 text-white rounded-tr-none"
                  )}
                >
                  {msg.text}
                </div>

                {/* Nút Copy nhanh cho câu trả lời của AI */}
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

        {/* Trạng thái AI đang soạn tin nhắn */}
        {isTyping && (
          <div className="flex gap-3 max-w-[80%] self-start animate-pulse">
            <div className="w-8 h-8 rounded-full bg-primary/20 border border-primary/40 text-primary flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-white/5 border border-white/10 p-4 rounded-2xl rounded-tl-none flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce delay-75"></span>
              <span className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce delay-150"></span>
              <span className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce delay-225"></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Gợi ý Prompt nhanh */}
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

      {/* Nhập tin nhắn ở đáy */}
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
