import type {
  DialogueHistoryResponse,
  DialogueMessageRequest,
  DialogueMessageResponse
} from "@/types/api";

export async function getHistory(_rawFileIds?: string[]): Promise<DialogueHistoryResponse> {
  await new Promise((r) => setTimeout(r, 200));
  return { raw_file_ids: [], messages: [], count: 0 };
}

export async function sendMessage(body: DialogueMessageRequest): Promise<DialogueMessageResponse> {
  await new Promise((r) => setTimeout(r, 800));
  const now = new Date().toISOString();
  return {
    user_message: {
      id: `msg_u_${Date.now()}`,
      role: "teacher",
      content: body.message,
      raw_file_ids: body.raw_file_ids ?? [],
      teacher_edit_ids: [],
      created_by: null,
      created_at: now,
      metadata: {}
    },
    assistant_message: {
      id: `msg_a_${Date.now()}`,
      role: "assistant",
      content: `收到您的反馈：「${body.message}」。这是 mock 回复，实际回复需要后端生成。`,
      raw_file_ids: body.raw_file_ids ?? [],
      teacher_edit_ids: [],
      created_by: null,
      created_at: now,
      metadata: {}
    },
    edits: [],
    integration: null,
    metadata: {}
  };
}
