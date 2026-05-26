# Kế Hoạch Kỹ Thuật Giai Đoạn 1: Nâng Cấp Tiền Sản Xuất (Pre-Production)

Tài liệu này đặc tả chi tiết các bước lập trình (Implementation Plan) để nâng cấp AI Leader Agent (`worker_agent`) theo kiến trúc **Decoupled Routing (Định tuyến phân tách)** và **Plan-Act Loop**.

---

## 1. Nâng Cấp System Prompt (`leader_system_prompt.txt`)

*Tư duy: Tách biệt việc chọn Format (dựa trên hành động) và việc tinh chỉnh Nội dung/Pacing (dựa trên Phễu TMCP).*
```text
[VAI TRÒ CỦA BẠN]
Bạn là Giám đốc Sáng tạo (Creative Director) & Chuyên gia Tâm lý học hành vi. 
Nhiệm vụ: Đọc Content Briefs từ TMCP và sản xuất cấu hình video.

[BƯỚC 1: CHỌN ĐỊNH DẠNG (FORMAT ROUTING)]
Dựa vào *Hành động/Hình ảnh* trong kịch bản để chọn `worker_type`:
- Hành động mở hộp, giật gân -> `unbox_viral`
- Phân tích, so sánh, B-roll -> `review`
- Danh sách tĩnh, catalog, thông số -> `slideshow`

[BƯỚC 2: BƠM CẢM XÚC PHỄU (FUNNEL INJECTION)]
Tùy chỉnh `text_overlay` và `pacing` (nhịp độ) của bản `viral_optimized` theo Phễu:
1. AWARENESS/FEAR: Cắt cảnh cực nhanh (fast cut). Text overlay phải là một câu giật tít sốc ở 3s đầu. Tận dụng tối đa "Tóm tắt nội dung chính (Master Brief)" để viết câu Hook đánh thẳng vào nỗi đau.
2. CONSIDERATION/RETENTION: Nhịp độ trung bình. Dùng "Master Brief" làm khung sườn để giải thích Key Message rõ ràng, xây dựng niềm tin.
3. CONVERSION: Giữ khung hình tĩnh đủ lâu để đọc thông số. Đoạn Outro phải có CTA khổng lồ.

[CẤU TRÚC JSON ĐẦU RA YÊU CẦU]
{
  "worker_type": "review",
  "ai_metadata": {
      "hook_score": 8,
      "seo_titles": [],
      "qa_warnings": []
  },
  "draft_variants": {
      "original": { ... }, // Giữ nguyên kịch bản gốc
      "viral_optimized": { ... } // Tối ưu theo phễu
  }
}
```

---

## 2. Tái Cấu Trúc Backend (`agent_runner.py`)

Sử dụng **SmolAgents** để tạo vòng lặp tự sửa lỗi (Plan-Act Loop):

```python
# 1. Trích xuất Phễu và Master Brief từ Webhook TMCP
funnel_stage = payload.get("funnel_stage", "Unknown") 
psych_angle = payload.get("psych_angle", "") 
master_contents_brief = payload.get("master_contents_brief", "")

user_content = (
    f"--- CONTENT BRIEFS TỪ TMCP ---\n"
    f"- Phễu: {funnel_stage} | Tâm lý: {psych_angle}\n"
    f"- Tóm tắt nội dung chính (Master Brief): {master_contents_brief}\n"
    f"- Kịch bản: {script_content}\n"
)

# 2. Tool kiểm tra độ dài chữ / thời gian
@tool
def validate_video_pacing(timeline_script_str: str) -> str:
    # Quét JSON, báo lỗi cho LLM nếu > 4.5 từ/giây. Yêu cầu LLM chia đôi cảnh.
    ...

# 3. Agent Loop
agent = CodeAgent(tools=[validate_video_pacing], model=OpenAIServerModel(...), max_steps=3)
result_raw = agent.run(user_content)
```

---

## 3. Thiết Kế Database Chuẩn Hóa (Clean Database Schema)

**Tuyệt đối không nhồi nhét (overload) dữ liệu.** Chúng ta sẽ cập nhật `shared_core/models.py` (Bảng `video_jobs`) với các cột minh bạch:

```python
# Trích xuất từ shared_core/models.py
class VideoJob(Base):
    __tablename__ = "video_jobs"
    
    job_type = Column(String) 
    
    # 1. AI ANALYSIS: Lưu điểm số, SEO, cảnh báo
    ai_metadata = Column(FlexibleJSON, nullable=True) 

    # 2. NGUỒN GỐC: Lưu payload nguyên bản từ TMCP
    tmcp_source_config = Column(FlexibleJSON, nullable=True)

    # 3. CÁC BẢN NHÁP: { "original": {...}, "viral_optimized": {...} }
    draft_variants = Column(FlexibleJSON, nullable=True)

    # 4. CẤU HÌNH RENDER CUỐI CÙNG: Dành riêng cho Celery Worker đọc!
    config_data = Column(FlexibleJSON, nullable=True)
```

**Quy trình chuẩn hóa:**
1. **Leader Agent** ghi dữ liệu vào `ai_metadata`, `tmcp_source_config`, và `draft_variants`. Cột `config_data` tạm thời để trống (`null`).
2. **Frontend UI** tải `draft_variants` lên để người dùng chọn (Toggle) và chỉnh sửa.
3. Khi người dùng bấm **"Lưu / Chạy Job"**, Frontend gửi cấu hình đã chốt lên API, Backend sẽ lưu đè vào `config_data`.
4. **Celery Worker** (nhà máy) chỉ cần đọc `config_data` để render, không cần xử lý các logic nháp phức tạp.

---

## 4. Tích Hợp Frontend Admin UI (React Component Hóa)

Tạo một Component dùng chung `AIDraftPanel.tsx` thay vì code rải rác:

**1. Tạo Custom Hook: `useAIDraft.ts`**
```typescript
export function useAIDraft(job: VideoJobModel) {
    const hasDrafts = !!job.draft_variants;
    const [activeMode, setActiveMode] = useState<"original" | "viral_optimized">("original");

    // Lấy config từ draft_variants (nếu đang duyệt) hoặc fallback về config_data
    const currentConfig = hasDrafts ? job.draft_variants[activeMode] : job.config_data;
    
    return { hasDrafts, activeMode, setActiveMode, currentConfig, aiMetadata: job.ai_metadata };
}
```

**2. Tạo Reusable Component: `components/ui/AIDraftPanel.tsx`**
```tsx
import { Switch, Badge, Progress } from "lucide-react";

export function AIDraftPanel({ hasDrafts, activeMode, onToggle, metadata }) {
    if (!hasDrafts) return null;

    return (
        <div className="glass-panel p-4 mb-6 flex flex-col gap-4">
            {/* Phễu Marketing Badges */}
            <div className="flex gap-2">
                <Badge variant="outline">Stage: {metadata.funnel_stage}</Badge>
                <Badge variant="destructive">Angle: {metadata.psych_angle}</Badge>
            </div>

            {/* Hook Score */}
            <div className="flex items-center gap-4">
                <span className="text-sm">Điểm Hook: {metadata.hook_score}/10</span>
                <Progress value={metadata.hook_score * 10} color={metadata.hook_score >= 8 ? 'bg-green-500' : 'bg-yellow-500'} />
            </div>

            {/* SEO Panel */}
            {metadata.seo_titles && (
               <div className="text-sm text-muted-foreground">
                  <strong>SEO:</strong> {metadata.seo_titles.join(" | ")}
               </div>
            )}

            {/* Toggle Switch */}
            <div className="flex items-center gap-3">
                <span className={activeMode === "original" ? "text-primary font-bold" : ""}>Gốc (TMCP)</span>
                <Switch 
                   checked={activeMode === "viral_optimized"} 
                   onCheckedChange={(checked) => onToggle(checked ? "viral_optimized" : "original")} 
                />
                <span className={activeMode === "viral_optimized" ? "text-primary font-bold" : ""}>AI Viral (Phễu)</span>
            </div>
        </div>
    )
}
```

---

## 5. Tiêu Chuẩn Coding (Clean Code Standards)

### Backend (Python/FastAPI)
1. **S.O.L.I.D Principles:** Tách hàm `process_tmcp_webhook_impl` thành các helper riêng: `extract_tmcp_payload()`, `build_llm_prompt()`, và `save_job_variants()`.
2. **Strict Typing (Type Hinting):** Khai báo rõ ràng: `def heal_draft_parameters(worker_type: str, draft_params: Dict[str, Any]) -> Dict[str, Any]:`.
3. **Phòng thủ (Defensive Programming):** Luôn dùng `.get()` kết hợp với kiểu dữ liệu mặc định khi đọc JSON từ LLM.

### Frontend (React/TypeScript)
1. **DRY (Don't Repeat Yourself):** Tuyệt đối không copy-paste thanh UI hiển thị Điểm số sang 4 trang Job. Bắt buộc dùng Component `<AIDraftPanel />`.
2. **Interface Rõ Ràng:** Khai báo rõ interface cho Metadata mới:
   ```typescript
   interface AIMetadata {
       funnel_stage?: string;
       psych_angle?: string;
       hook_score: number;
       qa_warnings: string[];
       seo_titles?: string[];
   }
   ```