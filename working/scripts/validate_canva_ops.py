#!/usr/bin/env python3
"""Fail-closed safety check for Canva text operations before an MCP perform call."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from template.template_port import parse_snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("ops", type=Path)
    args = parser.parse_args()

    snapshot_raw = json.loads(args.snapshot.read_text(encoding="utf-8-sig"))
    elements = {element["eid"]: element for element in parse_snapshot(args.snapshot)}
    fills = {
        fill["element_id"]: fill
        for fill in snapshot_raw.get("fills", [])
        if fill.get("element_id")
    }
    page_dimensions = {
        page.get("page_index", page.get("page_number")): page.get("dimension", {})
        for page in snapshot_raw.get("pages", [])
    }
    ops = json.loads(args.ops.read_text(encoding="utf-8-sig"))
    errors: list[str] = []
    warnings: list[str] = []
    seen: set[tuple] = set()

    for index, op in enumerate(ops):
        op_type = op.get("type")
        eid = op.get("element_id")
        label = f"op {index + 1} ({op_type})"
        if not eid or (eid not in elements and eid not in fills):
            errors.append(f"{label}: element_id is absent from the live snapshot")
            continue
        element = elements.get(eid)
        fill = fills.get(eid)
        signature = (
            op_type,
            eid,
            op.get("find_text"),
            op.get("text"),
            op.get("left"),
            op.get("top"),
        )
        if signature in seen:
            errors.append(f"{label}: exact duplicate operation")
        seen.add(signature)

        if op_type == "position_element":
            if not fill:
                errors.append(f"{label}: position_element must target a snapshot-backed fill")
            elif not fill.get("editable"):
                errors.append(f"{label}: target fill is not editable")
            elif set(op) != {"type", "element_id", "left", "top"}:
                errors.append(
                    f"{label}: position_element must specify only element_id, left, and top"
                )
            elif not all(
                isinstance(op.get(axis), (int, float)) and op[axis] >= 0
                for axis in ("left", "top")
            ):
                errors.append(f"{label}: left and top must be non-negative numbers")
            else:
                container = fill.get("containerElement") or {}
                dimensions = container.get("dimension") or {}
                page_dimensions_for_fill = page_dimensions.get(fill.get("page_index"), {})
                width = dimensions.get("width")
                height = dimensions.get("height")
                page_width = page_dimensions_for_fill.get("width")
                page_height = page_dimensions_for_fill.get("height")
                if not all(
                    isinstance(value, (int, float))
                    for value in (width, height, page_width, page_height)
                ):
                    errors.append(
                        f"{label}: fill and page dimensions are required for bounds validation"
                    )
                elif (
                    op["left"] + width > page_width
                    or op["top"] + height > page_height
                ):
                    errors.append(f"{label}: positioned fill would exceed page bounds")
        elif not element:
            errors.append(f"{label}: {op_type} cannot target a fill element")
        elif op_type == "replace_text" and element["runs"] > 1:
            errors.append(
                f"{label}: whole-box replace targets {element['runs']} styled runs; "
                "use exact run-level find_and_replace_text operations"
            )
        elif op_type == "find_and_replace_text":
            find_text = op.get("find_text")
            if not find_text:
                errors.append(f"{label}: empty find_text")
            elif element["text"].count(find_text) != 1:
                errors.append(f"{label}: find_text is not unique in the target element")
            elif element["runs"] > 1 and find_text not in element["run_texts"]:
                errors.append(
                    f"{label}: anchor crosses a style boundary; it must equal one full text run"
                )
        elif op_type == "format_text":
            formatting = op.get("formatting") or {}
            if formatting != {"font_style": "normal"}:
                errors.append(
                    f"{label}: broad formatting mutation is forbidden; only the known "
                    "work-box italic normalization is permitted"
                )
            if not element["text"].startswith("CEO & Executive Director"):
                warnings.append(
                    f"{label}: formatting target is not the canonical CEO work box"
                )
        elif op_type == "resize_element":
            if set(op) - {"type", "element_id", "width"}:
                errors.append(
                    f"{label}: resize may change layout; only a width-only cover autosize is allowed"
                )
        elif op_type not in {
            "replace_text",
            "find_and_replace_text",
            "format_text",
            "resize_element",
            "position_element",
        }:
            errors.append(f"{label}: operation type is outside the approved port allowlist")

    cover_eids = {
        eid
        for eid, element in elements.items()
        if round(element["top"]) in range(166, 170)
        and round(element["left"]) in range(50, 55)
    }
    for eid in cover_eids:
        text_indexes = [
            i
            for i, op in enumerate(ops)
            if op.get("element_id") == eid
            and op.get("type") in {"replace_text", "find_and_replace_text"}
        ]
        if not text_indexes:
            continue
        resize_indexes = [
            i
            for i, op in enumerate(ops)
            if op.get("element_id") == eid and op.get("type") == "resize_element"
        ]
        if not resize_indexes or min(resize_indexes) > min(text_indexes):
            errors.append(
                f"cover {eid}: width-only resize must occur before the first text mutation"
            )

    if warnings:
        print("WARNINGS")
        for warning in warnings:
            print(f"- {warning}")
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    pages = sorted(
        {element["page"] for element in elements.values()}
        | {fill.get("page_index") for fill in fills.values() if fill.get("page_index")}
    )
    print(
        f"PASS: {len(ops)} operations target snapshot-backed elements across "
        f"{len(pages)} parsed pages; no mixed-run whole-box replacements."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
