from __future__ import annotations

from dataclasses import dataclass, field

from natvr.markers import normalize_marker_field_name
from natvr.models import MarkerEventV1


@dataclass(slots=True)
class MarkerContextTracker:
    active_markers: dict[str, MarkerEventV1] = field(default_factory=dict)
    activation_order: list[str] = field(default_factory=list)

    def observe(self, marker: MarkerEventV1) -> None:
        marker_id = marker.marker_id
        if marker.event == "end":
            self.active_markers.pop(marker_id, None)
            self.activation_order = [
                active_id for active_id in self.activation_order if active_id != marker_id
            ]
            return

        self.active_markers[marker_id] = marker
        self.activation_order = [
            active_id for active_id in self.activation_order if active_id != marker_id
        ]
        self.activation_order.append(marker_id)

    def active_markers_by_type(self) -> dict[str, MarkerEventV1]:
        by_type: dict[str, MarkerEventV1] = {}
        for marker_id in self.activation_order:
            marker = self.active_markers.get(marker_id)
            if marker is None:
                continue
            by_type[marker.marker_type] = marker
        return by_type

    def to_output_context(self) -> dict[str, object]:
        by_type = self.active_markers_by_type()
        if not by_type:
            return {}

        context: dict[str, object] = {}
        active_markers_payload: dict[str, object] = {}
        for marker_type, marker in by_type.items():
            normalized_type = normalize_marker_field_name(marker_type)
            marker_payload = {
                "marker_type": marker.marker_type,
                "marker_id": marker.marker_id,
                "label": marker.label,
                "session_id": marker.session_id,
                "emitted_at_us": marker.emitted_at_us,
                "attributes": dict(marker.attributes),
            }
            active_markers_payload[normalized_type] = marker_payload
            if marker_type == "cue":
                if "cue_id" in marker.attributes:
                    context["cue_id"] = marker.attributes["cue_id"]
                if "phase" in marker.attributes:
                    context["cue_phase"] = marker.attributes["phase"]
                if "gesture" in marker.attributes:
                    context["cue_gesture"] = marker.attributes["gesture"]
                if "prompt" in marker.attributes:
                    context["cue_prompt"] = marker.attributes["prompt"]

        context["active_markers"] = active_markers_payload
        return context
