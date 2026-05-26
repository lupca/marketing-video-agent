import { useState } from "react";

export interface AIMetadata {
  funnel_stage?: string;
  psych_angle?: string;
  hook_score: number;
  qa_warnings: string[];
  seo_titles?: string[];
  content_brief_context?: {
    angle_name?: string;
    funnel_stage?: string;
    psychological_angle?: string;
    pain_point_focus?: string;
    key_message_variation?: string;
    call_to_action_direction?: string;
    brief?: string;
  };
}

export function useAIDraft(job: any) {
  const hasDrafts = !!(job && job.draft_variants);
  const [activeMode, setActiveMode] = useState<"original" | "viral_optimized">("original");

  // Get config from draft_variants if we have them, fallback to config_data
  const currentConfig = hasDrafts && job.draft_variants ? job.draft_variants[activeMode] : (job ? job.config_data : null);

  return {
    hasDrafts,
    activeMode,
    setActiveMode,
    currentConfig,
    aiMetadata: job ? (job.ai_metadata as AIMetadata) : undefined,
  };
}
