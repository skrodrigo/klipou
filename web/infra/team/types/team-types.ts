export type TeamMember = {
  membership_id: string;
  user_id: string;
  role: "member" | "admin";
  joined_at: string;
};

export type InviteTeamMemberPayload = {
  email: string;
  role: "member" | "admin";
};

export type InviteTeamMemberResponse = {
  status: string;
  email: string;
  role: "member" | "admin";
};

export type ListTeamMembersResponse = {
  members: TeamMember[];
  total: number;
};

export type UpdateTeamMemberRolePayload = {
  role: "member" | "admin";
};

export type UpdateTeamMemberRoleResponse = {
  membership_id: string;
  role: "member" | "admin";
};

export type RemoveTeamMemberResponse = {
  membership_id: string;
  status: string;
};
