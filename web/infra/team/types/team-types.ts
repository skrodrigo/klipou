export type TeamMember = {
  member_id: string;
  user_id: number;
  organization_id: string;
  role: "member" | "co-leader" | "leader";
  joined_at: string;
  is_active: boolean;
};

export type InviteTeamMemberPayload = {
  email: string;
  role: "member" | "co-leader" | "leader";
};

export type InviteTeamMemberResponse = {
  detail: string;
  member: TeamMember;
};

export type ListTeamMembersResponse = {
  members: TeamMember[];
  total: number;
};

export type UpdateTeamMemberRolePayload = {
  role: "member" | "co-leader" | "leader";
};

export type UpdateTeamMemberRoleResponse = {
  detail: string;
  member: TeamMember;
};

export type RemoveTeamMemberResponse = {
  detail: string;
};
