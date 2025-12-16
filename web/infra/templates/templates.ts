import { request } from "../http";
import type {
  Template,
  CreateTemplatePayload,
  CreateTemplateResponse,
  ListTemplatesResponse,
  UpdateTemplatePayload,
  UpdateTemplateResponse,
  DeleteTemplateResponse,
} from "./types/template-types";

export type {
  Template,
  CreateTemplatePayload,
  CreateTemplateResponse,
  ListTemplatesResponse,
  UpdateTemplatePayload,
  UpdateTemplateResponse,
  DeleteTemplateResponse,
};

export async function listTemplates(): Promise<ListTemplatesResponse> {
  return request<ListTemplatesResponse>("/api/templates/", {
    method: "GET",
  });
}

export async function createTemplate(payload: CreateTemplatePayload): Promise<CreateTemplateResponse> {
  return request<CreateTemplateResponse>("/api/templates/create/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateTemplate(
  templateId: string,
  payload: UpdateTemplatePayload
): Promise<UpdateTemplateResponse> {
  return request<UpdateTemplateResponse>(`/api/templates/${templateId}/`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteTemplate(templateId: string): Promise<DeleteTemplateResponse> {
  return request<DeleteTemplateResponse>(`/api/templates/${templateId}/delete/`, {
    method: "DELETE",
  });
}
