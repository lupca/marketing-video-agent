import { useEffect } from "react";
import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  className?: string;
  maxWidth?: "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl" | "5xl" | "6xl" | "full";
}

export function Modal({ isOpen, onClose, title, children, className, maxWidth = "md" }: ModalProps) {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      document.addEventListener("keydown", handleEsc);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleEsc);
      document.body.style.overflow = "auto";
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const maxWidthClass = {
    "sm": "max-w-sm",
    "md": "max-w-md",
    "lg": "max-w-lg",
    "xl": "max-w-xl",
    "2xl": "max-w-2xl",
    "3xl": "max-w-3xl",
    "4xl": "max-w-4xl",
    "5xl": "max-w-5xl",
    "6xl": "max-w-6xl",
    "full": "max-w-[90vw] h-[90vh]",
  }[maxWidth];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className={cn(
        "glass-panel w-full flex flex-col animate-in zoom-in-95 duration-200 overflow-hidden border border-white/10 shadow-[0_0_40px_rgba(0,0,0,0.5)] rounded-2xl",
        maxWidthClass,
        className
      )}>
        {true && (
          <div className="flex items-center justify-between p-4 border-b border-white/10 bg-black/20">
            {title && typeof title === "string" ? (
              <h3 className="text-lg font-semibold">{title}</h3>
            ) : title}
            <button
              onClick={onClose}
              className="text-muted-foreground hover:text-white p-2 ml-auto rounded-lg hover:bg-white/5 transition-colors"
            >
              ✕
            </button>
          </div>
        )}
        <div className="flex-1 overflow-auto custom-scrollbar">
          {children}
        </div>
      </div>
    </div>
  );
}
