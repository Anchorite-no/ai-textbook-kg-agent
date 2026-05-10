import type { OrganizeWorkflowAcceptedResponse } from "@/types/api";
import { request } from "./client";

export interface OrganizeFilesOptions {
  buildGraph?: boolean;
  buildLayeredGraphs?: boolean;
  buildRag?: boolean;
  buildAlignmentGraph?: boolean;
  buildIntegrationResult?: boolean;
  useLlm?: boolean;
  maxSections?: number;
  maxNodesPerSection?: number;
  alignmentMinConfidence?: number;
  alignmentMaxNodes?: number;
  integrationTargetCompressionRatio?: number;
  integrationMaxNodes?: number;
}

export async function organizeFiles(
  files: File[],
  options: OrganizeFilesOptions = {}
): Promise<OrganizeWorkflowAcceptedResponse> {
  const formData = new FormData();
  for (const file of files) formData.append("files", file);
  appendIfDefined(formData, "build_graph", options.buildGraph);
  appendIfDefined(formData, "build_layered_graphs", options.buildLayeredGraphs);
  appendIfDefined(formData, "build_rag", options.buildRag);
  appendIfDefined(formData, "build_alignment_graph", options.buildAlignmentGraph);
  appendIfDefined(formData, "build_integration_result", options.buildIntegrationResult);
  appendIfDefined(formData, "use_llm", options.useLlm);
  appendIfDefined(formData, "max_sections", options.maxSections);
  appendIfDefined(formData, "max_nodes_per_section", options.maxNodesPerSection);
  appendIfDefined(formData, "alignment_min_confidence", options.alignmentMinConfidence);
  appendIfDefined(formData, "alignment_max_nodes", options.alignmentMaxNodes);
  appendIfDefined(formData, "integration_target_compression_ratio", options.integrationTargetCompressionRatio);
  appendIfDefined(formData, "integration_max_nodes", options.integrationMaxNodes);

  return request<OrganizeWorkflowAcceptedResponse>("/api/workflows/organize", {
    method: "POST",
    body: formData
  });
}

function appendIfDefined(formData: FormData, key: string, value: string | number | boolean | undefined): void {
  if (value === undefined) return;
  formData.append(key, String(value));
}

export const workflowsApi = {
  organizeFiles
};
