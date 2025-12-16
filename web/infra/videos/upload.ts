import { request } from '../http'

export interface GenerateUploadUrlResponse {
  upload_url: string
  video_id: string
  key: string
}

export interface ConfirmUploadResponse {
  video_id: string
  status: string
}

/**
 * Gera uma URL pré-assinada para upload de vídeo no R2
 */
export async function generateUploadUrl(
  filename: string,
  fileSize: number,
  videoId: string,
  contentType: string = 'video/mp4'
): Promise<GenerateUploadUrlResponse> {
  return request<GenerateUploadUrlResponse>('/api/videos/upload/generate-url/', {
    method: 'POST',
    body: JSON.stringify({
      filename,
      file_size: fileSize,
      video_id: videoId,
      content_type: contentType,
    }),
  })
}

/**
 * Faz upload do arquivo para o R2 usando a URL pré-assinada
 */
export async function uploadToR2(
  uploadUrl: string,
  file: File,
  contentType: string = 'video/mp4'
): Promise<void> {
  try {
    const response = await fetch(uploadUrl, {
      method: 'PUT',
      body: file,
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('Upload error response:', errorText)
      throw new Error(`Erro ao fazer upload do arquivo: ${response.status} ${response.statusText}`)
    }
  } catch (error) {
    console.error('Upload error:', error)
    throw error
  }
}

/**
 * Confirma que o upload foi concluído
 */
export async function confirmUpload(
  videoId: string,
  fileSize: number
): Promise<ConfirmUploadResponse> {
  return request<ConfirmUploadResponse>('/api/videos/upload/confirm/', {
    method: 'POST',
    body: JSON.stringify({
      video_id: videoId,
      file_size: fileSize,
    }),
  })
}

/**
 * Fluxo completo de upload:
 * 1. Gera URL pré-assinada
 * 2. Faz upload do arquivo para R2
 * 3. Confirma o upload
 */
export async function uploadVideo(file: File, videoId: string): Promise<string> {
  try {
    // Step 1: Gerar URL pré-assinada
    const { upload_url } = await generateUploadUrl(
      file.name,
      file.size,
      videoId,
      file.type
    )

    // Step 2: Fazer upload para R2
    await uploadToR2(upload_url, file, file.type)

    // Step 3: Confirmar upload
    await confirmUpload(videoId, file.size)

    return videoId
  } catch (error) {
    throw error
  }
}
