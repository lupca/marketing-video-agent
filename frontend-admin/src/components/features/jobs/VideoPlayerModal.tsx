import { Modal } from "../../ui/Modal";
import { PlayCircle } from "lucide-react";

interface VideoPlayerModalProps {
  url: string;
  onClose: () => void;
}

export function VideoPlayerModal({ url, onClose }: VideoPlayerModalProps) {
  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      maxWidth="4xl"
      title={
        <div className="flex items-center gap-2">
          <PlayCircle className="w-5 h-5 text-primary" /> Watch Video
        </div>
      }
    >
      <div className="p-4 bg-[#0D0D12] rounded-b-xl border-t border-white/10 flex items-center justify-center min-h-[50vh]">
        <video
          src={url}
          controls
          autoPlay
          className="max-h-[75vh] max-w-full rounded-lg shadow-2xl bg-black border border-white/10 outline-none ring-primary/50 focus:ring-2 transition-all"
        />
      </div>
    </Modal>
  );
}
