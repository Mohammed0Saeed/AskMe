import React, { useEffect, useState } from 'react'
import { GraduationCap, ChevronRight, Star, CheckCircle, XCircle, RotateCcw } from 'lucide-react'
import { training as trainingApi } from '../api/client'
import Card, { CardHeader } from '../components/ui/Card'
import Button from '../components/ui/Button'
import { Select, Textarea } from '../components/ui/Input'
import PageHeader from '../components/ui/PageHeader'
import EmptyState from '../components/ui/EmptyState'
import clsx from 'clsx'

const DOMAINS     = ['', 'Legal', 'Customer Service', 'HR', 'Finance', 'Technology', 'Operations', 'Marketing', 'Other']
const DIFFICULTIES = ['', 'easy', 'medium', 'hard']

function ScoreBadge({ score }) {
  const color = score >= 80 ? 'text-emerald-600' : score >= 50 ? 'text-amber-600' : 'text-brand-600'
  return <span className={clsx('text-2xl font-bold', color)}>{score}</span>
}

export default function TrainingPage() {
  const [questions, setQuestions] = useState([])
  const [progress, setProgress]   = useState(null)
  const [domain, setDomain]       = useState('')
  const [difficulty, setDifficulty] = useState('')
  const [loading, setLoading]     = useState(true)

  // Quiz state
  const [current, setCurrent]   = useState(null)
  const [answer, setAnswer]     = useState('')
  const [result, setResult]     = useState(null)
  const [evaluating, setEval]   = useState(false)

  useEffect(() => {
    Promise.all([
      trainingApi.questions().then(setQuestions).catch(() => setQuestions([])),
      trainingApi.progress().then(setProgress).catch(() => null),
    ]).finally(() => setLoading(false))
  }, [])

  const filtered = questions.filter((q) => {
    if (domain && q.domain !== domain) return false
    if (difficulty && q.difficulty !== difficulty) return false
    return true
  })

  const startQuestion = (q) => {
    setCurrent(q)
    setAnswer('')
    setResult(null)
  }

  const submit = async () => {
    if (!answer.trim() || !current) return
    setEval(true)
    try {
      const res = await trainingApi.evaluate({
        question_id:     current.question_id,
        situation:       current.situation,
        expected_answer: current.expected_answer,
        user_answer:     answer,
      })
      setResult(res)
      // Evaluate response includes updated stats — refresh progress directly
      trainingApi.progress().then(setProgress).catch(() => null)
    } catch (err) {
      setResult({ score: 0, feedback: err.message, strengths: [], improvements: [] })
    } finally {
      setEval(false)
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )

  return (
    <div className="p-6 space-y-5">
      <PageHeader icon={GraduationCap} title="Training" description="Practice scenarios based on internal knowledge" />

      {/* Progress */}
      {progress && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Completed',  value: progress.total_attempts  || 0 },
            { label: 'Avg score',  value: `${Math.round(progress.average_score || 0)}%` },
            { label: 'Streak 🔥',  value: progress.streak          || 0 },
            { label: 'Level',      value: progress.level           || 'Trainee' },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white border border-offwhite-300 rounded-2xl p-4 text-center shadow-soft">
              <p className="text-xl font-bold text-warm-900">{value}</p>
              <p className="text-[11px] text-warm-500 mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Active quiz */}
      {current ? (
        <Card>
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs text-warm-500 font-medium">
              {current.domain} · {current.difficulty}
            </span>
            <button
              onClick={() => { setCurrent(null); setResult(null) }}
              className="text-xs text-warm-400 hover:text-warm-600 flex items-center gap-1"
            >
              <RotateCcw size={11} /> Back
            </button>
          </div>

          <div className="bg-offwhite-100 rounded-xl p-4 mb-4">
            <p className="text-xs text-warm-500 mb-1 font-medium uppercase tracking-wide">Situation</p>
            <p className="text-sm text-warm-800 leading-relaxed">{current.situation}</p>
          </div>

          {!result ? (
            <>
              <Textarea
                label="Your answer"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Type your response here…"
                rows={5}
              />
              <div className="flex gap-2 mt-3">
                <Button onClick={submit} loading={evaluating} disabled={!answer.trim()}>
                  Submit answer
                </Button>
                <Button variant="secondary" onClick={() => { setCurrent(null); setResult(null) }}>
                  Skip
                </Button>
              </div>
            </>
          ) : (
            <div className="space-y-4">
              {/* Score */}
              <div className="flex items-center gap-4 bg-offwhite-50 rounded-xl p-4 border border-offwhite-300">
                <ScoreBadge score={result.score} />
                <div>
                  <p className="text-xs font-semibold text-warm-700">Score</p>
                  <p className="text-xs text-warm-500">{result.feedback}</p>
                </div>
              </div>

              {result.strengths?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-emerald-700 mb-1.5 flex items-center gap-1">
                    <CheckCircle size={12} /> Strengths
                  </p>
                  <ul className="space-y-1">
                    {result.strengths.map((s, i) => (
                      <li key={i} className="text-xs text-warm-700 pl-3 border-l-2 border-emerald-400">{s}</li>
                    ))}
                  </ul>
                </div>
              )}

              {result.improvements?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-amber-700 mb-1.5 flex items-center gap-1">
                    <XCircle size={12} /> To improve
                  </p>
                  <ul className="space-y-1">
                    {result.improvements.map((s, i) => (
                      <li key={i} className="text-xs text-warm-700 pl-3 border-l-2 border-amber-400">{s}</li>
                    ))}
                  </ul>
                </div>
              )}

              <Button onClick={() => { setCurrent(null); setResult(null) }} variant="secondary">
                Try another question
              </Button>
            </div>
          )}
        </Card>
      ) : (
        <>
          {/* Filters */}
          <div className="flex items-center gap-3">
            <Select value={domain} onChange={(e) => setDomain(e.target.value)} className="w-44 text-xs py-1.5">
              {DOMAINS.map((d) => <option key={d} value={d}>{d || 'All domains'}</option>)}
            </Select>
            <Select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} className="w-32 text-xs py-1.5">
              {DIFFICULTIES.map((d) => <option key={d} value={d}>{d || 'All levels'}</option>)}
            </Select>
          </div>

          {/* Question list */}
          <Card padding={false}>
            <CardHeader title={`${filtered.length} questions`} className="px-5 pt-5" />
            {filtered.length === 0 ? (
              <EmptyState icon={GraduationCap} title="No questions found" description="Try different filters" />
            ) : (
              <div className="divide-y divide-offwhite-200">
                {filtered.map((q) => (
                  <button
                    key={q.question_id}
                    onClick={() => startQuestion(q)}
                    className="w-full flex items-center gap-3 px-5 py-3.5 hover:bg-offwhite-50 text-left transition-all group"
                  >
                    <Star size={14} className="text-brand-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-warm-900 truncate">{q.situation?.slice(0, 80)}…</p>
                      <p className="text-[10px] text-warm-400 mt-0.5">{q.domain} · {q.difficulty}</p>
                    </div>
                    <ChevronRight size={14} className="text-warm-300 group-hover:text-brand-400 transition-all flex-shrink-0" />
                  </button>
                ))}
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
