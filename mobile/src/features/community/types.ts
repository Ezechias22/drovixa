export type CommentTargetType = 'content' | 'episode' | 'short';
export type LikeTargetType = 'content' | 'episode' | 'short';

export type CommunityComment = {
  id: string;
  target_type: CommentTargetType;
  target_id: string;
  parent_id?: string | null;
  body: string;
  is_spoiler: boolean;
  status: 'visible' | 'hidden' | 'deleted' | 'under_review' | 'spam';
  is_pinned: boolean;
  like_count: number;
  reply_count: number;
  liked_by_me: boolean;
  edited: boolean;
  edited_at?: string | null;
  created_at: string;
  author: { id: string; name: string; badge?: 'admin' | 'creator' | 'moderator' | null };
  can_edit: boolean;
  can_delete: boolean;
};

export type ReportReason = {
  code: string;
  label: string;
  description?: string | null;
  target_types: string[];
};

export type PageEnvelope<T> = {
  success: boolean;
  data: T;
  meta: { page: number; limit: number; total: number; pages: number };
};
