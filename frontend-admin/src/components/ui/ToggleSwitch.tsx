import { cn } from "../../lib/utils";

interface ToggleSwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label?: string;
}

export function ToggleSwitch({ checked, onChange, disabled, label }: ToggleSwitchProps) {
  return (
    <label className={cn("inline-flex items-center cursor-pointer", disabled && "opacity-50 cursor-not-allowed")}>
      <div className="relative">
        <input
          type="checkbox"
          className="sr-only"
          checked={checked}
          onChange={(e) => !disabled && onChange(e.target.checked)}
          disabled={disabled}
        />
        <div 
          className={cn(
            "w-11 h-6 rounded-full transition-colors duration-300 ease-in-out",
            checked ? "bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.4)]" : "bg-white/10"
          )}
        ></div>
        <div 
          className={cn(
            "absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition-transform duration-300 ease-in-out",
            checked ? "translate-x-5" : "translate-x-0"
          )}
        ></div>
      </div>
      {label && <span className="ml-3 text-sm font-medium text-white/80">{label}</span>}
    </label>
  );
}
