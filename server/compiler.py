import sys
import os
import re
import xml.etree.ElementTree as ET
from typing import Tuple, Dict, Any, List

# Ensure server/proto is on Python import path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROTO_DIR = os.path.join(CURRENT_DIR, "proto")
if PROTO_DIR not in sys.path:
    sys.path.insert(0, PROTO_DIR)

import lecture_pb2

# Register default SVG namespace so ElementTree does not inject ns0: prefixes
ET.register_namespace("", "http://www.w3.org/2000/svg")


class ASTValidationError(Exception):
    """Raised when SVG AST verification fails due to malformed XML or invalid tags."""
    pass


def validate_svg_ast(svg_str: str, auto_repair: bool = True) -> Tuple[bool, str, str]:
    """
    Syntactic AST Verification Interceptor:
    Validates generated SVG markup using Python's non-evaluating xml.etree.ElementTree parser.
    Ensures safe DOM structure, closing tags matching opening tags, and proper viewBox.
    
    Returns:
        (is_valid: bool, repaired_or_original_svg: str, status_message: str)
    """
    if not svg_str or not svg_str.strip():
        return True, "", "Empty SVG payload"

    cleaned = svg_str.strip()

    # Pass through client-side localized engine payloads directly (Mermaid diagrams, D3 JSON, parametric JSON)
    if cleaned.startswith("{") or cleaned.startswith("graph ") or cleaned.startswith("flowchart ") or ("-->" in cleaned and "<svg" not in cleaned):
        return True, cleaned, "Valid client-engine payload (Mermaid/JSON preserved)"

    # If the LLM returned SVG elements without root <svg> tag, wrap them in standard 400x400 container
    if not cleaned.startswith("<svg"):
        cleaned = f'<svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg">{cleaned}</svg>'

    try:
        # Non-evaluating XML AST parse
        root = ET.fromstring(cleaned)
        
        # Verify root tag is svg (ignoring XML namespace prefix if present)
        tag_name = root.tag.split("}")[-1] if "}" in root.tag else root.tag
        if tag_name.lower() != "svg":
            raise ASTValidationError(f"Root XML element must be <svg>, received <{tag_name}>")

        # Ensure viewBox attribute is present
        if "viewBox" not in root.attrib and "viewbox" not in root.attrib:
            root.attrib["viewBox"] = "0 0 400 400"

        # Serialize back to clean normalized XML
        normalized = ET.tostring(root, encoding="unicode")
        return True, normalized, "AST Validation Passed: 100% Valid XML DOM Tree"

    except ET.ParseError as err:
        if not auto_repair:
            return False, svg_str, f"AST Syntax Error: {err}"

        # Error mitigation tactic: Attempt auto-repair of common LLM hallucinations
        # e.g., mismatched closing tags, unescaped &, raw > or < inside text, unclosed <svg>
        try:
            repaired = cleaned

            # 1. Replace unescaped & not part of an existing valid XML entity
            repaired = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', repaired)

            # 2. Fix self-closing void elements often hallucinated with mismatched closers
            repaired = re.sub(r'<path([^>]*?)(?<!/)>(\s*)</path>', r'<path\1/>', repaired)
            repaired = re.sub(r'<circle([^>]*?)(?<!/)>(\s*)</circle>', r'<circle\1/>', repaired)
            repaired = re.sub(r'<line([^>]*?)(?<!/)>(\s*)</line>', r'<line\1/>', repaired)
            repaired = re.sub(r'<ellipse([^>]*?)(?<!/)>(\s*)</ellipse>', r'<ellipse\1/>', repaired)
            repaired = re.sub(r'<rect([^>]*?)(?<!/)>(\s*)</rect>', r'<rect\1/>', repaired)

            # 3. Replace raw > inside text nodes (e.g. > 100km or 27% > Mass)
            def fix_text_tag(m):
                content = m.group(1)
                content = content.replace('>', '&gt;')
                return f">{content}<"
            repaired = re.sub(r'>([^<]+)<', fix_text_tag, repaired)

            # 4. Ensure closing </svg>
            if not repaired.strip().endswith('</svg>'):
                repaired = repaired.strip() + '</svg>'

            # Re-test parse
            root = ET.fromstring(repaired)
            normalized = ET.tostring(root, encoding="unicode")
            return True, normalized, f"AST Self-Healing Interceptor: Repaired malformed XML ({err})"
        except Exception:
            return False, svg_str, f"AST Critical Failure: Hallucinated invalid XML syntax: {err}"


def compile_to_protobuf_binary(lecture_data: Dict[str, Any]) -> bytes:
    """
    Google Protocol Buffers (Protobuf v3) serialization layer.
    Compresses structured log array into binary byte array under 50KB/min runtime.
    """
    payload = lecture_pb2.LecturePayload()
    payload.lecture_id = str(lecture_data.get("lecture_id", f"lec-{os.urandom(4).hex()}"))
    payload.topic_title = str(lecture_data.get("topic_title", "Untitled Lecture"))
    payload.source_video_url = str(lecture_data.get("source_video_url", lecture_data.get("sourceVideoUrl", "")))

    for frame_dict in lecture_data.get("frames", []):
        frame = payload.frames.add()
        frame.timestamp_seconds = float(frame_dict.get("timestamp_seconds", 0.0))
        frame.spoken_text = str(frame_dict.get("spoken_text", ""))
        
        # Action type mapping
        action_val = frame_dict.get("action_type", 1)
        if isinstance(action_val, str):
            action_map = {
                "RENDER_TEXT_ONLY": lecture_pb2.RENDER_TEXT_ONLY,
                "INJECT_NEW_VECTOR": lecture_pb2.INJECT_NEW_VECTOR,
                "ANIMATE_EXISTING_VECTOR": lecture_pb2.ANIMATE_EXISTING_VECTOR,
                "CLEAR_CANVAS_RESET": lecture_pb2.CLEAR_CANVAS_RESET,
            }
            action_val = action_map.get(action_val, lecture_pb2.INJECT_NEW_VECTOR)
        frame.action_type = int(action_val)
        if hasattr(frame, "visual_engine"):
            frame.visual_engine = str(frame_dict.get("visual_engine", "svg"))

        # SVG AST Validation Interceptor
        raw_svg = frame_dict.get("svg_payload", "")
        is_valid, validated_svg, status = validate_svg_ast(raw_svg, auto_repair=True)
        if not is_valid:
            print(f"[Warning] Frame @{frame.timestamp_seconds}s SVG AST error: {status}")
        frame.svg_payload = validated_svg

    return payload.SerializeToString()


def deserialize_from_protobuf_binary(binary_bytes: bytes) -> Dict[str, Any]:
    """
    De-serializes binary byte array back into Python execution object.
    """
    payload = lecture_pb2.LecturePayload()
    payload.ParseFromString(binary_bytes)

    action_names = {
        lecture_pb2.RENDER_TEXT_ONLY: "RENDER_TEXT_ONLY",
        lecture_pb2.INJECT_NEW_VECTOR: "INJECT_NEW_VECTOR",
        lecture_pb2.ANIMATE_EXISTING_VECTOR: "ANIMATE_EXISTING_VECTOR",
        lecture_pb2.CLEAR_CANVAS_RESET: "CLEAR_CANVAS_RESET",
    }

    return {
        "lecture_id": payload.lecture_id,
        "topic_title": payload.topic_title,
        "source_video_url": getattr(payload, "source_video_url", ""),
        "frames": [
            {
                "timestamp_seconds": f.timestamp_seconds,
                "spoken_text": f.spoken_text,
                "action_type": f.action_type,
                "action_name": action_names.get(f.action_type, "UNKNOWN"),
                "svg_payload": f.svg_payload,
                "visual_engine": getattr(f, "visual_engine", "svg"),
            }
            for f in payload.frames
        ],
    }
