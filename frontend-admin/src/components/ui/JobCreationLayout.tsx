import React, { useState } from "react";
import { Sparkles } from "lucide-react";
import { ProductionGuideDrawer } from "./ProductionGuideDrawer";
import { cn } from "../../lib/utils";

interface JobCreationLayoutProps {
  children: React.ReactNode;
  jobType: string;
  tmcpContext?: any;
}

export function JobCreationLayout({ children, jobType, tmcpContext }: JobCreationLayoutProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative min-h-screen">
      {/* 1. Main Page Form Content */}
      <div className="w-full">
        {children}
      </div>

      {/* 2. Floating Action Button with pulsing neon effect */}
      <button
        onClick={() => setIsOpen(true)}
        className={cn(
          "fixed bottom-8 right-8 z-40 flex items-center gap-2 rounded-full px-5 py-3.5 text-sm font-bold text-white shadow-lg transition-all hover:scale-105 focus:outline-none select-none",
          tmcpContext
            ? "bg-gradient-to-r from-cyan-500 via-indigo-500 to-fuchsia-600 shadow-[0_4px_20px_rgba(6,182,212,0.4)] hover:shadow-[0_4px_25px_rgba(6,182,212,0.6)]"
            : "bg-gradient-to-r from-violet-600 to-fuchsia-600 shadow-[0_4px_20px_rgba(124,58,237,0.4)] hover:shadow-[0_4px_25px_rgba(124,58,237,0.6)]"
        )}
      >
        <Sparkles className={cn("w-4 h-4", tmcpContext && "animate-spin-slow")} />
        {tmcpContext ? "Xem Kịch Bản & Hướng Dẫn" : "Hướng Dẫn Dựng Video"}
        
        {/* Pulsing neon notifications dot */}
        {tmcpContext && (
          <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-cyan-500 border border-white/20"></span>
          </span>
        )}
      </button>

      {/* 3. Production Guide Drawer */}
      <ProductionGuideDrawer
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        jobType={jobType}
        tmcpContext={tmcpContext}
      />
    </div>
  );
}
