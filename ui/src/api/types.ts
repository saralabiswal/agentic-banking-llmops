/**
 * Author: Sarala Biswal
 */
// TypeScript mirrors of Pydantic schemas from platform/core/schemas.py.

export type Segment = "STANDARD" | "PRIME" | "AFFLUENT" | "PRIVATE";
export type Channel = "MOBILE" | "WEB" | "PHONE" | "BRANCH" | "SMS" | "PUSH" | "EMAIL" | "CRM";
export type Scenario = "payment_risk_intervention" | "billing_dispute_resolution" | "churn_prevention";

export interface CardProfile {
  balance: string;
  creditLimit: string;
  utilization: number;
  missedPmts: number;
  pastDue: string;
  daysSinceLastPayment: number | null;
}

export interface BankingProfile {
  checkingBalance: string;
  savingsBalance: string;
  lastDepositAt: string | null;
  overdrafts30d: number;
  directDeposit: boolean;
}

export interface CRMProfile {
  tenureMonths: number;
  npsScore: number | null;
  openTickets: number;
  lastContactAt: string | null;
}

export interface BehavioralProfile {
  appLogins30d: number;
  preferredChannel: Channel;
  smsOk: boolean;
  pushEnabled: boolean;
  emailOk: boolean;
}

export interface ModelSignals {
  riskScore: number;
  churnProbability: number;
  clvEstimate: string;
  lastIntervention: string | null;
  intervention7d: number;
  paymentPropensity: number;
  modelVersions: Record<string, string>;
}

export interface CustomerProfile {
  customerId: string;
  name: string;
  segment: Segment;
  card: CardProfile;
  banking: BankingProfile;
  crm: CRMProfile | null;
  behavioral: BehavioralProfile;
  signals: ModelSignals;
  assembledAt: string;
  assemblyLatencyMs: number;
  sourcesAvailable: string[];
  sourcesDegraded: string[];
  partialContext: boolean;
}

export interface AssemblyResult {
  status: "ASSEMBLED" | "DEGRADED" | "FAILED";
  sessionId: string;
  customerId: string;
  partialContext: boolean;
  sourcesAvailable: string[];
  sourcesDegraded: string[];
  modelVersionsUsed: Record<string, string>;
  ttlExpiresAt: string;
  assemblyMs: number;
}

export interface PolicyChunk {
  chunkId: string;
  documentId: string;
  documentTitle: string;
  documentType: "POLICY" | "REGULATION" | "PLAYBOOK" | "COMPLIANCE";
  docVersion: string;
  rawText: string;
  rerankScore: number;
  chunkType: "DOCUMENT" | "SECTION" | "PARAGRAPH";
  parentChunkId: string | null;
  productLine: string | null;
  jurisdiction: string | null;
}

export interface RetrievalResult {
  sessionId: string;
  query: string;
  chunks: PolicyChunk[];
  kbVersion: string;
  retrievalMs: number;
  embeddingModel: string;
  rerankerModel: string;
}

export interface AgentOutput {
  agentName: string;
  output: Record<string, unknown>;
  latencyMs: number;
}

export interface OrchestratorOutput {
  traceId: string;
  sessionId: string;
  customerId: string;
  scenario: string;
  status: "PENDING_GUARDRAILS" | "HUMAN_REVIEW" | "FAILED";
  agentOutputs: AgentOutput[];
  proposedActions: ProposedAction[];
  branchDecisions: Record<string, unknown>[];
  requiresApproval: boolean;
  orchestrationMs: number;
}

export interface AgentContext {
  sessionId: string;
  customerId: string;
  scenario: string;
  pipelineStep: number;
  traceId: string;
  policyChunks: PolicyChunk[];
  priorOutputs: AgentOutput[];
  authorizedTools: string[];
  maxTokens: number;
  timeoutMs: number;
}

export interface PolicyMatch {
  hardshipEligible: boolean;
  reason: string;
  policyRef: string;
}

export interface RiskAssessment {
  riskLevel: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  riskScore: number;
  confidence: number;
  lowerConfidenceReason: string | null;
  primarySignals: string[];
  protectiveSignals: string[];
  policyMatch: PolicyMatch;
  recommendedNext: string;
}

export interface ProposedAction {
  actionId: string;
  actionType: string;
  requiresApproval: boolean;
  channel: Channel | null;
  caseType: string | null;
  amount: string | null;
  approvalReason: string | null;
  customerMessage: string | null;
  metadata: Record<string, unknown>;
}

export interface PolicyCompliance {
  contactFrequencyOk: boolean;
  reason: string;
  policyRef: string;
}

export interface InterventionProposal {
  interventionType: string;
  interventionChannel: Channel;
  customerMessage: string;
  internalNote: string;
  proposedActions: ProposedAction[];
  policyCompliance: PolicyCompliance;
  estimatedImpact: string;
  fallbackIfNoResponse: string | null;
}

export interface CheckResult {
  status: "APPROVED" | "FLAGGED" | "BLOCKED";
  ruleId: string;
  category: "REGULATORY" | "BUSINESS_POLICY" | "RESPONSIBLE_AI";
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  message: string;
  details: Record<string, unknown>;
}

export interface GuardrailsResult {
  traceId: string;
  sessionId: string;
  customerId: string;
  approvedActions: ProposedAction[];
  flaggedActions: ProposedAction[];
  blockedActions: ProposedAction[];
  checks: CheckResult[];
  requiresHumanReview: boolean;
}

export interface ApprovalQueueItem {
  queueId: string;
  status: "PENDING" | "APPROVED" | "REJECTED" | "ESCALATED" | "AUTO_REJECTED";
  priority: "URGENT" | "HIGH" | "STANDARD" | "LOW";
  createdAt: string;
  slaDeadline: string;
  escalationAt: string;
  assignedTo: string | null;
  action: ProposedAction;
  flagReasons: string[];
  context: Record<string, unknown>;
  decision: "APPROVED" | "REJECTED" | null;
  decisionBy: string | null;
  decisionAt: string | null;
  rejectionReason: string | null;
  feedbackSentToAgent: boolean;
  feedbackSentToMlops: boolean;
}

export interface ExperimentVariant {
  experimentId: string;
  variantId: string;
  name: string;
  weight: number;
  payload: Record<string, unknown>;
  sampleCount: number;
  conversionCount: number;
}

export interface ExperimentResult {
  experimentId: string;
  variantId: string;
  sampleCount: number;
  conversionCount: number;
  conversionRate: number;
  confidence: number;
  isWinner: boolean;
}

export interface DeliveryReceipt {
  receiptId: string;
  actionId: string;
  channel: Channel;
  status: "DELIVERED" | "FAILED" | "QUEUED";
  deliveredAt: string;
  metadata: Record<string, unknown>;
}

export interface ExecutionResult {
  traceId: string;
  actionId: string;
  actionExecuted: boolean;
  status: "EXECUTED" | "PENDING_APPROVAL" | "BLOCKED" | "FAILED";
  channel: Channel | null;
  deliveryReceipt: DeliveryReceipt | null;
  outcomeTrackingId: string | null;
  customerMessage: string | null;
  pendingActions: ApprovalQueueItem[];
}

export interface OutcomeEvent {
  outcomeId: string;
  traceId: string;
  actionId: string;
  customerId: string;
  outcomeType: "PUSH_OPENED" | "ENROLLED" | "IGNORED" | "OPT_OUT" | "COMPLAINT";
  outcomeTs: string;
  metadata: Record<string, unknown>;
}

export interface AuditRecord {
  auditId: string;
  eventType:
    | "CONTEXT_ASSEMBLY"
    | "VECTOR_RETRIEVAL"
    | "MEMORY_RETRIEVED"
    | "ORCHESTRATION_COMPLETE"
    | "GUARDRAILS_EVALUATION"
    | "AB_ASSIGNMENT"
    | "ACTION_EXECUTED"
    | "MEMORY_STORED"
    | "OUTCOME_CAPTURED";
  traceId: string;
  sessionId: string;
  customerId: string;
  timestamp: string;
  layer: "1" | "2" | "3" | "4" | "5" | "6";
  payload: Record<string, unknown>;
}

export interface ConfigResponse {
  llmBackend: "mock" | "ollama" | "api";
  llmModeLabel: "Mock LLM" | "Ollama" | "API";
  llmModel: string;
  ollamaBaseUrl: string;
  apiKeyConfigured: boolean;
  environment: string;
  contextTtlSeconds: number;
  sourceAdapterTimeoutMs: number;
  retrievalTopK: number;
  hybridAlpha: number;
  experimentConfidenceThreshold: number;
}

export interface LLMBackendRequest {
  llmBackend: "mock" | "ollama" | "api";
  llmModel: string;
  ollamaBaseUrl: string;
  apiKey?: string;
}

export interface ConnectionTestResponse {
  ok: boolean;
  message: string;
}

export interface OllamaModelsResponse {
  ok: boolean;
  message: string;
  models: string[];
}

export interface RunPipelineRequest {
  customerId: string;
  scenario: Scenario;
  blueprint?: string;
  callerId?: string;
  trigger?: string;
}

export interface RunPipelineResponse {
  traceId: string;
  sessionId: string;
  status: "started";
}

export interface PipelineStatus {
  traceId: string;
  sessionId?: string;
  status: "started" | "running" | "completed" | "failed" | "unknown";
  customerId?: string;
  scenario?: string;
  executionResult?: ExecutionResult;
  error?: string;
}

export interface PipelineRunSummary {
  traceId: string;
  sessionId?: string;
  status: "started" | "running" | "completed" | "failed" | "unknown" | string;
  customerId?: string;
  scenario?: string;
  startedAt?: string;
  completedAt?: string;
}

export interface Experiment {
  experimentId: string;
  status: string;
  winner: string | null;
  variants: ExperimentVariant[];
}

export interface ModelVersion {
  modelId: string;
  version: string;
  role: "champion" | "challenger";
  championVersion: string;
  challengerVersion: string;
  recall: number;
  airScore: number;
  driftStatus: "stable" | "monitor" | "investigate" | "retrain";
  psi: number;
  championTraffic: number;
  challengerTraffic: number;
  psiTrend: PsiPoint[];
  gates: EvaluationGate[];
}

export interface Rule {
  ruleId: string;
  category: "REGULATORY" | "BUSINESS_POLICY" | "RESPONSIBLE_AI";
  version: string;
  description?: string;
  condition?: Record<string, unknown>;
  outcome?: "APPROVE" | "FLAG" | "BLOCK";
}

export type Decision = "APPROVED" | "REJECTED";

export interface PsiPoint {
  date: string;
  psi: number;
}

export interface EvaluationGate {
  name: string;
  status: "PASS" | "FAIL" | "MONITOR";
}

export interface OfflineGateResult {
  gate: string;
  passed: boolean;
  metrics: Record<string, number>;
  failureReason: string | null;
}

export interface EvaluationReport {
  modelName: string;
  candidateVersion: string;
  championVersion: string | null;
  gates: OfflineGateResult[];
  overallPassed: boolean;
  promotionAllowed: boolean;
  evaluatedAt: string;
  traceId: string;
}

export interface EvaluationRunRequest {
  modelName: string;
  candidateVersion: string;
}

export interface EvaluationModelOption {
  modelName: string;
  label: string;
  versions: string[];
  defaultVersion: string;
}

export interface EvaluationOptions {
  models: EvaluationModelOption[];
  storageOk: boolean;
  storageError: string | null;
}

export type LayerStatus = "idle" | "active" | "complete" | "error";

export interface LayerState {
  id: string;
  status: LayerStatus;
  latencyMs: number | null;
  summary: string | null;
  error: string | null;
}
