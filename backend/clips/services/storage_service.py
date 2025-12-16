"""
Serviço de Storage para Cloudflare R2.

Convenção de nomes de arquivos:
- Vídeos originais: videos/{organization_id}/{video_id}/{original_filename}
- Thumbnails: thumbnails/{organization_id}/{video_id}/thumbnail.jpg
- Clips: clips/{organization_id}/{video_id}/{clip_id}/clip.mp4
- Transcrições: transcripts/{organization_id}/{video_id}/transcript.json
- Legendas ASS: captions/{organization_id}/{video_id}/{clip_id}/caption.ass
"""

import os
import boto3
from typing import Optional, Tuple
from django.conf import settings
from botocore.exceptions import ClientError


class R2StorageService:
    """Serviço para gerenciar uploads/downloads em Cloudflare R2."""

    def __init__(self):
        """Inicializa cliente S3 para Cloudflare R2."""
        self.account_id = settings.CLOUDFLARE_ACCOUNT_ID
        self.access_key = settings.CLOUDFLARE_ACCESS_KEY_ID
        self.secret_key = settings.CLOUDFLARE_SECRET_ACCESS_KEY
        self.bucket_name = settings.CLOUDFLARE_BUCKET_NAME
        self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"
        self.public_url = getattr(settings, "CLOUDFLARE_R2_PUBLIC_URL", f"https://{self.bucket_name}.{self.account_id}.r2.cloudflarestorage.com")

        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name="auto",
        )

    def upload_video(
        self,
        file_path: str,
        organization_id: str,
        video_id: str,
        original_filename: str,
    ) -> str:
        """
        Faz upload de vídeo original para R2.

        Args:
            file_path: Caminho local do arquivo
            organization_id: ID da organização
            video_id: ID do vídeo
            original_filename: Nome original do arquivo

        Returns:
            Caminho no R2 (storage_path)
        """
        key = f"videos/{organization_id}/{video_id}/{original_filename}"
        return self._upload_file(file_path, key)

    def upload_thumbnail(
        self,
        file_path: str,
        organization_id: str,
        video_id: str,
    ) -> str:
        """
        Faz upload de thumbnail para R2.

        Args:
            file_path: Caminho local do arquivo
            organization_id: ID da organização
            video_id: ID do vídeo

        Returns:
            Caminho no R2 (storage_path)
        """
        key = f"thumbnails/{organization_id}/{video_id}/thumbnail.jpg"
        return self._upload_file(file_path, key)

    def upload_clip(
        self,
        file_path: str,
        organization_id: str,
        video_id: str,
        clip_id: str,
    ) -> str:
        """
        Faz upload de clip de vídeo para R2.

        Args:
            file_path: Caminho local do arquivo
            organization_id: ID da organização
            video_id: ID do vídeo
            clip_id: ID do clip

        Returns:
            Caminho no R2 (storage_path)
        """
        key = f"clips/{organization_id}/{video_id}/{clip_id}/clip.mp4"
        return self._upload_file(file_path, key)

    def upload_transcript(
        self,
        file_path: str,
        organization_id: str,
        video_id: str,
    ) -> str:
        """
        Faz upload de transcrição (JSON) para R2.

        Args:
            file_path: Caminho local do arquivo
            organization_id: ID da organização
            video_id: ID do vídeo

        Returns:
            Caminho no R2 (storage_path)
        """
        key = f"transcripts/{organization_id}/{video_id}/transcript.json"
        return self._upload_file(file_path, key)

    def upload_caption(
        self,
        file_path: str,
        organization_id: str,
        video_id: str,
        clip_id: str,
    ) -> str:
        """
        Faz upload de legenda ASS para R2.

        Args:
            file_path: Caminho local do arquivo
            organization_id: ID da organização
            video_id: ID do vídeo
            clip_id: ID do clip

        Returns:
            Caminho no R2 (storage_path)
        """
        key = f"captions/{organization_id}/{video_id}/{clip_id}/caption.ass"
        return self._upload_file(file_path, key)

    def _upload_file(self, file_path: str, key: str) -> str:
        """
        Faz upload de arquivo local para R2.

        Args:
            file_path: Caminho local do arquivo
            key: Chave no R2 (path)

        Returns:
            Caminho no R2 (key)

        Raises:
            Exception: Se upload falhar
        """
        try:
            with open(file_path, "rb") as f:
                self.client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=f,
                )
            return key
        except ClientError as e:
            raise Exception(f"Erro ao fazer upload para R2: {e}") from e
        except FileNotFoundError as e:
            raise Exception(f"Arquivo não encontrado: {file_path}") from e

    def download_file(self, key: str, local_path: str) -> None:
        """
        Faz download de arquivo do R2 para local.

        Args:
            key: Chave no R2
            local_path: Caminho local para salvar

        Raises:
            Exception: Se download falhar
        """
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            self.client.download_file(
                self.bucket_name,
                key,
                local_path,
            )
        except ClientError as e:
            raise Exception(f"Erro ao fazer download do R2: {e}") from e

    def get_public_url(self, key: str) -> str:
        """
        Gera URL pública fixa para acessar arquivo no R2.
        Sem expiração - para exibição no frontend.

        Args:
            key: Chave no R2

        Returns:
            URL pública fixa

        Raises:
            Exception: Se geração de URL falhar
        """
        try:
            # URL pública fixa (sem assinatura)
            # Remove barra final da URL base se existir
            base_url = self.public_url.rstrip('/')
            url = f"{base_url}/{key}"
            return url
        except Exception as e:
            raise Exception(f"Erro ao gerar URL pública: {e}") from e

    def get_signed_url(self, key: str, expiration: int = 3600) -> str:
        """
        Gera URL assinada para acessar arquivo no R2.
        Com expiração - apenas para upload.

        Args:
            key: Chave no R2
            expiration: Tempo de expiração em segundos (padrão: 1 hora)

        Returns:
            URL assinada

        Raises:
            Exception: Se geração de URL falhar
        """
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expiration,
            )
            return url
        except ClientError as e:
            raise Exception(f"Erro ao gerar URL assinada: {e}") from e

    def generate_presigned_upload_url(
        self, key: str, content_type: str = "video/mp4", expires_in: int = 3600
    ) -> str:
        """
        Gera URL pré-assinada para upload de arquivo no R2.

        Args:
            key: Chave no R2 (path)
            content_type: Tipo de conteúdo do arquivo
            expires_in: Tempo de expiração em segundos (padrão: 1 hora)

        Returns:
            URL pré-assinada para upload

        Raises:
            Exception: Se geração de URL falhar
        """
        try:
            # Gera URL pré-assinada para PUT (upload)
            url = self.client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
            )
            print(f"[R2StorageService] URL de upload gerada para: {key}")
            print(f"[R2StorageService] URL: {url[:100]}...")
            return url
        except ClientError as e:
            print(f"[R2StorageService] Erro ao gerar URL de upload: {e}")
            raise Exception(f"Erro ao gerar URL pré-assinada para upload: {e}") from e

    def delete_file(self, key: str) -> None:
        """
        Deleta arquivo do R2.

        Args:
            key: Chave no R2

        Raises:
            Exception: Se deleção falhar
        """
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
        except ClientError as e:
            raise Exception(f"Erro ao deletar arquivo do R2: {e}") from e

    def file_exists(self, key: str) -> bool:
        """
        Verifica se arquivo existe no R2.

        Args:
            key: Chave no R2

        Returns:
            True se existe, False caso contrário
        """
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise Exception(f"Erro ao verificar arquivo no R2: {e}") from e
