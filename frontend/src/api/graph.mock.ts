/** 图谱 mock 数据：医学教材风格的 ~50 节点 ~90 边。 */

import type {
  KnowledgeNode,
  KnowledgeEdge,
  KnowledgeNodeType,
  KnowledgeRelationType,
  SourceLocator,
  GraphNodeDetailResponse,
  Chunk
} from "@/types/api";

export interface GraphPayloadMock {
  nodes: KnowledgeNode[];
  edges: KnowledgeEdge[];
  meta: {
    mode: "single" | "merged" | "compare";
    nodeCount: number;
    edgeCount: number;
    textbookIds: string[];
  };
}

const TEXTBOOK_A = "raw_mock_a";
const TEXTBOOK_B = "raw_mock_b";

function locator(textbookId: string, page: number): SourceLocator {
  return {
    raw_file_id: textbookId,
    source_path: `materials/${textbookId}.pdf`,
    source_type: "converted_textbook",
    locator_text: `${textbookId} page ${page}`,
    page_start: page,
    page_end: page,
    line_start: null,
    line_end: null,
    sheet_name: null,
    row_start: null,
    row_end: null,
    slide_number: null,
    char_start: null,
    char_end: null,
    element_ids: [],
    quote_hash: null
  };
}

interface NodeSeed {
  name: string;
  type: KnowledgeNodeType;
  book: string;
  page: number;
  confidence: number;
  freq: number;
  definition?: string;
}

const NODE_SEEDS: NodeSeed[] = [
  // 循环系统结构
  { name: "心脏", type: "Structure", book: TEXTBOOK_A, page: 12, confidence: 0.96, freq: 8, definition: "推动血液循环的中空肌性器官，分为四个腔室。" },
  { name: "右心房", type: "Structure", book: TEXTBOOK_A, page: 13, confidence: 0.92, freq: 5 },
  { name: "右心室", type: "Structure", book: TEXTBOOK_A, page: 13, confidence: 0.92, freq: 5 },
  { name: "左心房", type: "Structure", book: TEXTBOOK_A, page: 14, confidence: 0.93, freq: 5 },
  { name: "左心室", type: "Structure", book: TEXTBOOK_A, page: 14, confidence: 0.93, freq: 6 },
  { name: "二尖瓣", type: "Structure", book: TEXTBOOK_A, page: 16, confidence: 0.88, freq: 3 },
  { name: "三尖瓣", type: "Structure", book: TEXTBOOK_A, page: 16, confidence: 0.88, freq: 3 },
  { name: "主动脉瓣", type: "Structure", book: TEXTBOOK_A, page: 17, confidence: 0.87, freq: 3 },
  { name: "肺动脉瓣", type: "Structure", book: TEXTBOOK_A, page: 17, confidence: 0.86, freq: 3 },
  { name: "主动脉", type: "Structure", book: TEXTBOOK_A, page: 18, confidence: 0.91, freq: 6 },
  { name: "肺动脉", type: "Structure", book: TEXTBOOK_A, page: 19, confidence: 0.9, freq: 4 },
  { name: "毛细血管", type: "Structure", book: TEXTBOOK_A, page: 24, confidence: 0.93, freq: 7, definition: "管壁仅一层内皮细胞构成的最小血管。" },
  { name: "动脉", type: "Structure", book: TEXTBOOK_A, page: 22, confidence: 0.94, freq: 8 },
  { name: "静脉", type: "Structure", book: TEXTBOOK_A, page: 23, confidence: 0.94, freq: 7 },

  // 循环过程
  { name: "体循环", type: "Process", book: TEXTBOOK_A, page: 30, confidence: 0.95, freq: 6, definition: "血液从左心室出发经全身回到右心房的循环。" },
  { name: "肺循环", type: "Process", book: TEXTBOOK_A, page: 30, confidence: 0.95, freq: 6 },
  { name: "心动周期", type: "Process", book: TEXTBOOK_A, page: 36, confidence: 0.92, freq: 5 },
  { name: "舒张期", type: "Process", book: TEXTBOOK_A, page: 38, confidence: 0.9, freq: 4 },
  { name: "收缩期", type: "Process", book: TEXTBOOK_A, page: 38, confidence: 0.9, freq: 4 },

  // 心脏功能
  { name: "心输出量", type: "Function", book: TEXTBOOK_A, page: 42, confidence: 0.91, freq: 4 },
  { name: "每搏量", type: "Function", book: TEXTBOOK_A, page: 43, confidence: 0.89, freq: 3 },
  { name: "心率", type: "Function", book: TEXTBOOK_A, page: 44, confidence: 0.93, freq: 7 },
  { name: "血压", type: "Concept", book: TEXTBOOK_A, page: 50, confidence: 0.95, freq: 9, definition: "血液对血管壁产生的侧压力。" },
  { name: "收缩压", type: "Concept", book: TEXTBOOK_A, page: 51, confidence: 0.93, freq: 5 },
  { name: "舒张压", type: "Concept", book: TEXTBOOK_A, page: 51, confidence: 0.93, freq: 5 },
  { name: "脉压", type: "Concept", book: TEXTBOOK_A, page: 52, confidence: 0.86, freq: 2 },

  // 心电与诊断
  { name: "心电图", type: "Diagnosis", book: TEXTBOOK_A, page: 60, confidence: 0.94, freq: 6 },
  { name: "P 波", type: "Term", book: TEXTBOOK_A, page: 61, confidence: 0.85, freq: 3 },
  { name: "QRS 波群", type: "Term", book: TEXTBOOK_A, page: 61, confidence: 0.86, freq: 3 },
  { name: "T 波", type: "Term", book: TEXTBOOK_A, page: 61, confidence: 0.85, freq: 3 },
  { name: "心音", type: "Term", book: TEXTBOOK_A, page: 65, confidence: 0.84, freq: 3 },

  // 病理生理学（textbook B）
  { name: "高血压", type: "Disease", book: TEXTBOOK_B, page: 102, confidence: 0.96, freq: 8, definition: "动脉血压持续升高的临床综合征。" },
  { name: "低血压", type: "Disease", book: TEXTBOOK_B, page: 110, confidence: 0.92, freq: 4 },
  { name: "心力衰竭", type: "Disease", book: TEXTBOOK_B, page: 130, confidence: 0.93, freq: 6 },
  { name: "心肌梗死", type: "Disease", book: TEXTBOOK_B, page: 142, confidence: 0.95, freq: 7 },
  { name: "冠心病", type: "Disease", book: TEXTBOOK_B, page: 138, confidence: 0.94, freq: 6 },
  { name: "动脉粥样硬化", type: "Mechanism", book: TEXTBOOK_B, page: 155, confidence: 0.92, freq: 5 },
  { name: "心律失常", type: "Disease", book: TEXTBOOK_B, page: 168, confidence: 0.91, freq: 5 },

  // 症状
  { name: "胸痛", type: "Symptom", book: TEXTBOOK_B, page: 145, confidence: 0.88, freq: 4 },
  { name: "气促", type: "Symptom", book: TEXTBOOK_B, page: 132, confidence: 0.85, freq: 3 },
  { name: "心悸", type: "Symptom", book: TEXTBOOK_B, page: 170, confidence: 0.86, freq: 3 },

  // 治疗
  { name: "ACE 抑制剂", type: "Treatment", book: TEXTBOOK_B, page: 105, confidence: 0.9, freq: 4 },
  { name: "β 受体阻滞剂", type: "Treatment", book: TEXTBOOK_B, page: 106, confidence: 0.91, freq: 5 },
  { name: "他汀类", type: "Treatment", book: TEXTBOOK_B, page: 158, confidence: 0.89, freq: 3 },

  // 病理过程
  { name: "心肌缺血", type: "Process", book: TEXTBOOK_B, page: 140, confidence: 0.93, freq: 5 },
  { name: "心肌重塑", type: "Process", book: TEXTBOOK_B, page: 134, confidence: 0.88, freq: 3 },
  { name: "肺淤血", type: "Process", book: TEXTBOOK_B, page: 136, confidence: 0.86, freq: 3 },

  // 实验
  { name: "Frank-Starling 定律", type: "Mechanism", book: TEXTBOOK_A, page: 46, confidence: 0.88, freq: 3 },
  { name: "压力 - 容积曲线", type: "Experiment", book: TEXTBOOK_A, page: 48, confidence: 0.84, freq: 2 }
];

interface EdgeSeed {
  source: string;
  target: string;
  rel: KnowledgeRelationType;
  confidence: number;
}

const EDGE_SEEDS: EdgeSeed[] = [
  // 心脏 包含 各腔
  { source: "心脏", target: "右心房", rel: "CONTAINS", confidence: 0.97 },
  { source: "心脏", target: "右心室", rel: "CONTAINS", confidence: 0.97 },
  { source: "心脏", target: "左心房", rel: "CONTAINS", confidence: 0.97 },
  { source: "心脏", target: "左心室", rel: "CONTAINS", confidence: 0.97 },
  { source: "右心房", target: "三尖瓣", rel: "CONTAINS", confidence: 0.9 },
  { source: "左心房", target: "二尖瓣", rel: "CONTAINS", confidence: 0.9 },
  { source: "左心室", target: "主动脉瓣", rel: "CONTAINS", confidence: 0.9 },
  { source: "右心室", target: "肺动脉瓣", rel: "CONTAINS", confidence: 0.9 },
  { source: "左心室", target: "主动脉", rel: "LEADS_TO", confidence: 0.92 },
  { source: "右心室", target: "肺动脉", rel: "LEADS_TO", confidence: 0.92 },

  // IS_A
  { source: "动脉", target: "主动脉", rel: "IS_A", confidence: 0.85 },
  { source: "动脉", target: "肺动脉", rel: "IS_A", confidence: 0.85 },

  // 体循环 / 肺循环 涉及
  { source: "体循环", target: "左心室", rel: "PART_OF", confidence: 0.93 },
  { source: "体循环", target: "主动脉", rel: "PART_OF", confidence: 0.92 },
  { source: "体循环", target: "毛细血管", rel: "PART_OF", confidence: 0.9 },
  { source: "肺循环", target: "右心室", rel: "PART_OF", confidence: 0.93 },
  { source: "肺循环", target: "肺动脉", rel: "PART_OF", confidence: 0.92 },
  { source: "体循环", target: "肺循环", rel: "PARALLEL_WITH", confidence: 0.95 },

  // 心动周期
  { source: "心动周期", target: "舒张期", rel: "CONTAINS", confidence: 0.95 },
  { source: "心动周期", target: "收缩期", rel: "CONTAINS", confidence: 0.95 },
  { source: "舒张期", target: "收缩期", rel: "PARALLEL_WITH", confidence: 0.95 },

  // 心率 / 输出量
  { source: "心输出量", target: "每搏量", rel: "REFINES", confidence: 0.86 },
  { source: "心输出量", target: "心率", rel: "REFINES", confidence: 0.86 },
  { source: "每搏量", target: "Frank-Starling 定律", rel: "EXPLAINS", confidence: 0.84 },
  { source: "压力 - 容积曲线", target: "心动周期", rel: "EVIDENCED_BY", confidence: 0.78 },

  // 血压
  { source: "血压", target: "收缩压", rel: "REFINES", confidence: 0.95 },
  { source: "血压", target: "舒张压", rel: "REFINES", confidence: 0.95 },
  { source: "脉压", target: "收缩压", rel: "REFINES", confidence: 0.85 },
  { source: "脉压", target: "舒张压", rel: "REFINES", confidence: 0.85 },

  // 心电图
  { source: "心电图", target: "P 波", rel: "CONTAINS", confidence: 0.92 },
  { source: "心电图", target: "QRS 波群", rel: "CONTAINS", confidence: 0.92 },
  { source: "心电图", target: "T 波", rel: "CONTAINS", confidence: 0.92 },
  { source: "心电图", target: "心律失常", rel: "APPLIES_TO", confidence: 0.88 },
  { source: "心电图", target: "心肌梗死", rel: "APPLIES_TO", confidence: 0.86 },

  // 病理（B 教材）
  { source: "高血压", target: "血压", rel: "REFINES", confidence: 0.92 },
  { source: "低血压", target: "血压", rel: "REFINES", confidence: 0.9 },
  { source: "动脉粥样硬化", target: "冠心病", rel: "CAUSES", confidence: 0.93 },
  { source: "冠心病", target: "心肌缺血", rel: "CAUSES", confidence: 0.92 },
  { source: "心肌缺血", target: "心肌梗死", rel: "LEADS_TO", confidence: 0.94 },
  { source: "心肌梗死", target: "胸痛", rel: "CAUSES", confidence: 0.9 },
  { source: "心力衰竭", target: "气促", rel: "CAUSES", confidence: 0.88 },
  { source: "心力衰竭", target: "肺淤血", rel: "LEADS_TO", confidence: 0.86 },
  { source: "心力衰竭", target: "心肌重塑", rel: "EXPLAINS", confidence: 0.82 },
  { source: "心律失常", target: "心悸", rel: "CAUSES", confidence: 0.86 },
  { source: "ACE 抑制剂", target: "高血压", rel: "APPLIES_TO", confidence: 0.92 },
  { source: "β 受体阻滞剂", target: "高血压", rel: "APPLIES_TO", confidence: 0.92 },
  { source: "β 受体阻滞剂", target: "心律失常", rel: "APPLIES_TO", confidence: 0.86 },
  { source: "他汀类", target: "动脉粥样硬化", rel: "APPLIES_TO", confidence: 0.88 },

  // 跨教材：A 与 B 的同名概念
  { source: "心律失常", target: "心电图", rel: "EVIDENCED_BY", confidence: 0.92 },
  { source: "高血压", target: "动脉", rel: "APPLIES_TO", confidence: 0.84 },
  { source: "动脉粥样硬化", target: "动脉", rel: "APPLIES_TO", confidence: 0.85 }
];

function buildNodes(): KnowledgeNode[] {
  return NODE_SEEDS.map((seed, idx): KnowledgeNode => ({
    id: `knode_mock_${idx + 1}`,
    name: seed.name,
    node_type: seed.type,
    definition: seed.definition ?? null,
    aliases: [],
    source_locator: locator(seed.book, seed.page),
    evidence_chunk_ids: [`chunk_${seed.book}_${seed.page}`],
    confidence: seed.confidence,
    metadata: { frequency: seed.freq }
  }));
}

function buildEdges(nodes: KnowledgeNode[]): KnowledgeEdge[] {
  const idByName = new Map(nodes.map((n) => [n.name, n.id]));
  return EDGE_SEEDS.flatMap((seed, idx): KnowledgeEdge[] => {
    const sourceId = idByName.get(seed.source);
    const targetId = idByName.get(seed.target);
    if (!sourceId || !targetId) return [];
    return [
      {
        id: `kedge_mock_${idx + 1}`,
        source_node_id: sourceId,
        target_node_id: targetId,
        relation_type: seed.rel,
        description: null,
        source_locator: nodes.find((n) => n.id === sourceId)!.source_locator,
        evidence_chunk_ids: [],
        confidence: seed.confidence,
        metadata: {}
      }
    ];
  });
}

export async function fetchGraph(
  mode: "single" | "merged" | "compare" = "merged"
): Promise<GraphPayloadMock> {
  await new Promise((r) => setTimeout(r, 320));
  const nodes = buildNodes();
  const edges = buildEdges(nodes);
  return {
    nodes,
    edges,
    meta: {
      mode,
      nodeCount: nodes.length,
      edgeCount: edges.length,
      textbookIds: [TEXTBOOK_A, TEXTBOOK_B]
    }
  };
}

const MOCK_CHUNKS: Record<string, string[]> = {
  "心脏": [
    "心脏是推动血液流动的中空性肌性器官，位于胸腔中纵隔内，约三分之二在正中线左侧。成人心脏大小接近本人拳头，平均重约300克。心脏由心内膜、心肌层和心外膜三层构成，被心包膜所包裹。",
    "心脏被房间隔和室间隔分为左、右两半，每半又由房室口分为心房和心室，共构成右心房、右心室、左心房和左心室四个腔。右心房接收上下腔静脉回流的体循环静脉血，经三尖瓣注入右心室；左心房接收肺静脉回流的动脉血，经二尖瓣注入左心室。"
  ],
  "血压": [
    "血压是指血液对血管壁产生的侧压力。在临床上，血压通常指动脉血压，是推动血液在动脉中流动的驱动力。血压的形成需要三个基本条件：足够的循环血量、心脏射血和外周阻力。",
    "动脉血压在心动周期中随心脏的收缩和舒张而发生周期性波动。心室收缩时，动脉血压达到最高值，称为收缩压（正常值约 100-120 mmHg）；心室舒张时，动脉血压降至最低值，称为舒张压（正常值约 60-80 mmHg）。收缩压与舒张压之差为脉压。"
  ],
  "高血压": [
    "高血压是以动脉血压持续升高为主要特征的临床综合征，是最常见的心血管疾病之一。诊断标准为在未使用降压药物的情况下，非同日三次测量收缩压≥140 mmHg 和/或舒张压≥90 mmHg。",
    "高血压的发病机制涉及多种因素：交感神经系统活性增高、肾素-血管紧张素-醛固酮系统激活、血管内皮功能受损等。长期高血压可导致心、脑、肾等靶器官损害，是冠心病、脑卒中和肾衰竭的重要危险因素。一线治疗药物包括 ACE 抑制剂、β 受体阻滞剂、钙拮抗剂和利尿剂等。"
  ],
  "心肌梗死": [
    "急性心肌梗死是由冠状动脉急性闭塞导致心肌持续性缺血缺氧，进而引起心肌坏死的严重心血管急症。最常见的病因是在冠状动脉粥样硬化的基础上，斑块破裂诱发血栓形成。",
    "典型表现为持续剧烈的胸骨后压榨性疼痛，持续时间超过 30 分钟，含服硝酸甘油不能缓解，常伴有大汗、恐惧和濒死感。心电图可见 ST 段弓背向上抬高，血清心肌酶谱（CK-MB、cTnI）升高是确诊依据。"
  ],
  "体循环": [
    "体循环又称大循环，是血液从左心室射入主动脉，经各级动脉到达全身毛细血管，进行物质交换后，再经各级静脉回流至右心房的循环过程。体循环的主要功能是将含氧丰富的动脉血输送至全身各组织器官，并将代谢产物带回。"
  ],
  "心力衰竭": [
    "心力衰竭是由于心脏结构或功能异常导致心室充盈和/或射血功能受损，心排出量不能满足机体组织代谢需要的一组复杂临床综合征。常见症状包括呼吸困难、疲乏和液体潴留（肺淤血、体循环淤血及外周水肿）。",
    "心力衰竭时，机体通过 Frank-Starling 机制、交感-肾上腺髓质系统激活和心肌重塑等代偿机制来维持心输出量，但长期代偿终将导致心功能进行性恶化。"
  ],
  "毛细血管": [
    "毛细血管是连接小动脉和小静脉之间的微细血管，管壁仅由一层内皮细胞和基膜构成，是血液与组织之间进行物质交换的场所。毛细血管管径极细（约 5-10μm），红细胞需变形才能通过，这有利于充分的气体和物质交换。"
  ]
};

function getMockChunkTexts(nodeName: string): string[] {
  if (MOCK_CHUNKS[nodeName]) return MOCK_CHUNKS[nodeName];
  return [
    `${nodeName}是医学基础课程中的重要知识点，在临床实践和基础研究中具有广泛应用。掌握其基本概念、作用机制和临床意义对于理解相关疾病的发生发展至关重要。`
  ];
}

export async function fetchNode(nodeId: string): Promise<GraphNodeDetailResponse | null> {
  await new Promise((r) => setTimeout(r, 120));
  const nodes = buildNodes();
  const node = nodes.find((n) => n.id === nodeId);
  if (!node) return null;
  const allEdges = buildEdges(nodes);
  const edges = allEdges.filter(
    (e) => e.source_node_id === nodeId || e.target_node_id === nodeId
  );
  const chunkTexts = getMockChunkTexts(node.name);
  const evidence_chunks: Chunk[] = chunkTexts.map((text, i) => ({
    id: (node.evidence_chunk_ids ?? [])[0] ?? `chunk_gen_${i}`,
    raw_file_id: node.source_locator.raw_file_id,
    section_id: `sec_${node.id}_${i}`,
    text,
    order_index: i,
    char_start: 0,
    char_end: text.length,
    char_count: text.length,
    source_locator: node.source_locator,
    metadata: {}
  }));
  return {
    node,
    edges,
    evidence_chunks,
    graph_id: "graph_mock_1",
    raw_file_id: node.source_locator.raw_file_id
  };
}

export async function buildGraph(textbookIds: string[]): Promise<{ job_id: string }> {
  await new Promise((r) => setTimeout(r, 400));
  return { job_id: `job_graph_${Date.now()}` };
}

export async function buildLayeredKG(textbookIds: string[]): Promise<{ job_id: string }> {
  await new Promise((r) => setTimeout(r, 400));
  return { job_id: `job_layered_${Date.now()}` };
}

export async function getLayeredKG(): Promise<unknown> {
  await new Promise((r) => setTimeout(r, 300));
  return { layers: [] };
}
