import { request } from "../http";
import type {
  TeamMember,
  InviteTeamMemberPayload,
  InviteTeamMemberResponse,
  ListTeamMembersResponse,
  UpdateTeamMemberRolePayload,
  UpdateTeamMemberRoleResponse,
  RemoveTeamMemberResponse,
} from "./types/team-types";

export type {
  TeamMember,
  InviteTeamMemberPayload,
  InviteTeamMemberResponse,
  ListTeamMembersResponse,
  UpdateTeamMemberRolePayload,
  UpdateTeamMemberRoleResponse,
  RemoveTeamMemberResponse,
};

export async function listTeamMembers(organizationId: string): Promise<ListTeamMembersResponse> {
  return request<ListTeamMembersResponse>(`/api/organizations/${organizationId}/members/`, {
    method: "GET",
  });
}

export async function inviteTeamMember(
  organizationId: string,
  payload: InviteTeamMemberPayload
): Promise<InviteTeamMemberResponse> {
  return request<InviteTeamMemberResponse>(
    `/api/organizations/${organizationId}/members/invite/`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function removeTeamMember(
  organizationId: string,
  membershipId: string
): Promise<RemoveTeamMemberResponse> {
  return request<RemoveTeamMemberResponse>(
    `/api/organizations/${organizationId}/members/${membershipId}/`,
    {
      method: "DELETE",
    }
  );
}

export async function updateTeamMemberRole(
  organizationId: string,
  membershipId: string,
  payload: UpdateTeamMemberRolePayload
): Promise<UpdateTeamMemberRoleResponse> {
  return request<UpdateTeamMemberRoleResponse>(
    `/api/organizations/${organizationId}/members/${membershipId}/role/`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    }
  );
}
