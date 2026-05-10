from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.models.schemas import (
    CompressionStats,
    DialogueMessage,
    DialogueMessageRequest,
    DialogueMessageResponse,
    DialogueMessageRole,
    IntegrationAction,
    IntegrationDecision,
    IntegrationResponse,
    TeacherEdit,
    TeacherEditApplyResponse,
    TeacherEditCreateRequest,
    TeacherEditOperation,
    DecisionOverrideRequest,
)
from app.services.converted_textbook_importer import stable_id
from app.services.integration_storage import load_integration, load_latest_integration, save_integration
from app.services.teacher_edit_storage import append_dialogue_messages, append_teacher_edit


ACTION_WORDS: dict[str, IntegrationAction] = {
    "merge": IntegrationAction.merge,
    "合并": IntegrationAction.merge,
    "keep": IntegrationAction.keep,
    "保留": IntegrationAction.keep,
    "remove": IntegrationAction.remove,
    "删除": IntegrationAction.remove,
    "移除": IntegrationAction.remove,
    "refine": IntegrationAction.refine,
    "补充": IntegrationAction.refine,
    "细化": IntegrationAction.refine,
    "conflict": IntegrationAction.conflict,
    "冲突": IntegrationAction.conflict,
}


def record_teacher_edit(request: TeacherEditCreateRequest) -> TeacherEditApplyResponse:
    integration = _load_target_integration(request.raw_file_ids)
    raw_file_ids = integration.raw_file_ids if integration else sorted(request.raw_file_ids)
    before = _target_snapshot(integration, request.target_type, request.target_id)
    edit = _make_edit(
        raw_file_ids=raw_file_ids,
        target_type=request.target_type,
        target_id=request.target_id,
        operation=request.operation,
        before=before,
        after=request.after,
        reason=request.reason,
        created_by=request.created_by,
        affected_ids=[request.target_id],
        metadata={**request.metadata, "stage": "00_stage10", "applied": False},
    )
    append_teacher_edit(raw_file_ids, edit)
    return TeacherEditApplyResponse(
        edit=edit,
        integration=integration,
        decision=None,
        message="教师修改事件已记录；当前操作仅作为事件入库，未覆盖系统生成图谱。",
        metadata={"raw_file_ids": raw_file_ids, "applied": False},
    )


def override_integration_decision(decision_id: str, request: DecisionOverrideRequest) -> TeacherEditApplyResponse:
    integration = _require_integration(request.raw_file_ids)
    decision_index, decision = _find_decision(integration, decision_id)
    before = decision.model_dump(mode="json")
    edit_id = stable_id("teacher_edit", integration.id, decision_id, request.action.value, request.reason, datetime.utcnow().isoformat())

    after_payload = _override_payload(request, edit_id, before)
    updated_decision = decision.model_copy(update=after_payload)
    updated_decisions = list(integration.decisions)
    updated_decisions[decision_index] = updated_decision
    updated_integration = _apply_teacher_override_to_integration(integration, updated_decisions, updated_decision, edit_id)

    edit = _make_edit(
        raw_file_ids=updated_integration.raw_file_ids,
        target_type="decision",
        target_id=decision_id,
        operation=TeacherEditOperation.override_decision,
        before=before,
        after=updated_decision.model_dump(mode="json"),
        reason=request.reason,
        created_by=request.created_by,
        affected_ids=[decision_id, *updated_decision.target_node_ids],
        metadata={
            **request.metadata,
            "stage": "00_stage10",
            "applied": True,
            "local_reintegration": True,
            "message": request.message,
        },
        edit_id=edit_id,
    )
    append_teacher_edit(updated_integration.raw_file_ids, edit)
    output_path = save_integration(updated_integration)
    return TeacherEditApplyResponse(
        edit=edit,
        integration=updated_integration,
        decision=updated_decision,
        message=f"已将整合决策 {decision_id} 覆盖为 {request.action.value}，并完成局部再整合标记。",
        metadata={"integration_output_path": str(output_path), "raw_file_ids": updated_integration.raw_file_ids, "applied": True},
    )


def handle_dialogue_message(request: DialogueMessageRequest) -> DialogueMessageResponse:
    integration = _load_target_integration(request.raw_file_ids)
    raw_file_ids = integration.raw_file_ids if integration else sorted(request.raw_file_ids)
    user_message = DialogueMessage(
        id=stable_id("dialogue_msg", "teacher", "|".join(raw_file_ids), request.message, datetime.utcnow().isoformat()),
        role=DialogueMessageRole.teacher,
        content=request.message,
        raw_file_ids=raw_file_ids,
        created_by=request.created_by,
        metadata=request.metadata,
    )

    edits: list[TeacherEdit] = []
    assistant_text: str
    if integration is not None:
        override = _override_from_dialogue(request)
        if override is not None:
            result = override_integration_decision(override["decision_id"], override["request"])
            edits.append(result.edit)
            integration = result.integration
            assistant_text = result.message
        else:
            assistant_text = "已记录教师反馈。请指定 target_decision_id 和 override_action，或在消息中包含 integration_decision_* 与合并/保留/删除/细化/冲突。"
    else:
        assistant_text = "已记录教师反馈，但当前没有可修改的整合结果。请先构建 integration。"

    assistant_message = DialogueMessage(
        id=stable_id("dialogue_msg", "assistant", "|".join(raw_file_ids), assistant_text, datetime.utcnow().isoformat()),
        role=DialogueMessageRole.assistant,
        content=assistant_text,
        raw_file_ids=raw_file_ids,
        teacher_edit_ids=[edit.id for edit in edits],
        metadata={"stage": "00_stage10", "edit_count": len(edits)},
    )
    append_dialogue_messages(raw_file_ids, [user_message, assistant_message])
    return DialogueMessageResponse(
        user_message=user_message,
        assistant_message=assistant_message,
        edits=edits,
        integration=integration,
        metadata={"raw_file_ids": raw_file_ids, "applied": bool(edits)},
    )


def _load_target_integration(raw_file_ids: list[str]) -> IntegrationResponse | None:
    ids = sorted(raw_file_ids)
    return load_integration(ids) if ids else load_latest_integration()


def _require_integration(raw_file_ids: list[str]) -> IntegrationResponse:
    integration = _load_target_integration(raw_file_ids)
    if integration is None:
        raise ValueError("Integration result not found. Build integration before applying teacher edits.")
    return integration


def _find_decision(integration: IntegrationResponse, decision_id: str) -> tuple[int, IntegrationDecision]:
    for index, decision in enumerate(integration.decisions):
        if decision.id == decision_id:
            return index, decision
    raise ValueError(f"Integration decision not found: {decision_id}")


def _override_payload(request: DecisionOverrideRequest, edit_id: str, before: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "action": request.action,
        "reason": f"教师覆盖：{request.reason}",
        "confidence": request.confidence,
        "metadata": {
            **before.get("metadata", {}),
            **request.metadata,
            "teacher_override": True,
            "teacher_reason": request.reason,
            "teacher_edit_id": edit_id,
            "original_action": before.get("action"),
            "overridden_at": datetime.utcnow().isoformat(),
        },
    }
    if "retained_content" in request.model_fields_set and request.retained_content is not None:
        payload["retained_content"] = request.retained_content
    if "removed_redundancy" in request.model_fields_set and request.removed_redundancy is not None:
        payload["removed_redundancy"] = request.removed_redundancy
    return payload


def _apply_teacher_override_to_integration(
    integration: IntegrationResponse,
    decisions: list[IntegrationDecision],
    updated_decision: IntegrationDecision,
    edit_id: str,
) -> IntegrationResponse:
    integrated_concepts = []
    for concept in integration.integrated_concepts:
        if updated_decision.id not in concept.decision_ids:
            integrated_concepts.append(concept)
            continue
        metadata = {
            **concept.metadata,
            "teacher_override": True,
            "teacher_edit_id": edit_id,
            "teacher_action": updated_decision.action.value,
        }
        update: dict[str, Any] = {"metadata": metadata}
        if updated_decision.action == IntegrationAction.remove:
            update["summary"] = "教师标记为移出整合正文。"
        elif updated_decision.retained_content:
            update["definition"] = updated_decision.retained_content
            update["summary"] = "教师覆盖后的整合表述。"
        integrated_concepts.append(concept.model_copy(update=update))

    stats = _recalculate_stats(integration.compression_stats, decisions)
    metadata = {
        **integration.metadata,
        "teacher_edit_count": int(integration.metadata.get("teacher_edit_count", 0)) + 1,
        "last_teacher_edit_id": edit_id,
        "updated_by_teacher": True,
        "local_reintegration": True,
    }
    return integration.model_copy(update={"decisions": decisions, "integrated_concepts": integrated_concepts, "compression_stats": stats, "metadata": metadata})


def _recalculate_stats(existing: CompressionStats, decisions: list[IntegrationDecision]) -> CompressionStats:
    action_counts = {action.value: 0 for action in IntegrationAction}
    retained_char_count = 0
    for decision in decisions:
        action_counts[decision.action.value] += 1
        if decision.action != IntegrationAction.remove and decision.retained_content:
            retained_char_count += len(decision.retained_content)

    original_char_count = existing.original_char_count
    retained = retained_char_count or existing.retained_char_count
    compression_ratio = round(retained / original_char_count, 4) if original_char_count else 0.0
    return existing.model_copy(
        update={
            "retained_char_count": retained,
            "merged_node_count": action_counts[IntegrationAction.merge.value],
            "kept_node_count": action_counts[IntegrationAction.keep.value],
            "removed_node_count": action_counts[IntegrationAction.remove.value],
            "refined_node_count": action_counts[IntegrationAction.refine.value],
            "conflict_count": action_counts[IntegrationAction.conflict.value],
            "compression_ratio": compression_ratio,
            "metadata": {
                **existing.metadata,
                "action_counts": action_counts,
                "teacher_recalculated": True,
            },
        }
    )


def _make_edit(
    raw_file_ids: list[str],
    target_type: str,
    target_id: str,
    operation: TeacherEditOperation,
    before: dict[str, Any],
    after: dict[str, Any],
    reason: str | None,
    created_by: str | None,
    affected_ids: list[str],
    metadata: dict[str, Any],
    edit_id: str | None = None,
) -> TeacherEdit:
    return TeacherEdit(
        id=edit_id or stable_id("teacher_edit", "|".join(raw_file_ids), target_type, target_id, operation.value, datetime.utcnow().isoformat()),
        target_type=target_type,  # type: ignore[arg-type]
        target_id=target_id,
        operation=operation,
        before=before,
        after=after,
        reason=reason,
        created_by=created_by,
        affected_ids=list(dict.fromkeys(affected_ids)),
        metadata=metadata,
    )


def _target_snapshot(integration: IntegrationResponse | None, target_type: str, target_id: str) -> dict[str, Any]:
    if integration is None:
        return {}
    if target_type == "decision":
        for decision in integration.decisions:
            if decision.id == target_id:
                return decision.model_dump(mode="json")
    return {}


def _override_from_dialogue(request: DialogueMessageRequest) -> dict[str, Any] | None:
    decision_id = request.target_decision_id or _decision_id_from_text(request.message)
    action = request.override_action or _action_from_text(request.message)
    if not decision_id or action is None:
        return None
    reason = request.reason or request.message
    return {
        "decision_id": decision_id,
        "request": DecisionOverrideRequest(
            raw_file_ids=request.raw_file_ids,
            action=action,
            retained_content=request.retained_content,
            removed_redundancy=request.removed_redundancy,
            reason=reason,
            confidence=request.confidence,
            created_by=request.created_by,
            message=request.message,
            metadata=request.metadata,
        ),
    }


def _decision_id_from_text(message: str) -> str | None:
    match = re.search(r"integration_decision_[A-Za-z0-9_]+", message)
    return match.group(0) if match else None


def _action_from_text(message: str) -> IntegrationAction | None:
    lowered = message.lower()
    for marker, action in ACTION_WORDS.items():
        if marker in lowered or marker in message:
            return action
    return None
