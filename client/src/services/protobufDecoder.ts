import protobuf from 'protobufjs';
import type { LecturePayload } from '../types/lecture';

// Embedded protobuf schema guarantees instant, 100% offline compilation and zero network dependency
export const PROTO_SCHEMA = `
syntax = "proto3";

package byteclass;

message LecturePayload {
  string lecture_id = 1;
  string topic_title = 2;
  repeated LectureFrame frames = 3;
  string source_video_url = 4;
}

message LectureFrame {
  float timestamp_seconds = 1;
  string spoken_text = 2;
  FrameAction action_type = 3;
  string svg_payload = 4;
  string visual_engine = 5;
  string chapter_title = 6;
  string spoken_text_hi = 7;
  string chapter_title_hi = 8;
}

enum FrameAction {
  RENDER_TEXT_ONLY = 0;
  INJECT_NEW_VECTOR = 1;
  ANIMATE_EXISTING_VECTOR = 2;
  CLEAR_CANVAS_RESET = 3;
}
`;

let rootInstance: protobuf.Root | null = null;
let lecturePayloadType: protobuf.Type | null = null;

function getLecturePayloadType(): protobuf.Type {
  if (!lecturePayloadType) {
    rootInstance = protobuf.parse(PROTO_SCHEMA).root;
    lecturePayloadType = rootInstance.lookupType('byteclass.LecturePayload');
  }
  return lecturePayloadType;
}

/**
 * Deserializes a binary byte array (.bin Protobuf payload) back into a LecturePayload object
 */
export function deserializeLectureBinary(buffer: ArrayBuffer | Uint8Array): LecturePayload {
  const type = getLecturePayloadType();
  const uint8 = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  const message = type.decode(uint8);
  const object = type.toObject(message, {
    enums: Number,
    longs: Number,
    defaults: true,
  });

  const sourceUrl = object.sourceVideoUrl || object.source_video_url || '';

  return {
    lectureId: object.lectureId || object.lecture_id || 'unknown-id',
    topicTitle: object.topicTitle || object.topic_title || 'Untitled Lecture',
    sourceVideoUrl: sourceUrl,
    sourceType: sourceUrl ? 'youtube' : 'json_file',
    frames: (object.frames || []).map((f: any) => ({
      timestampSeconds: f.timestampSeconds ?? f.timestamp_seconds ?? 0,
      spokenText: f.spokenText ?? f.spoken_text ?? '',
      actionType: f.actionType ?? f.action_type ?? 0,
      svgPayload: f.svgPayload ?? f.svg_payload ?? '',
      visualEngine: f.visualEngine ?? f.visual_engine ?? '',
      chapterTitle: f.chapterTitle ?? f.chapter_title ?? '',
      spokenTextHi: f.spokenTextHi ?? f.spoken_text_hi ?? '',
      chapterTitleHi: f.chapterTitleHi ?? f.chapter_title_hi ?? '',
    })),
  };
}

/**
 * Serializes a LecturePayload JavaScript object into a compressed binary Uint8Array (.bin Protobuf payload)
 */
export function serializeLectureBinary(payload: LecturePayload): Uint8Array {
  const type = getLecturePayloadType();
  const protoObject = {
    lecture_id: payload.lectureId,
    topic_title: payload.topicTitle,
    source_video_url: payload.sourceVideoUrl || '',
    frames: payload.frames.map((f) => ({
      timestamp_seconds: f.timestampSeconds,
      spoken_text: f.spokenText,
      action_type: f.actionType,
      svg_payload: f.svgPayload,
      visual_engine: f.visualEngine || '',
      chapter_title: f.chapterTitle || '',
      spoken_text_hi: f.spokenTextHi || '',
      chapter_title_hi: f.chapterTitleHi || '',
    })),
  };

  const errMsg = type.verify(protoObject);
  if (errMsg) {
    throw new Error(`Protobuf validation error: ${errMsg}`);
  }

  const message = type.create(protoObject);
  return type.encode(message).finish();
}
