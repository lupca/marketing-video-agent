import type { Asset } from "../../../hooks/useAssets";

export interface UploadedFile {
  file?: File;
  asset?: Asset;
  id: string | null;
  s3_url: string | null;
  uploading: boolean;
  progress: number;
}

export interface Segment {
  name: string;
  label: string;
  timeStart: number;
  timeEnd: number;
  clips: UploadedFile[];
  textOverlay: string;
  highlightWords: string;
  effects: string[];
  pacingMin: number;
  pacingMax: number;
}
