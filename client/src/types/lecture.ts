export const FrameAction = {
  RENDER_TEXT_ONLY: 0,
  INJECT_NEW_VECTOR: 1,
  ANIMATE_EXISTING_VECTOR: 2,
  CLEAR_CANVAS_RESET: 3,
} as const;

export type FrameAction = (typeof FrameAction)[keyof typeof FrameAction];

export interface LectureFrame {
  timestampSeconds: number;
  spokenText: string;
  actionType: FrameAction | number;
  svgPayload: string;
  visualEngine?: 'mermaid' | 'd3' | 'svg' | 'manim' | string;
  chapterTitle?: string;
  spokenTextHi?: string;
  chapterTitleHi?: string;
}

export interface LecturePayload {
  lectureId: string;
  topicTitle: string;
  sourceVideoUrl?: string;
  sourceType?: 'youtube' | 'json_file';
  targetDurationSeconds?: number;
  frames: LectureFrame[];
}

export interface SavedLectureMetadata {
  id: string;
  title: string;
  sourceVideoUrl?: string;
  sourceType?: 'youtube' | 'json_file';
  frameCount: number;
  durationSeconds: number;
  binarySizeBytes: number;
  mp4EquivalentBytes: number;
  compressionRatio: number;
  createdAt: string;
  isCustom?: boolean;
}

export interface SavedLecture extends SavedLectureMetadata {
  binaryBlob: ArrayBuffer;
}
