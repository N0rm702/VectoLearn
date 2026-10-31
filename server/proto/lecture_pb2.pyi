from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class FrameAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RENDER_TEXT_ONLY: _ClassVar[FrameAction]
    INJECT_NEW_VECTOR: _ClassVar[FrameAction]
    ANIMATE_EXISTING_VECTOR: _ClassVar[FrameAction]
    CLEAR_CANVAS_RESET: _ClassVar[FrameAction]
RENDER_TEXT_ONLY: FrameAction
INJECT_NEW_VECTOR: FrameAction
ANIMATE_EXISTING_VECTOR: FrameAction
CLEAR_CANVAS_RESET: FrameAction

class LecturePayload(_message.Message):
    __slots__ = ("lecture_id", "topic_title", "frames", "source_video_url")
    LECTURE_ID_FIELD_NUMBER: _ClassVar[int]
    TOPIC_TITLE_FIELD_NUMBER: _ClassVar[int]
    FRAMES_FIELD_NUMBER: _ClassVar[int]
    SOURCE_VIDEO_URL_FIELD_NUMBER: _ClassVar[int]
    lecture_id: str
    topic_title: str
    frames: _containers.RepeatedCompositeFieldContainer[LectureFrame]
    source_video_url: str
    def __init__(self, lecture_id: _Optional[str] = ..., topic_title: _Optional[str] = ..., frames: _Optional[_Iterable[_Union[LectureFrame, _Mapping]]] = ..., source_video_url: _Optional[str] = ...) -> None: ...

class LectureFrame(_message.Message):
    __slots__ = ("timestamp_seconds", "spoken_text", "action_type", "svg_payload")
    TIMESTAMP_SECONDS_FIELD_NUMBER: _ClassVar[int]
    SPOKEN_TEXT_FIELD_NUMBER: _ClassVar[int]
    ACTION_TYPE_FIELD_NUMBER: _ClassVar[int]
    SVG_PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    timestamp_seconds: float
    spoken_text: str
    action_type: FrameAction
    svg_payload: str
    def __init__(self, timestamp_seconds: _Optional[float] = ..., spoken_text: _Optional[str] = ..., action_type: _Optional[_Union[FrameAction, str]] = ..., svg_payload: _Optional[str] = ...) -> None: ...
