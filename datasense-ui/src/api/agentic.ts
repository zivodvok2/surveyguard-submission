import { client } from './client'

export type Verdict = 'confirmed' | 'rejected' | 'review'
export type ReviewerDecision = 'pending' | 'confirmed' | 'rejected' | 'investigate'

export interface TranscriptSegment {
  start: number
  end: number
  text: string
  speaker: string
}

export interface VerifiedFinding {
  finding_id: string
  respondent_id: string
  question_id?: string | null
  category: string
  severity: 'critical' | 'warning' | 'info'
  claim: string
  evidence: Record<string, unknown>
  detector_confidence: number
  verdict: Verdict
  confidence: number
  verifier_reason: string
  reviewer_decision: ReviewerDecision
}

export interface InterviewAudit {
  respondent_id: string
  recording_name: string
  duration_seconds?: number | null
  transcript: TranscriptSegment[]
  findings: VerifiedFinding[]
}

export interface AuditReport {
  audit_id: string
  generated_at: string
  questionnaire_name: string
  dataset_name: string
  questions_extracted: number
  interviews_reviewed: number
  summary: {
    rows_checked: number
    recordings_checked: number
    candidate_findings: number
    confirmed_findings: number
    needs_human_review: number
    rejected_by_verifier: number
    critical_confirmed: number
    deterministic_flags: number
  }
  dataset_findings: VerifiedFinding[]
  interviews: InterviewAudit[]
  trajectory: { component: string; action: string; output: Record<string, unknown>; duration_ms: number }[]
}

export async function createAgenticAudit(
  questionnaire: File,
  dataset: File,
  recordings: File[],
  groqApiKey?: string,
): Promise<string> {
  const form = new FormData()
  form.append('questionnaire', questionnaire)
  form.append('dataset', dataset)
  recordings.forEach(file => form.append('recordings', file))
  form.append('column_mapping', '{}')
  if (groqApiKey) form.append('groq_api_key', groqApiKey)
  const { data } = await client.post<{ audit_id: string }>('/api/agentic/audits', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data.audit_id
}

export async function waitForAudit(auditId: string, onProgress: (progress: number) => void): Promise<AuditReport> {
  for (let attempt = 0; attempt < 360; attempt += 1) {
    const { data } = await client.get<{ status: string; progress: number; error?: string }>(`/api/agentic/audits/${auditId}/status`)
    onProgress(data.progress)
    if (data.status === 'complete') {
      const result = await client.get<AuditReport>(`/api/agentic/audits/${auditId}`)
      return result.data
    }
    if (data.status === 'failed') throw new Error(data.error || 'Audit failed')
    await new Promise(resolve => setTimeout(resolve, 1000))
  }
  throw new Error('Audit timed out')
}

export async function setFindingDecision(auditId: string, findingId: string, decision: Exclude<ReviewerDecision, 'pending'>) {
  await client.post(`/api/agentic/audits/${auditId}/findings/${findingId}/decision`, { decision })
}

export async function downloadAgenticAudit(auditId: string) {
  const response = await client.get(`/api/agentic/audits/${auditId}/export`, { responseType: 'blob' })
  const url = URL.createObjectURL(response.data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `surveyguard-audit-${auditId.slice(0, 8)}.xlsx`
  anchor.click()
  URL.revokeObjectURL(url)
}
