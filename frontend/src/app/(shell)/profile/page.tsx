"use client";

import { useEffect, useState } from "react";
import { CheckCircle, Circle } from "lucide-react";

import { apiFetch } from "@/lib/api";
import { useIdentity } from "@/lib/identity";
import {
  completenessLabel,
  profileCompleteness,
  PROFILE_TYPE_LABELS,
  type ProfileType,
} from "@/lib/profile";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Fields = Record<string, unknown>;

const COLLEGE_OPTIONS = [
  { value: "", label: "선택 안 함" },
  { value: "informatics", label: "정보대학 (컴퓨터학과·데이터과학·AI)" },
  { value: "engineering", label: "공과대학" },
  { value: "business", label: "경영대학" },
  { value: "political_science_economics", label: "정경대학" },
  { value: "liberal_arts", label: "문과대학" },
  { value: "science", label: "이과대학" },
  { value: "life_sciences", label: "생명과학대학" },
  { value: "medicine", label: "의과대학" },
  { value: "nursing", label: "간호대학" },
  { value: "education", label: "사범대학" },
  { value: "law", label: "법과대학" },
];

const DEPARTMENT_OPTIONS: Record<string, { value: string; label: string }[]> = {
  informatics: [
    { value: "", label: "선택 안 함" },
    { value: "cs", label: "컴퓨터학과" },
    { value: "data_science", label: "데이터과학과" },
    { value: "ai", label: "인공지능학과" },
  ],
};

const STUDENT_SCOPE_OPTIONS = [
  { value: "undergraduate", label: "학부" },
  { value: "graduate", label: "대학원" },
];

const STATUS_OPTIONS = [
  { value: "enrolled", label: "재학" },
  { value: "leave", label: "휴학" },
  { value: "graduated", label: "졸업" },
  { value: "suspended", label: "제적" },
];

const GOAL_OPTIONS = [
  { value: "unknown", label: "미정" },
  { value: "graduate_school", label: "대학원 진학" },
  { value: "early_graduation", label: "조기졸업" },
  { value: "double_major", label: "복수전공" },
  { value: "career", label: "취업" },
];

const ADMISSION_TYPE_OPTIONS = [
  { value: "regular", label: "신입학" },
  { value: "transfer", label: "편입학" },
];

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      {children}
    </div>
  );
}

function SelectField({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

const INITIAL_STUDENT: Fields = {
  scope: "undergraduate",
  status: "enrolled",
  grade: 1,
  gpa: 0.0,
  credits_earned: 0,
  major: "",
  college_tag: "",
  department_tag: "",
  admission_year: "",
  has_scholarship: false,
  scholarship_type: "",
  goal: "unknown",
  double_major: "",
  leave_count: 0,
  probation_count: 0,
  is_military_leave: false,
  semester_credits: "",
  admission_type: "regular",
};

const INITIAL_STAFF: Fields = { department: "", role: "", years_of_service: 0 };
const INITIAL_FACULTY: Fields = { department: "", rank: "", is_tenured: false, research_area: "" };
const INITIAL_PUBLIC: Fields = { purpose: "general", affiliation: "" };

const INITIAL_MAP: Record<ProfileType, Fields> = {
  student: INITIAL_STUDENT,
  staff: INITIAL_STAFF,
  faculty: INITIAL_FACULTY,
  public: INITIAL_PUBLIC,
};

export default function ProfilePage() {
  const identity = useIdentity();
  const [profileType, setProfileType] = useState<ProfileType>("student");
  const [fields, setFields] = useState<Fields>({ ...INITIAL_STUDENT });
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!identity) return;
    apiFetch<{ profile_type?: string; profile?: Fields }>(
      `/api/profiles/${encodeURIComponent(identity.userId)}`,
    )
      .then((data) => {
        if (data.profile_type) setProfileType(data.profile_type as ProfileType);
        if (data.profile) setFields({ ...INITIAL_MAP[data.profile_type as ProfileType] ?? {}, ...data.profile });
      })
      .catch(() => {/* no existing profile */});
  }, [identity]);

  function set(key: string, value: unknown) {
    setFields((prev) => ({ ...prev, [key]: value }));
  }

  function switchType(t: ProfileType) {
    setProfileType(t);
    setFields({ ...INITIAL_MAP[t] });
  }

  async function save() {
    if (!identity) return;
    setSaving(true);
    setError(null);
    try {
      await apiFetch(`/api/profiles/${encodeURIComponent(identity.userId)}`, {
        method: "PUT",
        body: JSON.stringify({ user_id: identity.userId, profile_type: profileType, profile: fields }),
      });
      setSavedAt(new Date().toLocaleString("ko-KR"));
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  const ratio = profileCompleteness(profileType, fields);

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="sticky top-0 bg-background z-10 border-b px-4 py-3 flex items-center justify-between gap-4">
        <div>
          <h1 className="font-semibold text-sm">내 정보</h1>
          <p className="text-xs text-muted-foreground">
            프로필을 채울수록 더 정확한 규정 답변을 받을 수 있어요
          </p>
        </div>
        <Badge
          variant={ratio === 1 ? "default" : ratio === 0 ? "destructive" : "secondary"}
          className="shrink-0"
        >
          {ratio === 1 ? (
            <CheckCircle size={10} className="mr-1" />
          ) : (
            <Circle size={10} className="mr-1" />
          )}
          {completenessLabel(ratio)}
        </Badge>
      </div>

      <div className="flex-1 px-4 py-4 max-w-lg w-full mx-auto space-y-6">
        {identity && (
          <div className="text-xs text-muted-foreground bg-muted/50 rounded-lg px-3 py-2">
            <span className="font-medium">사용자 ID</span>: {identity.userId}
          </div>
        )}

        {/* 사용자 유형 */}
        <div className="space-y-2">
          <Label className="text-xs text-muted-foreground">사용자 유형</Label>
          <div className="flex gap-2 flex-wrap">
            {(Object.entries(PROFILE_TYPE_LABELS) as [ProfileType, string][]).map(([t, label]) => (
              <button
                key={t}
                type="button"
                onClick={() => switchType(t)}
                className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                  profileType === t
                    ? "bg-primary text-primary-foreground border-primary"
                    : "border-border text-muted-foreground hover:bg-muted"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* 학생 필드 */}
        {profileType === "student" && (
          <>
            <section className="space-y-3">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">기본 정보</p>
              <FieldRow label="과정">
                <SelectField value={String(fields.scope ?? "undergraduate")} onChange={(v) => set("scope", v)} options={STUDENT_SCOPE_OPTIONS} />
              </FieldRow>
              <FieldRow label="재학 상태">
                <SelectField value={String(fields.status ?? "enrolled")} onChange={(v) => set("status", v)} options={STATUS_OPTIONS} />
              </FieldRow>
              <div className="grid grid-cols-2 gap-3">
                <FieldRow label="학년">
                  <Input type="number" min={1} max={10} value={String(fields.grade ?? 1)} onChange={(e) => set("grade", Number(e.target.value))} />
                </FieldRow>
                <FieldRow label="입학연도">
                  <Input type="number" min={2000} max={2030} placeholder="2022" value={String(fields.admission_year ?? "")} onChange={(e) => set("admission_year", e.target.value ? Number(e.target.value) : "")} />
                </FieldRow>
              </div>
              <FieldRow label="전공">
                <Input placeholder="예: 컴퓨터학과" value={String(fields.major ?? "")} onChange={(e) => set("major", e.target.value)} />
              </FieldRow>
              <FieldRow label="입학 유형">
                <SelectField value={String(fields.admission_type ?? "regular")} onChange={(v) => set("admission_type", v)} options={ADMISSION_TYPE_OPTIONS} />
              </FieldRow>
            </section>

            <section className="space-y-3">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">학업 현황</p>
              <div className="grid grid-cols-2 gap-3">
                <FieldRow label="GPA">
                  <Input type="number" step={0.01} min={0} max={4.5} placeholder="3.50" value={String(fields.gpa ?? 0)} onChange={(e) => set("gpa", Number(e.target.value))} />
                </FieldRow>
                <FieldRow label="취득 학점">
                  <Input type="number" min={0} max={300} value={String(fields.credits_earned ?? 0)} onChange={(e) => set("credits_earned", Number(e.target.value))} />
                </FieldRow>
              </div>
              <FieldRow label="이번 학기 수강 학점 (선택)">
                <Input type="number" min={0} max={30} placeholder="18" value={String(fields.semester_credits ?? "")} onChange={(e) => set("semester_credits", e.target.value ? Number(e.target.value) : "")} />
              </FieldRow>
              <FieldRow label="복수전공 (선택)">
                <Input placeholder="예: 경영학과" value={String(fields.double_major ?? "")} onChange={(e) => set("double_major", e.target.value)} />
              </FieldRow>
              <div className="grid grid-cols-2 gap-3">
                <FieldRow label="휴학 횟수">
                  <Input type="number" min={0} max={10} value={String(fields.leave_count ?? 0)} onChange={(e) => set("leave_count", Number(e.target.value))} />
                </FieldRow>
                <FieldRow label="학사경고 횟수">
                  <Input type="number" min={0} max={10} value={String(fields.probation_count ?? 0)} onChange={(e) => set("probation_count", Number(e.target.value))} />
                </FieldRow>
              </div>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={Boolean(fields.is_military_leave)} onChange={(e) => set("is_military_leave", e.target.checked)} className="rounded" />
                군 휴학 중
              </label>
            </section>

            <section className="space-y-3">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">장학금</p>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={Boolean(fields.has_scholarship)} onChange={(e) => set("has_scholarship", e.target.checked)} className="rounded" />
                장학금 수령 중
              </label>
              {Boolean(fields.has_scholarship) && (
                <FieldRow label="장학금 종류">
                  <Input placeholder="예: merit, need_based, national" value={String(fields.scholarship_type ?? "")} onChange={(e) => set("scholarship_type", e.target.value)} />
                </FieldRow>
              )}
            </section>

            <section className="space-y-3">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">관심 분야 (선택)</p>
              <FieldRow label="목표">
                <SelectField value={String(fields.goal ?? "unknown")} onChange={(v) => set("goal", v)} options={GOAL_OPTIONS} />
              </FieldRow>
              <FieldRow label="단과대학">
                <SelectField
                  value={String(fields.college_tag ?? "")}
                  onChange={(v) => {
                    set("college_tag", v || undefined);
                    set("department_tag", undefined);
                  }}
                  options={COLLEGE_OPTIONS}
                />
                {!fields.college_tag && (
                  <p className="text-[10px] text-amber-600 mt-1">
                    단과대학을 선택하면 단과대별 공지와 행정실 연락처를 답변에 반영할 수 있습니다.
                  </p>
                )}
              </FieldRow>
              <FieldRow label="학과">
                {DEPARTMENT_OPTIONS[String(fields.college_tag ?? "")] ? (
                  <SelectField
                    value={String(fields.department_tag ?? "")}
                    onChange={(v) => set("department_tag", v || undefined)}
                    options={DEPARTMENT_OPTIONS[String(fields.college_tag ?? "")]}
                  />
                ) : (
                  <Input placeholder="예: cs, ai (선택)" value={String(fields.department_tag ?? "")} onChange={(e) => set("department_tag", e.target.value || undefined)} />
                )}
              </FieldRow>
            </section>
          </>
        )}

        {/* 교직원 필드 */}
        {profileType === "staff" && (
          <section className="space-y-3">
            <FieldRow label="소속 부서">
              <Input placeholder="예: 학사팀" value={String(fields.department ?? "")} onChange={(e) => set("department", e.target.value)} />
            </FieldRow>
            <FieldRow label="담당 역할">
              <Input placeholder="예: 수강신청 담당" value={String(fields.role ?? "")} onChange={(e) => set("role", e.target.value)} />
            </FieldRow>
            <FieldRow label="근속 연수">
              <Input type="number" min={0} value={String(fields.years_of_service ?? 0)} onChange={(e) => set("years_of_service", Number(e.target.value))} />
            </FieldRow>
          </section>
        )}

        {/* 교원 필드 */}
        {profileType === "faculty" && (
          <section className="space-y-3">
            <FieldRow label="소속 학과">
              <Input placeholder="예: 컴퓨터학과" value={String(fields.department ?? "")} onChange={(e) => set("department", e.target.value)} />
            </FieldRow>
            <FieldRow label="직급">
              <Input placeholder="예: 교수, 부교수" value={String(fields.rank ?? "")} onChange={(e) => set("rank", e.target.value)} />
            </FieldRow>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={Boolean(fields.is_tenured)} onChange={(e) => set("is_tenured", e.target.checked)} className="rounded" />
              정년 보장
            </label>
            <FieldRow label="연구 분야 (선택)">
              <Input placeholder="예: 머신러닝" value={String(fields.research_area ?? "")} onChange={(e) => set("research_area", e.target.value)} />
            </FieldRow>
          </section>
        )}

        {/* 일반인 필드 */}
        {profileType === "public" && (
          <section className="space-y-3">
            <FieldRow label="문의 목적">
              <Input placeholder="예: 입학 문의, 학사 정보 조회" value={String(fields.purpose ?? "general")} onChange={(e) => set("purpose", e.target.value)} />
            </FieldRow>
            <FieldRow label="소속 (선택)">
              <Input placeholder="선택 입력" value={String(fields.affiliation ?? "")} onChange={(e) => set("affiliation", e.target.value)} />
            </FieldRow>
          </section>
        )}

        {error && (
          <p className="text-xs text-destructive bg-destructive/10 px-3 py-2 rounded-lg">{error}</p>
        )}
        {savedAt && (
          <p className="text-xs text-muted-foreground">마지막 저장: {savedAt}</p>
        )}

        <Button onClick={save} disabled={saving || !identity} className="w-full">
          {saving ? "저장 중…" : "저장"}
        </Button>

        <div className="pb-6" />
      </div>
    </div>
  );
}
