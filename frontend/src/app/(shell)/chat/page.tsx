"use client";

import { useEffect, useRef, useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight, Loader2, Send, UserCog } from "lucide-react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";

import { apiFetch, pollJob, type CitedArticle, type CitedContentSource, type KnowledgeHandlerResult } from "@/lib/api";
import { useIdentity } from "@/lib/identity";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  createdAt: string;
  knowledge?: KnowledgeHandlerResult;
  error?: string;
}

function RegulationPath({ fullName, shortName }: { fullName: string; shortName: string }) {
  const parts = fullName.split(" > ");
  if (parts.length <= 1) {
    return (
      <span className="text-[10px] font-medium text-muted-foreground bg-muted px-1.5 py-0.5 rounded inline-block">
        {fullName}
      </span>
    );
  }
  return (
    <span
      className="text-[10px] text-muted-foreground inline-flex flex-wrap items-center gap-0.5"
      title={fullName}
    >
      {parts.map((part, i) => (
        <span key={i} className="inline-flex items-center gap-0.5">
          {i > 0 && <span className="opacity-40 select-none">›</span>}
          <span className={i === parts.length - 1 ? "font-medium text-foreground/70 bg-muted px-1 py-px rounded" : ""}>
            {part}
          </span>
        </span>
      ))}
    </span>
  );
}

function CitedRules({
  ruleIds,
  articles,
}: {
  ruleIds: string[];
  articles?: CitedArticle[];
}) {
  const [open, setOpen] = useState(false);
  const hasArticles = articles && articles.length > 0;
  const count = hasArticles ? articles.length : ruleIds.length;
  if (!count) return null;
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        근거 조항 {count}개
      </button>
      {open && (
        <div className="mt-1.5 flex flex-col gap-1.5">
          {hasArticles
            ? articles.map((a) => (
                <div
                  key={a.node_id}
                  className="rounded-lg border border-border bg-muted/30 px-2.5 py-1.5 text-xs"
                >
                  <div className="flex flex-col gap-0.5">
                    {(a.regulation_full_name || a.regulation_name) && (
                      <RegulationPath
                        fullName={a.regulation_full_name || a.regulation_name}
                        shortName={a.regulation_name}
                      />
                    )}
                    <span className="font-medium text-foreground">{a.label}</span>
                  </div>
                  {a.content_preview && (
                    <p className="mt-0.5 text-muted-foreground line-clamp-2">
                      {a.content_preview}
                    </p>
                  )}
                </div>
              ))
            : ruleIds.map((id) => (
                <Badge key={id} variant="outline" className="text-xs font-mono">
                  {id}
                </Badge>
              ))}
        </div>
      )}
    </div>
  );
}

function CitedContentSources({ sources }: { sources: CitedContentSource[] }) {
  const [open, setOpen] = useState(false);
  if (!sources.length) return null;
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        출처 공지/게시글 {sources.length}건
      </button>
      {open && (
        <div className="mt-1.5 flex flex-col gap-1.5">
          {sources.map((s, i) => (
            <div
              key={i}
              className="rounded-lg border border-border bg-muted/30 px-2.5 py-1.5 text-xs"
            >
              {s.url ? (
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-primary underline underline-offset-2 hover:no-underline"
                >
                  {s.title}
                </a>
              ) : (
                <span className="font-medium text-foreground">{s.title}</span>
              )}
              {(s.category || s.issuing_office) && (
                <p className="mt-0.5 text-muted-foreground">
                  {[s.issuing_office, s.category].filter(Boolean).join(" · ")}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ProfileGapsHint({ gaps }: { gaps: string[] }) {
  if (!gaps.length) return null;
  return (
    <div className="mt-2 flex items-start gap-2 bg-amber-50 dark:bg-amber-950/30 text-amber-800 dark:text-amber-300 rounded-lg px-3 py-2 text-xs">
      <UserCog size={14} className="mt-0.5 shrink-0" />
      <div>
        <p className="font-medium mb-0.5">프로필을 채우면 더 정확한 답변을 받을 수 있어요</p>
        <Link href="/profile" className="underline underline-offset-2 hover:no-underline">
          내 정보 입력하기 →
        </Link>
      </div>
    </div>
  );
}

function AnswerMarkdown({ text }: { text: string }) {
  return (
    <ReactMarkdown
      components={{
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
        ol: ({ children }) => <ol className="mt-1.5 mb-2 flex flex-col gap-1.5 pl-4 list-decimal">{children}</ol>,
        ul: ({ children }) => <ul className="mt-1.5 mb-2 flex flex-col gap-1 pl-4 list-disc">{children}</ul>,
        li: ({ children }) => <li className="leading-snug">{children}</li>,
        h3: ({ children }) => <p className="mt-2 mb-1 font-semibold text-foreground">{children}</p>,
        h4: ({ children }) => <p className="mt-1.5 mb-0.5 font-medium text-foreground">{children}</p>,
        hr: () => <hr className="my-2 border-border" />,
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

function AssistantBubble({ msg }: { msg: ChatMessage }) {
  return (
    <div className="flex flex-col gap-1 max-w-[85%]">
      <div className="rounded-2xl rounded-tl-sm bg-card ring-1 ring-foreground/10 px-4 py-3 text-sm leading-relaxed">
        <AnswerMarkdown text={msg.text} />
        {msg.knowledge && (
          <>
            <CitedRules
              ruleIds={msg.knowledge.cited_rule_ids}
              articles={msg.knowledge.cited_articles}
            />
            <CitedContentSources sources={msg.knowledge.cited_content_sources ?? []} />
            <ProfileGapsHint gaps={msg.knowledge.profile_gaps} />
          </>
        )}
        {msg.knowledge?.requires_human_review && (
          <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
            <AlertTriangle size={12} className="text-amber-500" />
            담당자가 확인 중입니다
          </div>
        )}
        {msg.error && (
          <p className="mt-1 text-xs text-destructive">{msg.error}</p>
        )}
      </div>
      <p className="text-[10px] text-muted-foreground px-1">
        {new Date(msg.createdAt).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}
      </p>
    </div>
  );
}

function UserBubble({ msg }: { msg: ChatMessage }) {
  return (
    <div className="flex flex-col items-end gap-1 max-w-[85%] self-end">
      <div className="rounded-2xl rounded-tr-sm bg-primary text-primary-foreground px-4 py-3 text-sm leading-relaxed">
        {msg.text}
      </div>
      <p className="text-[10px] text-muted-foreground px-1">
        {new Date(msg.createdAt).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}
      </p>
    </div>
  );
}

export default function ChatPage() {
  const identity = useIdentity();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [hasProfile, setHasProfile] = useState<boolean | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!identity) return;
    loadHistory();
    loadSuggestions();
    checkProfile();
  }, [identity]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function loadHistory() {
    if (!identity) return;
    try {
      const turns = await apiFetch<
        Array<{ turn_id: string; role: string; text: string; created_at: string }>
      >(`/api/sessions/${encodeURIComponent(identity.sessionId)}/history?limit=40`);
      const chatMsgs: ChatMessage[] = (turns ?? [])
        .filter((t) => t.role !== "SYSTEM")
        .map((t) => ({
          id: t.turn_id,
          role: t.role === "USER" ? "user" : "assistant",
          text: t.text,
          createdAt: t.created_at,
        }));
      setMessages(chatMsgs);
    } catch {/* ignore */}
  }

  async function checkProfile() {
    if (!identity) return;
    try {
      const data = await apiFetch<{ profile_type?: string; profile?: Record<string, unknown> } | null>(
        `/api/profiles/${encodeURIComponent(identity.userId)}`,
      );
      setHasProfile(Boolean(data && data.profile_type));
    } catch {
      setHasProfile(false);
    }
  }

  async function loadSuggestions() {
    if (!identity) return;
    try {
      const persona = await apiFetch<{ predicted_questions?: string[] }>(
        `/api/sessions/${encodeURIComponent(identity.sessionId)}/persona`,
      );
      setSuggestions(persona?.predicted_questions ?? []);
    } catch {/* no persona yet */}
  }

  async function send(query: string) {
    if (!identity || !query.trim() || sending) return;
    const q = query.trim();
    setText("");
    setSuggestions([]);
    setSending(true);

    const userMsg: ChatMessage = {
      id: `local-${Date.now()}`,
      role: "user",
      text: q,
      createdAt: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    const loadingMsg: ChatMessage = {
      id: `loading-${Date.now()}`,
      role: "assistant",
      text: "…",
      createdAt: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, loadingMsg]);

    try {
      const submitRes = await apiFetch<{ job: { job_id: string } }>(
        `/api/gateway/web/submit`,
        {
          method: "POST",
          body: JSON.stringify({
            message: q,
            user_id: identity.userId,
            session_id: identity.sessionId,
          }),
        },
      );

      const jobId = submitRes.job?.job_id;
      if (!jobId) throw new Error("job_id 없음");

      const result = await pollJob(jobId);

      const responseText = result.final?.response ?? "답변을 가져오지 못했습니다.";
      const knowledgeWorker = result.worker_results?.find(
        (w) => w.node_id === "knowledge_query",
      );

      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? {
                ...m,
                text: responseText,
                knowledge: knowledgeWorker?.handler_result,
                createdAt: new Date().toISOString(),
              }
            : m,
        ),
      );
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? { ...m, text: "오류가 발생했습니다.", error: String(err) }
            : m,
        ),
      );
    } finally {
      setSending(false);
      textareaRef.current?.focus();
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    send(text);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(text);
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* 헤더 */}
      <div className="shrink-0 border-b px-4 py-3 flex items-center justify-between">
        <div>
          <h1 className="font-semibold text-sm">학사 AI 도우미</h1>
          <p className="text-xs text-muted-foreground">규정·절차·일정을 물어보세요</p>
        </div>
        {identity && (
          <span className="text-[10px] text-muted-foreground hidden sm:block truncate max-w-40">
            {identity.userId}
          </span>
        )}
      </div>

      {/* 프로필 미등록 온보딩 배너 */}
      {hasProfile === false && (
        <div className="shrink-0 bg-amber-50 dark:bg-amber-950/30 border-b border-amber-200 dark:border-amber-800 px-4 py-2.5 flex items-center justify-between gap-3">
          <p className="text-xs text-amber-800 dark:text-amber-300 leading-snug">
            <span className="font-medium">내 정보를 입력하면</span> 학년·학점 기반으로 규정 근거를 직접 인용해 드립니다.
          </p>
          <Link
            href="/profile"
            className="shrink-0 text-xs font-medium text-amber-900 dark:text-amber-200 underline underline-offset-2 whitespace-nowrap"
          >
            내 정보 입력 →
          </Link>
        </div>
      )}

      {/* 추천 질문 칩 */}
      {suggestions.length > 0 && (
        <div className="shrink-0 px-4 py-2 border-b flex gap-2 overflow-x-auto no-scrollbar">
          {suggestions.map((s, i) => (
            <button
              key={i}
              type="button"
              onClick={() => send(s)}
              disabled={sending}
              className="shrink-0 text-xs px-3 py-1.5 rounded-full border border-border bg-muted/50 hover:bg-muted transition-colors whitespace-nowrap"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* 메시지 목록 */}
      <ScrollArea className="flex-1 min-h-0">
        <div className="flex flex-col gap-4 px-4 py-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
              <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center text-xl">
                💬
              </div>
              <p className="text-sm font-medium">무엇이든 물어보세요</p>
              <p className="text-xs text-muted-foreground max-w-60">
                복수전공, 휴학, 수강신청, 장학금 등 학사 규정에 대해 질문해 보세요
              </p>
            </div>
          )}

          {messages.map((msg) =>
            msg.role === "user" ? (
              <UserBubble key={msg.id} msg={msg} />
            ) : (
              <div key={msg.id} className="flex items-start gap-2">
                {msg.text === "…" ? (
                  <div className="flex items-center gap-2 px-4 py-3 rounded-2xl rounded-tl-sm bg-card ring-1 ring-foreground/10">
                    <Loader2 size={14} className="animate-spin text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">답변 생성 중…</span>
                  </div>
                ) : (
                  <AssistantBubble msg={msg} />
                )}
              </div>
            ),
          )}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* 입력창 */}
      <div className="shrink-0 border-t bg-background px-4 py-3">
        <form onSubmit={handleSubmit} className="flex gap-2 items-end">
          <Textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="복수전공 신청 기간과 준비 서류를 알려줘"
            className="resize-none max-h-32 min-h-[2.5rem]"
            disabled={sending || !identity}
          />
          <Button
            type="submit"
            size="icon"
            disabled={sending || !text.trim() || !identity}
            className="shrink-0"
          >
            <Send size={16} />
          </Button>
        </form>
        <p className="text-[10px] text-muted-foreground mt-1.5">
          Enter로 전송 · Shift+Enter로 줄바꿈
        </p>
      </div>
    </div>
  );
}
