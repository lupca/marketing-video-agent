import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "../../lib/utils";

interface PaginationProps {
  currentPage: number;
  totalItems: number;
  itemsPerPage: number;
  onPageChange: (page: number) => void;
  onItemsPerPageChange?: (size: number) => void;
  className?: string;
}

export function Pagination({
  currentPage,
  totalItems,
  itemsPerPage,
  onPageChange,
  onItemsPerPageChange,
  className,
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(totalItems / itemsPerPage));

  // Reset page if it exceeds total pages
  if (currentPage > totalPages && totalPages > 0) {
    onPageChange(totalPages);
  }

  const getPageNumbers = () => {
    const siblingCount = 1;
    // We want to show: First, Last, Current, 1 sibling on each side, and dots
    const totalPageNumbers = siblingCount * 2 + 5; 

    if (totalPages <= totalPageNumbers) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }

    const leftSiblingIndex = Math.max(currentPage - siblingCount, 1);
    const rightSiblingIndex = Math.min(currentPage + siblingCount, totalPages);

    const shouldShowLeftDots = leftSiblingIndex > 2;
    const shouldShowRightDots = rightSiblingIndex < totalPages - 1;

    if (!shouldShowLeftDots && shouldShowRightDots) {
      const leftItemCount = 3 + 2 * siblingCount;
      const leftRange = Array.from({ length: leftItemCount }, (_, i) => i + 1);
      return [...leftRange, "dots", totalPages];
    }

    if (shouldShowLeftDots && !shouldShowRightDots) {
      const rightItemCount = 3 + 2 * siblingCount;
      const rightRange = Array.from({ length: rightItemCount }, (_, i) => totalPages - rightItemCount + i + 1);
      return [1, "dots", ...rightRange];
    }

    if (shouldShowLeftDots && shouldShowRightDots) {
      const middleRange = Array.from({ length: rightSiblingIndex - leftSiblingIndex + 1 }, (_, i) => leftSiblingIndex + i);
      return [1, "dots", ...middleRange, "dots", totalPages];
    }

    return [];
  };

  const pages = getPageNumbers();
  const startItemIndex = totalItems === 0 ? 0 : (currentPage - 1) * itemsPerPage + 1;
  const endItemIndex = Math.min(currentPage * itemsPerPage, totalItems);

  return (
    <div
      className={cn(
        "flex flex-col sm:flex-row items-center justify-between gap-4 px-6 py-4 bg-black/30 backdrop-blur-md border border-white/5 rounded-2xl shadow-[0_8px_32px_rgba(0,0,0,0.3)] animate-in fade-in duration-300",
        className
      )}
    >
      {/* Left side: Range indicators */}
      <div className="text-sm text-muted-foreground text-center sm:text-left">
        Đang hiển thị <span className="font-semibold text-white">{startItemIndex}</span> đến{" "}
        <span className="font-semibold text-white">{endItemIndex}</span> trong tổng số{" "}
        <span className="font-semibold text-primary">{totalItems}</span> bản ghi
      </div>

      {/* Right side: Controls */}
      <div className="flex flex-wrap items-center justify-center gap-4">
        {/* Items per page selector */}
        {onItemsPerPageChange && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground whitespace-nowrap">Hiển thị:</span>
            <select
              title="Số bản ghi mỗi trang"
              value={itemsPerPage}
              onChange={(e) => {
                onItemsPerPageChange(Number(e.target.value));
                onPageChange(1); // Reset to page 1
              }}
              className="bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl px-2.5 py-1.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-primary/50 cursor-pointer transition-all"
            >
              {[10, 20, 50, 100].map((size) => (
                <option key={size} value={size} className="bg-[#12121A] text-white">
                  {size} dòng
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Page buttons */}
        <div className="flex items-center gap-1.5 bg-black/20 p-1 rounded-xl border border-white/5">
          {/* Previous page button */}
          <button
            title="Trang trước"
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage === 1}
            className="p-2 rounded-lg text-muted-foreground hover:text-white hover:bg-white/10 disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-muted-foreground disabled:cursor-not-allowed transition-all active:scale-95 duration-150"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          {/* Page numbers */}
          {pages.map((page, index) => {
            if (page === "dots") {
              return (
                <span
                  key={`dots-${index}`}
                  className="px-2.5 py-1.5 text-sm text-muted-foreground select-none"
                >
                  ...
                </span>
              );
            }

            const isCurrent = page === currentPage;
            return (
              <button
                key={`page-${page}`}
                onClick={() => onPageChange(Number(page))}
                className={cn(
                  "min-w-[34px] px-2.5 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 active:scale-95",
                  isCurrent
                    ? "bg-primary text-white shadow-[0_0_12px_rgba(124,58,237,0.4)] font-bold scale-105"
                    : "text-muted-foreground hover:text-white hover:bg-white/5"
                )}
              >
                {page}
              </button>
            );
          })}

          {/* Next page button */}
          <button
            title="Trang sau"
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage === totalPages}
            className="p-2 rounded-lg text-muted-foreground hover:text-white hover:bg-white/10 disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-muted-foreground disabled:cursor-not-allowed transition-all active:scale-95 duration-150"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
