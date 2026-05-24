import { useAIStudioAddon } from "../../../context/AIStudioAddonContext";
import { AI_ADDONS } from "./addonConfig";
import { cn } from "../../../lib/utils";

export default function AIAddonDock() {
  const { isOpen, activeAddonId, openAddon, closeAddon } = useAIStudioAddon();

  const handleAddonClick = (addonId: string) => {
    if (isOpen && activeAddonId === addonId) {
      closeAddon();
    } else {
      openAddon(addonId);
    }
  };

  return (
    <div 
      className="fixed right-4 top-1/2 -translate-y-1/2 flex flex-col items-center gap-4 z-40 bg-black/40 border border-white/10 p-3 rounded-2xl backdrop-blur-xl shadow-[0_12px_48px_rgba(0,0,0,0.4)] animate-in fade-in slide-in-from-right-4 duration-500 select-none"
    >
      {/* Chỉ báo tiêu đề nhỏ tinh tế của Dock */}
      <div className="text-[7.5px] uppercase font-extrabold tracking-widest text-muted-foreground/60 -rotate-90 py-3 shrink-0">
        AI DOCK
      </div>

      {/* Danh sách các biểu tượng Addon */}
      {AI_ADDONS.map((addon) => {
        const Icon = addon.icon;
        const isSelected = isOpen && activeAddonId === addon.id;

        return (
          <button
            key={addon.id}
            onClick={() => handleAddonClick(addon.id)}
            className={cn(
              "w-10 h-10 rounded-xl flex items-center justify-center relative group transition-all duration-300 ease-out cursor-pointer border",
              isSelected
                ? "bg-primary text-white border-primary/50 shadow-[0_0_20px_rgba(124,58,237,0.6)] scale-110"
                : "bg-white/5 border-white/5 hover:border-white/20 text-muted-foreground hover:text-white hover:scale-110 active:scale-95"
            )}
            title={addon.name}
          >
            <Icon className={cn("w-5 h-5 transition-transform group-hover:rotate-6", isSelected && "animate-pulse")} />
            
            {/* Tooltip nổi sang bên trái */}
            <div 
              className="absolute right-full mr-4 top-1/2 -translate-y-1/2 px-3 py-2 bg-black/95 backdrop-blur-xl border border-white/10 rounded-xl text-[10px] text-white shadow-2xl opacity-0 scale-95 pointer-events-none group-hover:opacity-100 group-hover:scale-100 transition-all duration-200 whitespace-nowrap z-50 flex flex-col items-start gap-0.5 origin-right"
            >
              <h5 className="font-extrabold text-white flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-primary shadow-[0_0_4px_rgba(124,58,237,0.8)]"></span>
                {addon.name}
              </h5>
              <span className="text-[8.5px] text-muted-foreground font-normal">{addon.description}</span>
            </div>

            {/* Chỉ báo chấm tròn nhỏ phát sáng cho Addon đang chọn */}
            {isSelected && (
              <span className="absolute -bottom-0.5 w-1.5 h-1.5 bg-white rounded-full shadow-[0_0_8px_white] animate-pulse"></span>
            )}
          </button>
        );
      })}
    </div>
  );
}
