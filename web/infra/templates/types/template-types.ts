export type Template = {
  template_id: string;
  name: string;
  type: "overlay" | "bar" | "effect" | "text_style";
  ffmpeg_filter: string;
  preview_url: string;
  is_active: boolean;
  created_at: string;
  version: number;
};

export type CreateTemplatePayload = {
  name: string;
  type: "overlay" | "bar" | "effect" | "text_style";
  ffmpeg_filter: string;
  preview_url: string;
};

export type CreateTemplateResponse = {
  detail: string;
  template: Template;
};

export type ListTemplatesResponse = {
  templates: Template[];
  total: number;
};

export type UpdateTemplatePayload = {
  name?: string;
  type?: "overlay" | "bar" | "effect" | "text_style";
  ffmpeg_filter?: string;
  preview_url?: string;
  is_active?: boolean;
};

export type UpdateTemplateResponse = {
  detail: string;
  template: Template;
};

export type DeleteTemplateResponse = {
  detail: string;
};
