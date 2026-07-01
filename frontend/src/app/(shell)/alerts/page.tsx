"use client";

import Link from "next/link";
import type { ComponentType } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Bell,
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  FileText,
  Loader2,
  PlusCircle,
  RefreshCw,
  Sparkles,
  UserCog,
} from "lucide-react";

import { apiFetch, pollJob } from "@/lib/api";
import { useIdentity } from "@/lib/identity";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type ProfileType = "student" | "staff" | "faculty" | "public";
type ActionKind =
  | "profile"
  | "deadline_due"
  | "deadline_upcoming"
  | "prepared_answer"
  | "human_review"
  | "setup_watch";
type ActionUrgency = "now" | "soon" | "info" | "done";

interface DeadlineWatch {
  watch_id: string;
  issue_type: string;
  deadline: string;
  status: string;
  reminder_window_days: number;
  last_triggered_on: string | null;
  created_at: string;
  metadata?: Record<string, unknown>;
}

interface ProfileRecord {
  user_id: string;
  profile_type: ProfileType;
  profile: Record<string, unknown>;
}

interface OutboundDelivery {
  delivery_id: string;
  run_id: string | null;
  channel: string;
  status: "PENDING" | "SENT" | "FAILED";
  text: string;
  updated_at: string;
}

interface EscalationCase {
  escalation_id: string;
  session_id: string;
  user_id: string;
  reason: string;
  status: string;
  updated_at: string;
}

interface ActionItem {
  id: string;
  kind: ActionKind;
  urgency: ActionUrgency;
  title: string;
  description: string;
  meta?: string;
  cta?: string;
  href?: string;
  query?: string;
  source?: DeadlineWatch | OutboundDelivery | EscalationCase;
}

const PROFILE_REQUIRED_FIELDS: Record<ProfileType, { key: string; label: string }[]> = {
  student: [
    { key: "scope", label: "과정" },
    { key: "status", label: "재학 상태" },
    { key: "grade", label: "학년" },
    { key: "gpa", label: "GPA" },
    { key: "credits_earned", label: "취득 학점" },
    { key: "major", label: "전공" },
  ],
  staff: [
    { key: "department", label: "부서" },
    { key: "role", label: "역할" },
  ],
  faculty: [
    { key: "department", label: "학과" },
    { key: "rank", label: "직급" },
  ],
  public: [],
};

const QUICK_WATCHES = ["복수전공", "휴학", "수강신청", "졸업", "장학금"];

function isFilled(value: unknown): boolean {
  return value != null && value !== "";
}

function missingProfileFields(profile: ProfileRecord | null): string[] {
  if (!profile) return PROFILE_REQUIRED_FIELDS.student.map((field) => field.label);
  const required = PROFILE_REQUIRED_FIELDS[profile.profile_type] ?? [];
  return required
    .filter((field) => !isFilled(profile.profile[field.key]))
    .map((field) => field.label);
}

function profileRatio(profile: ProfileRecord | null): number {
  if (!profile) return 0;
  const required = PROFILE_REQUIRED_FIELDS[profile.profile_type] ?? [];
  if (required.length === 0) return 1;
  const filled = required.filter((field) => isFilled(profile.profile[field.key])).length;
  return filled / required.length;
}

function startOfToday(): Date {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function daysLeft(deadline: string): number {
  const date = new Date(deadline);
  const day = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  return Math.ceil((day.getTime() - startOfToday().getTime()) / 86_400_000);
}

function formatDate(date: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    weekday: "short",
  }).format(new Date(date));
}

function urgencyLabel(urgency: ActionUrgency): string {
  if (urgency === "now") return "지금 처리";
  if (urgency === "soon") return "곧 처리";
  if (urgency === "done") return "준비됨";
  return "확인";
}

function urgencyVariant(urgency: ActionUrgency): "default" | "secondary" | "destructive" | "outline" {
  if (urgency === "now") return "destructive";
  if (urgency === "soon") return "default";
  if (urgency === "done") return "secondary";
  return "outline";
}

function actionIcon(kind: ActionKind) {
  if (kind === "profile") return UserCog;
  if (kind === "deadline_due" || kind === "deadline_upcoming") return CalendarClock;
  if (kind === "prepared_answer") return FileText;
  if (kind === "human_review") return AlertTriangle;
  return Bell;
}

function summarizeText(text: string): string {
  const compact = text.replace(/\s+/g, " ").trim();
  return compact.length > 150 ? `${compact.slice(0, 150)}...` : compact;
}

export default function AlertsPage() {
  const identity = useIdentity();
  const [profile, setProfile] = useState<ProfileRecord | null>(null);
  const [watches, setWatches] = useState<DeadlineWatch[]>([]);
  const [outbox, setOutbox] = useState<OutboundDelivery[]>([]);
  const [escalations, setEscalations] = useState<EscalationCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [selectedDelivery, setSelectedDelivery] = useState<OutboundDelivery | null>(null);
  const [watchIssue, setWatchIssue] = useState("복수전공");
  const [watchDeadline, setWatchDeadline] = useState("");
  const [savingWatch, setSavingWatch] = useState(false);

  const loadInbox = useCallback(async () => {
    if (!identity) return;
    setLoading(true);
    setError(null);
    const [profileResult, watchResult, outboxResult, escalationResult] = await Promise.allSettled([
      apiFetch<ProfileRecord>(`/api/profiles/${encodeURIComponent(identity.userId)}`),
      apiFetch<DeadlineWatch[]>(`/api/sessions/${encodeURIComponent(identity.sessionId)}/deadline-watches`),
      apiFetch<OutboundDelivery[]>(`/api/sessions/${encodeURIComponent(identity.sessionId)}/outbox?limit=20`),
      apiFetch<EscalationCase[]>("/api/escalations"),
    ]);

    setProfile(profileResult.status === "fulfilled" ? profileResult.value : null);
    setWatches(watchResult.status === "fulfilled" ? watchResult.value : []);
    setOutbox(outboxResult.status === "fulfilled" ? outboxResult.value : []);
    setEscalations(
      escalationResult.status === "fulfilled"
        ? escalationResult.value.filter(
            (item) => item.session_id === identity.sessionId || item.user_id === identity.userId,
          )
        : [],
    );
    setLoading(false);
  }, [identity]);

  useEffect(() => {
    if (!identity) return;
    const timer = window.setTimeout(() => {
      void loadInbox().catch((err) => {
        setError(err instanceof Error ? err.message : "알림 정보를 불러오지 못했습니다.");
        setLoading(false);
      });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [identity, loadInbox]);

  const actions = useMemo<ActionItem[]>(() => {
    const items: ActionItem[] = [];
    const missingFields = missingProfileFields(profile);
    const completeness = profileRatio(profile);

    if (completeness < 1) {
      items.push({
        id: "profile",
        kind: "profile",
        urgency: "now",
        title: "학생 정보 보완 필요",
        description: `개인 상황을 알아야 복수전공, 휴학, 졸업 같은 행정 판단을 정확히 할 수 있습니다. 부족한 항목: ${missingFields.join(", ")}`,
        cta: "프로필 입력",
        href: "/profile",
      });
    }

    const activeWatches = watches.filter((watch) => watch.status === "ACTIVE");
    for (const watch of activeWatches) {
      const left = daysLeft(watch.deadline);
      if (left < 0) continue;

      if (left <= watch.reminder_window_days) {
        items.push({
          id: `due-${watch.watch_id}`,
          kind: "deadline_due",
          urgency: left <= 1 ? "now" : "soon",
          title: `${watch.issue_type} 행정 처리 확인`,
          description:
            left === 0
              ? "마감일이 오늘입니다. 제출 서류, 신청 경로, 예외 조건을 바로 확인해야 합니다."
              : `마감까지 ${left}일 남았습니다. 지금 준비해야 할 서류와 신청 절차를 확인하세요.`,
          meta: `${formatDate(watch.deadline)} 마감`,
          cta: "처리 체크리스트 생성",
          query: `${watch.issue_type} 마감이 ${left}일 남았습니다. 지금 처리해야 할 행정 절차, 자격 요건, 제출 서류를 체크리스트로 알려줘.`,
          source: watch,
        });
      } else if (left <= 30) {
        items.push({
          id: `upcoming-${watch.watch_id}`,
          kind: "deadline_upcoming",
          urgency: "info",
          title: `${watch.issue_type} 일정 사전 점검`,
          description: `마감까지 ${left}일 남았습니다. 아직 급하지는 않지만, 조건 확인과 서류 준비를 시작하기 좋습니다.`,
          meta: `${formatDate(watch.deadline)} 마감`,
          cta: "준비 항목 확인",
          query: `${watch.issue_type} 마감이 ${left}일 남았습니다. 사전에 확인해야 할 행정 조건과 준비물을 알려줘.`,
          source: watch,
        });
      }
    }

    for (const delivery of outbox.filter((item) => item.status === "PENDING").slice(0, 5)) {
      items.push({
        id: `delivery-${delivery.delivery_id}`,
        kind: "prepared_answer",
        urgency: "done",
        title: "준비된 행정 안내 확인",
        description: summarizeText(delivery.text),
        meta: new Intl.DateTimeFormat("ko-KR", {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        }).format(new Date(delivery.updated_at)),
        cta: "열어보기",
        source: delivery,
      });
    }

    for (const escalation of escalations.filter((item) => item.status !== "RESOLVED").slice(0, 3)) {
      items.push({
        id: `escalation-${escalation.escalation_id}`,
        kind: "human_review",
        urgency: "info",
        title: "담당자 확인 진행 중",
        description: escalation.reason || "규정 해석 또는 사용자 상황 확인이 필요해 담당자 검토로 전환되었습니다.",
        meta: escalation.status,
        source: escalation,
      });
    }

    if (activeWatches.length === 0) {
      items.push({
        id: "setup-watch",
        kind: "setup_watch",
        urgency: "info",
        title: "관심 행정 일정 등록",
        description:
          "복수전공, 휴학, 수강신청, 졸업, 장학금처럼 놓치면 손해가 큰 행정 업무를 등록하면 마감 전에 먼저 알려드립니다.",
      });
    }

    return items.sort((a, b) => {
      const rank: Record<ActionUrgency, number> = { now: 0, soon: 1, done: 2, info: 3 };
      return rank[a.urgency] - rank[b.urgency];
    });
  }, [escalations, outbox, profile, watches]);

  const counts = useMemo(
    () => ({
      now: actions.filter((item) => item.urgency === "now").length,
      soon: actions.filter((item) => item.urgency === "soon").length,
      done: actions.filter((item) => item.urgency === "done").length,
      review: actions.filter((item) => item.kind === "human_review").length,
    }),
    [actions],
  );

  async function prepareAnswer(action: ActionItem) {
    if (!identity || !action.query) return;
    setGeneratingId(action.id);
    setError(null);
    try {
      const submitted = await apiFetch<{ job: { job_id: string } }>("/api/gateway/web/submit", {
        method: "POST",
        body: JSON.stringify({
          message: action.query,
          user_id: identity.userId,
          session_id: identity.sessionId,
        }),
      });
      await pollJob(submitted.job.job_id);
      await loadInbox();
    } catch (err) {
      setError(err instanceof Error ? err.message : "체크리스트 생성에 실패했습니다.");
    } finally {
      setGeneratingId(null);
    }
  }

  async function registerWatch() {
    if (!identity || !watchIssue.trim() || !watchDeadline) return;
    setSavingWatch(true);
    setError(null);
    try {
      await apiFetch("/api/triggers/deadline-watches", {
        method: "POST",
        body: JSON.stringify({
          session_id: identity.sessionId,
          user_id: identity.userId,
          issue_type: watchIssue.trim(),
          deadline: watchDeadline,
          reminder_window_days: 7,
          metadata: { source: "action_inbox" },
        }),
      });
      setWatchDeadline("");
      await loadInbox();
    } catch (err) {
      setError(err instanceof Error ? err.message : "관심 일정을 등록하지 못했습니다.");
    } finally {
      setSavingWatch(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Sparkles className="size-4" />
            Proactive Action Inbox
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">행정 처리 알림</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            단순 D-day 알림이 아니라, 지금 사용자가 처리해야 할 행정 업무와 미리 준비된 답변을 모아 보여줍니다.
          </p>
        </div>
        <Button variant="outline" onClick={() => void loadInbox()} disabled={loading}>
          {loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}
          새로고침
        </Button>
      </div>

      {error ? (
        <Card className="border-destructive/30 bg-destructive/5" size="sm">
          <CardContent className="flex items-start gap-2 text-destructive">
            <AlertTriangle className="mt-0.5 size-4" />
            <span>{error}</span>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-3 md:grid-cols-4">
        <SummaryCard icon={AlertTriangle} label="지금 처리" value={counts.now} tone="text-destructive" />
        <SummaryCard icon={CalendarClock} label="곧 처리" value={counts.soon} tone="text-primary" />
        <SummaryCard icon={CheckCircle2} label="준비된 답변" value={counts.done} tone="text-emerald-600" />
        <SummaryCard icon={ClipboardList} label="담당자 확인" value={counts.review} tone="text-amber-600" />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
        <div className="flex flex-col gap-3">
          {loading ? (
            <Card>
              <CardContent className="flex items-center gap-2 py-10 text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                행정 처리 항목을 확인하는 중입니다.
              </CardContent>
            </Card>
          ) : actions.length === 0 ? (
            <Card>
              <CardContent className="flex items-center gap-2 py-10 text-muted-foreground">
                <CheckCircle2 className="size-4" />
                지금 당장 처리해야 할 행정 업무가 없습니다.
              </CardContent>
            </Card>
          ) : (
            actions.map((action) => {
              const Icon = actionIcon(action.kind);
              const delivery =
                action.kind === "prepared_answer" ? (action.source as OutboundDelivery | undefined) : undefined;
              return (
                <Card key={action.id} className="rounded-lg">
                  <CardHeader className="gap-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="flex size-8 items-center justify-center rounded-lg bg-muted">
                          <Icon className="size-4" />
                        </span>
                        <div>
                          <CardTitle>{action.title}</CardTitle>
                          {action.meta ? <CardDescription>{action.meta}</CardDescription> : null}
                        </div>
                      </div>
                      <Badge variant={urgencyVariant(action.urgency)}>{urgencyLabel(action.urgency)}</Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3">
                    <p className="text-sm leading-6 text-muted-foreground">{action.description}</p>
                    <div className="flex flex-wrap gap-2">
                      {action.href ? (
                        <Button variant="default" render={<Link href={action.href} />}>
                          {action.cta}
                        </Button>
                      ) : null}
                      {action.query ? (
                        <Button onClick={() => void prepareAnswer(action)} disabled={generatingId === action.id}>
                          {generatingId === action.id ? <Loader2 className="animate-spin" /> : <ClipboardList />}
                          {action.cta}
                        </Button>
                      ) : null}
                      {delivery ? (
                        <Button variant="outline" onClick={() => setSelectedDelivery(delivery)}>
                          <FileText />
                          {action.cta}
                        </Button>
                      ) : null}
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}
        </div>

        <div className="flex flex-col gap-4">
          {selectedDelivery ? (
            <Card className="rounded-lg">
              <CardHeader>
                <CardTitle>준비된 답변</CardTitle>
                <CardDescription>{selectedDelivery.channel} 채널에 보낼 수 있는 초안입니다.</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <div className="max-h-80 overflow-auto rounded-lg border bg-muted/30 p-3 text-sm leading-6 whitespace-pre-wrap">
                  {selectedDelivery.text}
                </div>
                <Button variant="outline" onClick={() => setSelectedDelivery(null)}>
                  닫기
                </Button>
              </CardContent>
            </Card>
          ) : null}

          <Card className="rounded-lg">
            <CardHeader>
              <CardTitle>관심 행정 업무 등록</CardTitle>
              <CardDescription>마감일이 있는 업무를 등록하면 처리 시점에 Inbox로 올라옵니다.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <div className="flex flex-wrap gap-2">
                {QUICK_WATCHES.map((issue) => (
                  <Button
                    key={issue}
                    size="xs"
                    variant={watchIssue === issue ? "default" : "outline"}
                    onClick={() => setWatchIssue(issue)}
                  >
                    {issue}
                  </Button>
                ))}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="issue">업무명</Label>
                <Input id="issue" value={watchIssue} onChange={(event) => setWatchIssue(event.target.value)} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="deadline">마감일</Label>
                <Input
                  id="deadline"
                  type="date"
                  value={watchDeadline}
                  onChange={(event) => setWatchDeadline(event.target.value)}
                />
              </div>
              <Button onClick={() => void registerWatch()} disabled={savingWatch || !watchIssue.trim() || !watchDeadline}>
                {savingWatch ? <Loader2 className="animate-spin" /> : <PlusCircle />}
                등록
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function SummaryCard({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: number;
  tone: string;
}) {
  return (
    <Card className="rounded-lg" size="sm">
      <CardContent className="flex items-center justify-between">
        <div>
          <div className="text-sm text-muted-foreground">{label}</div>
          <div className="mt-1 text-2xl font-semibold">{value}</div>
        </div>
        <Icon className={`size-5 ${tone}`} />
      </CardContent>
    </Card>
  );
}
