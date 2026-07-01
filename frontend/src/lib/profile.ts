export type ProfileType = "student" | "staff" | "faculty" | "public";

const REQUIRED_FIELDS: Record<ProfileType, string[]> = {
  student: ["scope", "status", "grade", "gpa", "credits_earned", "major"],
  staff: ["department", "role"],
  faculty: ["department", "rank"],
  public: [],
};

export function profileCompleteness(
  profileType: ProfileType | string,
  profile: Record<string, unknown>,
): number {
  const required = REQUIRED_FIELDS[profileType as ProfileType] ?? [];
  if (required.length === 0) return 1;
  const filled = required.filter(
    (field) => profile[field] != null && profile[field] !== "",
  ).length;
  return filled / required.length;
}

export function completenessLabel(ratio: number): string {
  if (ratio === 0) return "프로필 미입력";
  if (ratio < 1) return `${Math.round(ratio * 100)}% 입력됨`;
  return "프로필 완성";
}

export const PROFILE_TYPE_LABELS: Record<ProfileType, string> = {
  student: "학생",
  staff: "교직원",
  faculty: "교원",
  public: "일반",
};
