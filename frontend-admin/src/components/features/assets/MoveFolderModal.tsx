import React, { useState, useMemo } from "react";
import { Folder, Home, FolderSymlink } from "lucide-react";
import { Modal } from "../../ui/Modal";
import { Button } from "../../ui/Button";
import type { Folder as FolderType } from "../../../hooks/useAssets";

interface MoveFolderModalProps {
  isOpen: boolean;
  onClose: () => void;
  folders: FolderType[];
  movingItem: {
    type: "file" | "folder";
    id: string;
    name: string;
    parent_id?: string | null;
    folder_id?: string | null;
  } | null;
  onMove: (targetFolderId: string | null) => Promise<void>;
}

export function MoveFolderModal({ isOpen, onClose, folders, movingItem, onMove }: MoveFolderModalProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Flatten the folders into a nested visual hierarchy
  const nestedFolderList = useMemo(() => {
    if (!movingItem) return [];

    const getNestedFolders = (
      parentId: string | null,
      allFolders: FolderType[],
      depth = 0
    ): Array<{ folder: FolderType; depth: number }> => {
      const list: Array<{ folder: FolderType; depth: number }> = [];
      
      // Filter direct children and sort alphabetically
      const directChildren = allFolders
        .filter(f => {
          // If parentId is null/undefined, filter parent_id == null
          if (!parentId) return !f.parent_id;
          return f.parent_id === parentId;
        })
        .sort((a, b) => a.name.localeCompare(b.name));

      directChildren.forEach(child => {
        // Prevent moving a folder into itself
        if (movingItem.type === "folder" && child.id === movingItem.id) {
          return;
        }
        
        // Prevent moving a folder into its own descendants to avoid cyclic redundancy
        // (A folder cannot be moved inside its child folder)
        const isDescendantOfMovingFolder = (folderId: string): boolean => {
          if (movingItem.type !== "folder") return false;
          let curr = allFolders.find(f => f.id === folderId);
          while (curr && curr.parent_id) {
            if (curr.parent_id === movingItem.id) return true;
            curr = allFolders.find(f => f.id === curr.parent_id);
          }
          return false;
        };

        if (isDescendantOfMovingFolder(child.id)) {
          return;
        }

        list.push({ folder: child, depth });
        list.push(...getNestedFolders(child.id, allFolders, depth + 1));
      });
      return list;
    };

    return getNestedFolders(null, folders);
  }, [folders, movingItem]);

  const handleMove = async () => {
    if (!movingItem) return;
    setLoading(true);
    try {
      await onMove(selectedId);
      onClose();
    } catch (err) {
      console.error(err);
      alert("Failed to move item");
    } finally {
      setLoading(false);
    }
  };

  if (!movingItem) return null;

  // Active parent folder of moving item
  const currentParentId = movingItem.type === "folder" ? movingItem.parent_id : movingItem.folder_id;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2 text-white font-semibold">
          <FolderSymlink className="w-5 h-5 text-primary" />
          <span>Move "{movingItem.name}"</span>
        </div>
      }
      maxWidth="md"
    >
      <div className="p-6 space-y-6 bg-[#0a0a09]/95 text-white/90">
        <p className="text-sm text-muted-foreground">
          Select a destination folder for this {movingItem.type}.
        </p>

        {/* Directory List Container */}
        <div className="max-h-[300px] overflow-y-auto border border-white/10 rounded-xl bg-black/45 p-2 custom-scrollbar space-y-1">
          {/* Home / Root Node */}
          <button
            onClick={() => setSelectedId(null)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left text-sm font-medium transition-all ${
              selectedId === null
                ? "bg-primary/20 text-primary border border-primary/30"
                : "hover:bg-white/5 text-white/80 border border-transparent"
            }`}
          >
            <Home className="w-4 h-4" />
            <span>Home (My Files)</span>
            {currentParentId === null && (
              <span className="ml-auto text-[10px] text-muted-foreground/60 italic font-normal">
                Currently here
              </span>
            )}
          </button>

          {/* Render nested directory tree */}
          {nestedFolderList.length === 0 ? (
            <div className="py-8 text-center text-xs text-muted-foreground italic">
              No custom folders created yet.
            </div>
          ) : (
            nestedFolderList.map(({ folder, depth }) => (
              <button
                key={folder.id}
                onClick={() => setSelectedId(folder.id)}
                style={{ paddingLeft: `${(depth + 1) * 16}px` }}
                className={`w-full flex items-center gap-3 py-2.5 pr-3 rounded-lg text-left text-sm font-medium transition-all border ${
                  selectedId === folder.id
                    ? "bg-primary/20 text-primary border-primary/30"
                    : "hover:bg-white/5 text-white/80 border-transparent"
                }`}
              >
                <Folder className={`w-4 h-4 ${folder.is_job_folder ? "text-amber-400 fill-amber-400/10" : "text-indigo-400 fill-indigo-400/10"}`} />
                <span className="truncate">{folder.name}</span>
                {currentParentId === folder.id && (
                  <span className="ml-auto text-[10px] text-muted-foreground/60 italic font-normal shrink-0">
                    Currently here
                  </span>
                )}
              </button>
            ))
          )}
        </div>

        {/* Modal Buttons */}
        <div className="flex items-center justify-end gap-3 border-t border-white/10 pt-4">
          <Button onClick={onClose} variant="secondary">
            Cancel
          </Button>
          <Button
            onClick={handleMove}
            disabled={loading || selectedId === currentParentId}
            isLoading={loading}
            className="glowing-button pr-6 pl-6"
          >
            Move Here
          </Button>
        </div>
      </div>
    </Modal>
  );
}
