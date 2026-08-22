import { apiClient } from '@/api/client';
import type { ApiEnvelope } from '@/features/catalog/types';

import type {
  CommentTargetType,
  CommunityComment,
  LikeTargetType,
  PageEnvelope,
  ReportReason,
} from './types';

export async function getComments(targetType: CommentTargetType, targetId: string) {
  return (
    await apiClient.get<PageEnvelope<CommunityComment[]>>('/comments', {
      params: { target_type: targetType, target_id: targetId, page: 1, limit: 50 },
    })
  ).data;
}

export async function getReplies(commentId: string) {
  return (
    await apiClient.get<PageEnvelope<CommunityComment[]>>(`/comments/${commentId}/replies`, {
      params: { page: 1, limit: 50 },
    })
  ).data;
}

export async function createComment(input: {
  targetType: CommentTargetType;
  targetId: string;
  body: string;
  parentId?: string;
  isSpoiler: boolean;
}) {
  return (
    await apiClient.post<ApiEnvelope<CommunityComment>>('/comments', {
      target_type: input.targetType,
      target_id: input.targetId,
      body: input.body,
      parent_id: input.parentId,
      is_spoiler: input.isSpoiler,
    })
  ).data.data;
}

export async function updateComment(
  commentId: string,
  input: { body: string; isSpoiler: boolean },
) {
  return (
    await apiClient.patch<ApiEnvelope<CommunityComment>>(`/comments/${commentId}`, {
      body: input.body,
      is_spoiler: input.isSpoiler,
    })
  ).data.data;
}

export async function deleteComment(commentId: string) {
  await apiClient.delete(`/comments/${commentId}`);
}

export async function setCommentLike(commentId: string, liked: boolean) {
  const response = liked
    ? await apiClient.delete<ApiEnvelope<{ comment_id: string; liked: boolean; like_count: number }>>(
        `/comments/${commentId}/like`,
      )
    : await apiClient.post<ApiEnvelope<{ comment_id: string; liked: boolean; like_count: number }>>(
        `/comments/${commentId}/like`,
      );
  return response.data.data;
}

export async function getLikeStatus(targetType: LikeTargetType, targetId: string) {
  return (
    await apiClient.get<
      ApiEnvelope<{ target_type: LikeTargetType; target_id: string; liked: boolean; count: number }>
    >('/likes', { params: { target_type: targetType, target_id: targetId } })
  ).data.data;
}

export async function setLike(targetType: LikeTargetType, targetId: string, liked: boolean) {
  const input = { target_type: targetType, target_id: targetId };
  const response = liked
    ? await apiClient.delete<ApiEnvelope<{ liked: boolean; count: number }>>('/likes', {
        data: input,
      })
    : await apiClient.post<ApiEnvelope<{ liked: boolean; count: number }>>('/likes', input);
  return response.data.data;
}

export async function getReportReasons() {
  return (
    await apiClient.get<ApiEnvelope<ReportReason[]>>('/report-reasons', {
      params: { target_type: 'comment' },
    })
  ).data.data;
}

export async function reportComment(commentId: string, reasonCode: string, details?: string) {
  return (
    await apiClient.post(`/comments/${commentId}/report`, {
      reason_code: reasonCode,
      details: details || undefined,
    })
  ).data.data;
}
