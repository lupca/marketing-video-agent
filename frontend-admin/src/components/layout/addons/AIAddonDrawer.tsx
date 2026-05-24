import { X } from "lucide-react";
import { useAIStudioAddon } from "../../../context/AIStudioAddonContext";
import { AI_ADDONS } from "./addonConfig";
import { cn } from "../../../lib/utils";

export default function AIAddonDrawer() {
  const { isOpen, activeAddonId, closeAddon, openAddon } = useAIStudioAddon();

  // Tìm kiếm Addon đang hoạt động
  const activeAddon = AI_ADDONS.find((a) => a.id === activeAddonId);
  const ActiveComponent = activeAddon?.component || null;

  return (
    <>
      {/* Lớp nền mờ tối (Backdrop Overlay) khi Drawer mở */}
      {isOpen && (
        <div 
          onClick={closeAddon}
          className="fixed inset-0 bg-black/25 backdrop-blur-xs z-40 transition-opacity duration-300 animate-in fade-in"
        />
      )}

      {/* Ngăn kéo trượt Slide-over Drawer */}
      <div
        className={cn(
          "fixed right-0 top-0 h-screen w-[420px] bg-black/70 border-l border-white/10 shadow-[-10px_0_40px_rgba(0,0,0,0.6)] z-50 transition-all duration-300 ease-out transform flex flex-col backdrop-blur-3xl select-none",
          isOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        {/* Header của Drawer */}
        {activeAddon && (
          <div className="p-5 border-b border-white/10 shrink-0 space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary/20 rounded-xl text-primary border border-primary/20 animate-pulse">
                  <activeAddon.icon className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-extrabold text-white tracking-tight">{activeAddon.name} Addon</h3>
                  <p className="text-[10px] text-muted-foreground mt-0.5 leading-tight">{activeAddon.description}</p>
                </div>
              </div>

              {/* Nút đóng */}
              <button
                onClick={closeAddon}
                className="p-1.5 hover:bg-white/5 hover:text-white text-muted-foreground/60 rounded-lg transition-colors cursor-pointer"
                title="Đóng bảng hỗ trợ"
              >
                <X className="w-4.5 h-4.5" />
              </button>
            </div>

            {/* Quick Switcher: Cho phép chuyển nhanh giữa các Addon trực tiếp trong Drawer */}
            <div className="flex items-center gap-2 bg-white/5 p-1 rounded-xl border border-white/5 w-fit">
              {AI_ADDONS.map((addon) => {
                const Icon = addon.icon;
                const isSelected = addon.id === activeAddonId;

                return (
                  <button
                    key={addon.id}
                    onClick={() => openAddon(addon.id)}
                    className={cn(
                      "p-1.5 rounded-lg transition-all text-xs font-bold flex items-center gap-1 cursor-pointer",
                      isSelected
                        ? "bg-primary text-white shadow-sm"
                        : "text-muted-foreground/75 hover:text-white hover:bg-white/5"
                    )}
                    title={addon.name}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span className="text-[9px] font-bold uppercase tracking-wider px-0.5">{addon.name.split(" ")[0]}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Body của Drawer (Chứa Widget tương ứng) */}
        <div className="flex-1 p-5 overflow-y-auto custom-scrollbar">
          {ActiveComponent && (
            <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
              <ActiveComponent />
            </div>
          )}
        </div>
      </div>
    </>
  );
}
