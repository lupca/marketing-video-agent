import React, { createContext, useContext, useState } from "react";

export interface AIStudioAddonContextType {
  isOpen: boolean;
  activeAddonId: string | null;
  initialData: any;
  openAddon: (addonId: string, initialData?: any) => void;
  closeAddon: () => void;
}

const AIStudioAddonContext = createContext<AIStudioAddonContextType | undefined>(undefined);

export function AIStudioAddonProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeAddonId, setActiveAddonId] = useState<string | null>(null);
  const [initialData, setInitialData] = useState<any>(null);

  const openAddon = (addonId: string, data?: any) => {
    setActiveAddonId(addonId);
    setInitialData(data || null);
    setIsOpen(true);
  };

  const closeAddon = () => {
    setIsOpen(false);
    // Trì hoãn việc xóa id hoạt động một chút để kịp thời gian chạy hiệu ứng trượt đóng của drawer
    setTimeout(() => {
      setActiveAddonId(null);
      setInitialData(null);
    }, 300);
  };

  return (
    <AIStudioAddonContext.Provider value={{ isOpen, activeAddonId, initialData, openAddon, closeAddon }}>
      {children}
    </AIStudioAddonContext.Provider>
  );
}

export function useAIStudioAddon() {
  const context = useContext(AIStudioAddonContext);
  if (!context) {
    throw new Error("useAIStudioAddon must be used within an AIStudioAddonProvider");
  }
  return context;
}
