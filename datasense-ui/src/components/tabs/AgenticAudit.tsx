import React, { useMemo, useState } from 'react'
import {
  AudioLines, BookOpenCheck, CheckCircle2, ChevronDown, ChevronRight,
  Download, FileSpreadsheet, FileText, Loader2, SearchCheck, ShieldAlert,
  Sparkles, UploadCloud, XCircle,
} from 'lucide-react'
import { useAppStore } from '../../store/appStore'
import {
  type AuditReport, type ReviewerDecision, type VerifiedFinding,
  createAgenticAudit, downloadAgenticAudit, setFindingDecision, waitForAudit,
} from '../../api/agentic'

const pretty = (value: string) => value.replace(/_/g, ' ').replace(/\b\w/g, (letter: string) => letter.toUpperCase())
const time = (value: unknown) => typeof value === 'number' ? `${Math.floor(value / 60)}:${String(Math.round(value % 60)).padStart(2, '0')}` : '—'

function FileBox({ icon: Icon, title, description, accept, multiple, onChange, value }: {
  icon: React.ElementType; title: string; description: string; accept: string; multiple?: boolean;
  onChange: (files: File[]) => void; value: File[];
}) {
  return (
    <label className="card min-h-44 p-5 flex flex-col items-center justify-center text-center cursor-pointer hover:border-accent transition-colors group">
      <div className="w-11 h-11 rounded-xl bg-accent/10 text-accent flex items-center justify-center mb-3 group-hover:bg-accent/20 transition-colors"><Icon size={21} /></div>
      <p className="font-display font-bold text-sm text-tx">{title}</p>
      <p className="text-xs text-muted mt-1 max-w-56">{description}</p>
      <input className="sr-only" type="file" accept={accept} multiple={multiple} onChange={event => onChange(Array.from(event.target.files || []))} />
      <div className="mt-3 text-[11px] text-accent font-semibold">
        {value.length ? (multiple ? `${value.length} files selected` : value[0].name) : 'Choose file'}
      </div>
    </label>
  )
}

function FindingCard({ finding, auditId, onDecision }: { finding: VerifiedFinding; auditId: string; onDecision: (id: string, decision: Exclude<ReviewerDecision, 'pending'>) => void }) {
  const [open, setOpen] = useState(false)
  const timestamp = finding.evidence.timestamp as { start?: number; end?: number } | undefined
  return (
    <div className="card overflow-hidden">
      <button onClick={() => setOpen(!open)} className="w-full p-4 flex items-start gap-3 text-left">
        <div className={`mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center ${finding.verdict === 'confirmed' ? 'bg-navy/10 text-navy' : finding.verdict === 'review' ? 'bg-accent/10 text-accent' : 'bg-surface2 text-muted'}`}>
          {finding.verdict === 'confirmed' ? <ShieldAlert size={16} /> : finding.verdict === 'review' ? <SearchCheck size={16} /> : <CheckCircle2 size={16} />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={finding.verdict === 'confirmed' ? 'badge-critical' : finding.verdict === 'review' ? 'badge-warning' : 'badge-info'}>{finding.verdict}</span>
            <span className="text-[11px] text-muted">{finding.respondent_id}</span>
            {finding.question_id && <span className="text-[11px] font-semibold text-accent">{finding.question_id}</span>}
            {timestamp && <span className="text-[11px] text-muted">{time(timestamp.start)}–{time(timestamp.end)}</span>}
          </div>
          <p className="text-sm font-semibold text-tx mt-2">{finding.claim}</p>
          <p className="text-xs text-muted mt-1">{pretty(finding.category)} · {(finding.confidence * 100).toFixed(0)}% verification confidence</p>
        </div>
        {open ? <ChevronDown size={16} className="text-muted" /> : <ChevronRight size={16} className="text-muted" />}
      </button>
      {open && (
        <div className="border-t border-line px-4 py-4 bg-surface2/40 space-y-4">
          <div>
            <p className="label mb-1">Independent verifier</p>
            <p className="text-sm text-tx">{finding.verifier_reason}</p>
          </div>
          <div>
            <p className="label mb-2">Evidence</p>
            <div className="grid sm:grid-cols-2 gap-2">
              {Object.entries(finding.evidence).filter(([key]) => key !== 'timestamp').map(([key, value]) => (
                <div key={key} className="rounded-lg bg-surface border border-line p-3 min-w-0">
                  <p className="text-[10px] uppercase tracking-wide text-muted">{pretty(key)}</p>
                  <p className="text-xs text-tx mt-1 break-words">{typeof value === 'object' ? JSON.stringify(value) : String(value ?? '—')}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted mr-1">Reviewer decision:</span>
            {(['confirmed', 'rejected', 'investigate'] as const).map(decision => (
              <button key={decision} onClick={() => onDecision(finding.finding_id, decision)} className={`btn-ghost text-xs ${finding.reviewer_decision === decision ? 'border-accent text-accent' : ''}`}>{pretty(decision)}</button>
            ))}
            {finding.reviewer_decision !== 'pending' && <span className="badge-success ml-auto">Saved</span>}
          </div>
        </div>
      )}
    </div>
  )
}

export function AgenticAudit() {
  const groqApiKey = useAppStore(state => state.groqApiKey)
  const [questionnaire, setQuestionnaire] = useState<File[]>([])
  const [dataset, setDataset] = useState<File[]>([])
  const [recordings, setRecordings] = useState<File[]>([])
  const [report, setReport] = useState<AuditReport | null>(null)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)
  const [filter, setFilter] = useState<'all' | 'confirmed' | 'review' | 'rejected'>('all')

  const findings = useMemo(() => {
    if (!report) return []
    const all = [...report.dataset_findings, ...report.interviews.flatMap(interview => interview.findings)]
    return filter === 'all' ? all : all.filter(finding => finding.verdict === filter)
  }, [report, filter])

  async function run() {
    if (!questionnaire[0] || !dataset[0] || !recordings.length) return
    setRunning(true); setError(''); setReport(null); setProgress(3)
    try {
      const auditId = await createAgenticAudit(questionnaire[0], dataset[0], recordings, groqApiKey || undefined)
      const result = await waitForAudit(auditId, setProgress)
      setReport(result)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The audit could not be completed')
    } finally {
      setRunning(false)
    }
  }

  async function decide(id: string, decision: Exclude<ReviewerDecision, 'pending'>) {
    if (!report) return
    await setFindingDecision(report.audit_id, id, decision)
    const update = (finding: VerifiedFinding) => finding.finding_id === id ? { ...finding, reviewer_decision: decision } : finding
    setReport({ ...report, dataset_findings: report.dataset_findings.map(update), interviews: report.interviews.map(interview => ({ ...interview, findings: interview.findings.map(update) })) })
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-10">
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 text-accent text-xs font-bold uppercase tracking-widest mb-2"><Sparkles size={13} /> Agentic multimodal QC</div>
          <h1 className="font-display text-3xl font-extrabold text-tx">SurveyGuard Audit</h1>
          <p className="text-sm text-muted mt-2 max-w-3xl">Review the questionnaire, captured data, and completed interview recordings together. The verifier rejects weak AI flags before they reach the human review queue.</p>
        </div>
        {report && <button onClick={() => downloadAgenticAudit(report.audit_id)} className="btn-primary flex items-center gap-2"><Download size={15} /> Export evidence report</button>}
      </div>

      {!report && (
        <>
          <div className="grid md:grid-cols-3 gap-4">
            <FileBox icon={FileText} title="1. Questionnaire" description="PDF, DOCX, TXT, MD, or structured JSON" accept=".pdf,.docx,.txt,.md,.json" onChange={setQuestionnaire} value={questionnaire} />
            <FileBox icon={FileSpreadsheet} title="2. Survey dataset" description="Captured respondent values and verbatims" accept=".csv,.tsv,.xlsx,.xls,.sav,.parquet" onChange={setDataset} value={dataset} />
            <FileBox icon={AudioLines} title="3. Recordings" description="Audio files, or timestamped JSON/SRT/VTT transcripts for a key-free demo" accept="audio/*,video/mp4,.json,.txt,.srt,.vtt" multiple onChange={setRecordings} value={recordings} />
          </div>
          <div className="card p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <BookOpenCheck size={18} className="text-accent mt-0.5" />
              <div><p className="text-sm font-semibold text-tx">Audio is post-interview evidence</p><p className="text-xs text-muted mt-0.5">SurveyGuard never takes punitive action. Confirmed and uncertain findings remain reviewer decisions.</p></div>
            </div>
            <button disabled={running || !questionnaire[0] || !dataset[0] || !recordings.length} onClick={run} className="btn-primary min-w-44 flex items-center justify-center gap-2">
              {running ? <Loader2 size={16} className="animate-spin" /> : <UploadCloud size={16} />}{running ? `Auditing ${progress}%` : 'Run multimodal audit'}
            </button>
          </div>
          {running && <div className="h-2 rounded-full bg-line overflow-hidden"><div className="h-full bg-accent transition-all duration-500" style={{ width: `${Math.max(progress, 5)}%` }} /></div>}
          {error && <div className="card border-navy/30 p-4 flex items-center gap-3 text-sm text-navy"><XCircle size={17} /> {error}</div>}
        </>
      )}

      {report && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            {[
              ['Recordings', report.summary.recordings_checked], ['Confirmed', report.summary.confirmed_findings], ['Human review', report.summary.needs_human_review], ['Rejected', report.summary.rejected_by_verifier], ['Questions', report.questions_extracted],
            ].map(([label, value]) => <div className="kpi-card" key={String(label)}><p className="label">{label}</p><p className="font-display text-2xl font-extrabold text-tx mt-1">{value}</p></div>)}
          </div>

          <div className="grid lg:grid-cols-[1fr_300px] gap-5 items-start">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div><h2 className="font-display font-bold text-lg text-tx">Evidence-backed findings</h2><p className="text-xs text-muted">{findings.length} findings in the current view</p></div>
                <div className="flex gap-1 rounded-lg bg-surface2 p-1">
                  {(['all', 'confirmed', 'review', 'rejected'] as const).map(item => <button key={item} onClick={() => setFilter(item)} className={`px-3 py-1.5 rounded-md text-xs capitalize ${filter === item ? 'bg-surface text-accent shadow-sm' : 'text-muted hover:text-tx'}`}>{item}</button>)}
                </div>
              </div>
              {findings.map(finding => <FindingCard key={finding.finding_id} finding={finding} auditId={report.audit_id} onDecision={decide} />)}
              {!findings.length && <div className="card p-10 text-center"><CheckCircle2 className="mx-auto text-accent" /><p className="text-sm font-semibold mt-3">No findings in this view</p></div>}
            </div>

            <aside className="space-y-4 lg:sticky lg:top-4">
              <div className="card p-4"><p className="label mb-3">Agent trajectory</p><div className="space-y-3">{report.trajectory.map((step, index) => <div key={`${step.component}-${index}`} className="flex gap-3"><div className="w-6 h-6 rounded-full bg-accent/10 text-accent flex items-center justify-center text-[10px] font-bold shrink-0">{index + 1}</div><div><p className="text-xs font-semibold text-tx">{pretty(step.component)}</p><p className="text-[11px] text-muted">{pretty(step.action)} · {step.duration_ms} ms</p></div></div>)}</div></div>
              <div className="card p-4"><p className="label mb-3">Recordings reviewed</p><div className="space-y-2">{report.interviews.map(interview => <div key={interview.recording_name} className="rounded-lg border border-line p-3"><p className="text-xs font-semibold truncate">{interview.recording_name}</p><p className="text-[11px] text-muted mt-1">{interview.respondent_id} · {time(interview.duration_seconds)} · {interview.transcript.length} segments</p></div>)}</div></div>
            </aside>
          </div>

          <div className="flex justify-center"><button className="btn-ghost" onClick={() => { setReport(null); setProgress(0) }}>Start another audit</button></div>
        </>
      )}
    </div>
  )
}
