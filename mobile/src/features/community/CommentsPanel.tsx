import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { useAuthStore } from '@/stores/auth-store';
import { colors } from '@/theme';

import {
  createComment,
  deleteComment,
  getComments,
  getReplies,
  getReportReasons,
  reportComment,
  setCommentLike,
  updateComment,
} from './api';
import type { CommentTargetType, CommunityComment } from './types';

type Props = {
  targetType: CommentTargetType;
  targetId: string;
};

export function CommentsPanel({ targetType, targetId }: Props) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const session = useAuthStore((state) => state.session);
  const [draft, setDraft] = useState('');
  const [isSpoiler, setIsSpoiler] = useState(false);
  const [replyingTo, setReplyingTo] = useState<CommunityComment | null>(null);
  const [reporting, setReporting] = useState<CommunityComment | null>(null);
  const comments = useQuery({
    queryKey: ['comments', targetType, targetId],
    queryFn: () => getComments(targetType, targetId),
  });
  const submit = useMutation({
    mutationFn: () =>
      createComment({
        targetType,
        targetId,
        body: draft,
        parentId: replyingTo?.id,
        isSpoiler,
      }),
    onSuccess: async () => {
      setDraft('');
      setIsSpoiler(false);
      setReplyingTo(null);
      await queryClient.invalidateQueries({ queryKey: ['comments'] });
    },
  });

  return (
    <View style={styles.panel}>
      <View style={styles.headingRow}>
        <Text style={styles.heading}>Comments</Text>
        <Text style={styles.count}>{comments.data?.meta.total ?? 0}</Text>
      </View>

      {session ? (
        <View style={styles.composer}>
          {replyingTo ? (
            <View style={styles.replyingRow}>
              <Text style={styles.replyingText}>Replying to {replyingTo.author.name}</Text>
              <Pressable onPress={() => setReplyingTo(null)}>
                <Text style={styles.cancelText}>Cancel</Text>
              </Pressable>
            </View>
          ) : null}
          <TextInput
            maxLength={2000}
            multiline
            onChangeText={setDraft}
            placeholder={replyingTo ? 'Write a reply…' : 'Join the conversation…'}
            placeholderTextColor={colors.muted}
            style={styles.composerInput}
            value={draft}
          />
          <View style={styles.composerActions}>
            <Pressable
              accessibilityRole="checkbox"
              accessibilityState={{ checked: isSpoiler }}
              onPress={() => setIsSpoiler((value) => !value)}
              style={[styles.spoilerToggle, isSpoiler && styles.spoilerToggleActive]}
            >
              <Text style={styles.spoilerToggleText}>{isSpoiler ? '✓ Spoiler' : 'Mark spoiler'}</Text>
            </Pressable>
            <Pressable
              disabled={!draft.trim() || submit.isPending}
              onPress={() => submit.mutate()}
              style={[styles.postButton, (!draft.trim() || submit.isPending) && styles.disabled]}
            >
              {submit.isPending ? (
                <ActivityIndicator color={colors.background} />
              ) : (
                <Text style={styles.postButtonText}>{replyingTo ? 'Reply' : 'Post'}</Text>
              )}
            </Pressable>
          </View>
          {submit.isError ? (
            <Text style={styles.error}>Your comment could not be posted. Please try again.</Text>
          ) : null}
        </View>
      ) : (
        <Pressable onPress={() => router.push('/login')} style={styles.signInGate}>
          <Text style={styles.signInTitle}>Join the conversation</Text>
          <Text style={styles.muted}>Sign in to comment, reply, like and report.</Text>
          <Text style={styles.signInAction}>Sign in</Text>
        </Pressable>
      )}

      {comments.isPending ? (
        <ActivityIndicator color={colors.accent} style={styles.loader} />
      ) : comments.isError ? (
        <View style={styles.stateBox}>
          <Text style={styles.muted}>Comments are temporarily unavailable.</Text>
          <Pressable onPress={() => void comments.refetch()}>
            <Text style={styles.retry}>Try again</Text>
          </Pressable>
        </View>
      ) : comments.data.data.length ? (
        <View style={styles.list}>
          {comments.data.data.map((comment) => (
            <CommentCard
              comment={comment}
              key={comment.id}
              onReply={setReplyingTo}
              onReport={setReporting}
              rootId={comment.id}
            />
          ))}
        </View>
      ) : (
        <View style={styles.stateBox}>
          <Text style={styles.emptyTitle}>Start the conversation</Text>
          <Text style={styles.muted}>Be the first viewer to share a thought.</Text>
        </View>
      )}

      <ReportDialog comment={reporting} onClose={() => setReporting(null)} />
    </View>
  );
}

function CommentCard({
  comment,
  onReply,
  onReport,
  rootId,
  compact = false,
}: {
  comment: CommunityComment;
  onReply: (comment: CommunityComment) => void;
  onReport: (comment: CommunityComment) => void;
  rootId: string;
  compact?: boolean;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const session = useAuthStore((state) => state.session);
  const [spoilerVisible, setSpoilerVisible] = useState(false);
  const [showReplies, setShowReplies] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editBody, setEditBody] = useState(comment.body);
  const [editSpoiler, setEditSpoiler] = useState(comment.is_spoiler);
  const replies = useQuery({
    queryKey: ['comments', 'replies', rootId],
    queryFn: () => getReplies(rootId),
    enabled: showReplies && !compact,
  });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['comments'] });
  const like = useMutation({
    mutationFn: () => setCommentLike(comment.id, comment.liked_by_me),
    onSuccess: invalidate,
  });
  const edit = useMutation({
    mutationFn: () => updateComment(comment.id, { body: editBody, isSpoiler: editSpoiler }),
    onSuccess: async () => {
      setEditing(false);
      await invalidate();
    },
  });
  const remove = useMutation({ mutationFn: () => deleteComment(comment.id), onSuccess: invalidate });

  const requestDelete = () =>
    Alert.alert('Delete comment?', 'This action removes the comment from the conversation.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => remove.mutate() },
    ]);

  return (
    <View style={[styles.comment, compact && styles.reply]}>
      <View style={styles.avatar}>
        <Text style={styles.avatarText}>{comment.author.name.slice(0, 1).toUpperCase()}</Text>
      </View>
      <View style={styles.commentBody}>
        <View style={styles.authorRow}>
          <Text style={styles.author}>{comment.author.name}</Text>
          {comment.author.badge ? (
            <Text style={styles.badge}>{comment.author.badge.toUpperCase()}</Text>
          ) : null}
          {comment.is_pinned ? <Text style={styles.pinned}>PINNED</Text> : null}
        </View>
        <Text style={styles.time}>
          {new Date(comment.created_at).toLocaleDateString()}
          {comment.edited ? ' · edited' : ''}
        </Text>

        {editing ? (
          <View style={styles.editBox}>
            <TextInput
              maxLength={2000}
              multiline
              onChangeText={setEditBody}
              style={styles.editInput}
              value={editBody}
            />
            <View style={styles.editActions}>
              <Pressable onPress={() => setEditSpoiler((value) => !value)}>
                <Text style={styles.actionText}>{editSpoiler ? '✓ Spoiler' : 'Mark spoiler'}</Text>
              </Pressable>
              <Pressable onPress={() => setEditing(false)}>
                <Text style={styles.actionText}>Cancel</Text>
              </Pressable>
              <Pressable disabled={!editBody.trim() || edit.isPending} onPress={() => edit.mutate()}>
                <Text style={styles.actionStrong}>Save</Text>
              </Pressable>
            </View>
          </View>
        ) : comment.is_spoiler && !spoilerVisible ? (
          <Pressable onPress={() => setSpoilerVisible(true)} style={styles.spoilerBox}>
            <Text style={styles.spoilerTitle}>Spoiler hidden</Text>
            <Text style={styles.spoilerHint}>Tap to reveal</Text>
          </Pressable>
        ) : (
          <Text style={styles.commentText}>{comment.body}</Text>
        )}

        {!editing ? (
          <View style={styles.commentActions}>
            <Pressable
              onPress={() => (session ? like.mutate() : router.push('/login'))}
              style={styles.actionButton}
            >
              <Text style={[styles.actionText, comment.liked_by_me && styles.actionLiked]}>
                {comment.liked_by_me ? '♥' : '♡'} {comment.like_count}
              </Text>
            </Pressable>
            {!compact ? (
              <Pressable
                onPress={() => (session ? onReply(comment) : router.push('/login'))}
                style={styles.actionButton}
              >
                <Text style={styles.actionText}>Reply</Text>
              </Pressable>
            ) : null}
            <Pressable
              onPress={() => (session ? onReport(comment) : router.push('/login'))}
              style={styles.actionButton}
            >
              <Text style={styles.actionText}>Report</Text>
            </Pressable>
            {comment.can_edit ? (
              <Pressable onPress={() => setEditing(true)} style={styles.actionButton}>
                <Text style={styles.actionText}>Edit</Text>
              </Pressable>
            ) : null}
            {comment.can_delete ? (
              <Pressable onPress={requestDelete} style={styles.actionButton}>
                <Text style={styles.deleteText}>Delete</Text>
              </Pressable>
            ) : null}
          </View>
        ) : null}

        {!compact && comment.reply_count > 0 ? (
          <View style={styles.repliesWrap}>
            <Pressable onPress={() => setShowReplies((value) => !value)}>
              <Text style={styles.repliesButton}>
                {showReplies ? 'Hide replies' : `View ${comment.reply_count} replies`}
              </Text>
            </Pressable>
            {showReplies && replies.isPending ? <ActivityIndicator color={colors.accent} /> : null}
            {showReplies
              ? replies.data?.data.map((reply) => (
                  <CommentCard
                    comment={reply}
                    compact
                    key={reply.id}
                    onReply={onReply}
                    onReport={onReport}
                    rootId={rootId}
                  />
                ))
              : null}
          </View>
        ) : null}
      </View>
    </View>
  );
}

function ReportDialog({
  comment,
  onClose,
}: {
  comment: CommunityComment | null;
  onClose: () => void;
}) {
  const [selected, setSelected] = useState('');
  const [details, setDetails] = useState('');
  const reasons = useQuery({
    queryKey: ['report-reasons', 'comment'],
    queryFn: getReportReasons,
    enabled: Boolean(comment),
  });
  const report = useMutation({
    mutationFn: () => reportComment(comment!.id, selected, details),
    onSuccess: () => {
      Alert.alert('Report received', 'Thank you. Our moderation team will review it.');
      onClose();
    },
  });

  useEffect(() => {
    if (comment) {
      setSelected('');
      setDetails('');
    }
  }, [comment]);

  return (
    <Modal animationType="slide" onRequestClose={onClose} transparent visible={Boolean(comment)}>
      <View style={styles.modalBackdrop}>
        <View style={styles.modalCard}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Report comment</Text>
            <Pressable onPress={onClose}>
              <Text style={styles.modalClose}>×</Text>
            </Pressable>
          </View>
          <Text style={styles.muted}>Choose the reason that best describes the problem.</Text>
          <ScrollView contentContainerStyle={styles.reasonList} style={styles.reasonScroll}>
            {reasons.data?.map((reason) => (
              <Pressable
                key={reason.code}
                onPress={() => setSelected(reason.code)}
                style={[styles.reason, selected === reason.code && styles.reasonSelected]}
              >
                <Text style={styles.reasonTitle}>{reason.label}</Text>
                {reason.description ? <Text style={styles.reasonDescription}>{reason.description}</Text> : null}
              </Pressable>
            ))}
          </ScrollView>
          <TextInput
            maxLength={2000}
            multiline
            onChangeText={setDetails}
            placeholder="Additional details (optional)"
            placeholderTextColor={colors.muted}
            style={styles.reportDetails}
            value={details}
          />
          <Pressable
            disabled={!selected || report.isPending}
            onPress={() => report.mutate()}
            style={[styles.reportButton, (!selected || report.isPending) && styles.disabled]}
          >
            <Text style={styles.reportButtonText}>Submit report</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  panel: { gap: 18, marginTop: 18 },
  headingRow: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  heading: { color: colors.text, fontSize: 23, fontWeight: '900' },
  count: { color: colors.muted, fontSize: 14, fontWeight: '800' },
  composer: { gap: 12, padding: 15, borderRadius: 20, backgroundColor: colors.card },
  replyingRow: { flexDirection: 'row', justifyContent: 'space-between' },
  replyingText: { color: colors.accent, fontSize: 12, fontWeight: '800' },
  cancelText: { color: colors.muted, fontSize: 12, fontWeight: '800' },
  composerInput: {
    minHeight: 90,
    color: colors.text,
    padding: 13,
    borderRadius: 15,
    textAlignVertical: 'top',
    backgroundColor: colors.cardSecondary,
  },
  composerActions: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  spoilerToggle: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 99, backgroundColor: colors.cardSecondary },
  spoilerToggleActive: { backgroundColor: '#ff3d7124' },
  spoilerToggleText: { color: colors.text, fontSize: 12, fontWeight: '800' },
  postButton: { minWidth: 82, minHeight: 40, alignItems: 'center', justifyContent: 'center', borderRadius: 99, backgroundColor: colors.text },
  postButtonText: { color: colors.background, fontWeight: '900' },
  disabled: { opacity: 0.45 },
  error: { color: colors.danger, fontSize: 12 },
  signInGate: { gap: 7, padding: 18, borderRadius: 20, backgroundColor: colors.card },
  signInTitle: { color: colors.text, fontSize: 17, fontWeight: '900' },
  signInAction: { color: colors.accent, fontWeight: '900', marginTop: 5 },
  loader: { marginVertical: 22 },
  stateBox: { alignItems: 'center', gap: 8, padding: 24, borderRadius: 20, backgroundColor: colors.card },
  emptyTitle: { color: colors.text, fontSize: 17, fontWeight: '900' },
  muted: { color: colors.muted, lineHeight: 20 },
  retry: { color: colors.accent, fontWeight: '900' },
  list: { gap: 4 },
  comment: { flexDirection: 'row', gap: 11, paddingVertical: 15, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line },
  reply: { paddingVertical: 11, borderBottomWidth: 0 },
  avatar: { width: 38, height: 38, alignItems: 'center', justifyContent: 'center', borderRadius: 19, backgroundColor: colors.cardSecondary },
  avatarText: { color: colors.text, fontWeight: '900' },
  commentBody: { flex: 1, gap: 6 },
  authorRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 7 },
  author: { color: colors.text, fontWeight: '900' },
  badge: { color: colors.accent, fontSize: 9, fontWeight: '900', letterSpacing: 0.8 },
  pinned: { color: '#fbbf24', fontSize: 9, fontWeight: '900', letterSpacing: 0.8 },
  time: { color: colors.muted, fontSize: 11 },
  commentText: { color: '#e5e7eb', fontSize: 14, lineHeight: 21 },
  spoilerBox: { gap: 3, padding: 13, borderRadius: 13, backgroundColor: colors.cardSecondary },
  spoilerTitle: { color: colors.text, fontWeight: '900' },
  spoilerHint: { color: colors.muted, fontSize: 11 },
  commentActions: { flexDirection: 'row', flexWrap: 'wrap', gap: 5, marginTop: 3 },
  actionButton: { paddingRight: 9, paddingVertical: 4 },
  actionText: { color: colors.muted, fontSize: 12, fontWeight: '800' },
  actionStrong: { color: colors.accent, fontSize: 12, fontWeight: '900' },
  actionLiked: { color: colors.accent },
  deleteText: { color: '#fca5a5', fontSize: 12, fontWeight: '800' },
  editBox: { gap: 9 },
  editInput: { minHeight: 75, padding: 11, borderRadius: 13, color: colors.text, textAlignVertical: 'top', backgroundColor: colors.cardSecondary },
  editActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 15 },
  repliesWrap: { gap: 8, marginTop: 4 },
  repliesButton: { color: colors.accent, fontSize: 12, fontWeight: '900' },
  modalBackdrop: { flex: 1, justifyContent: 'flex-end', backgroundColor: '#000a' },
  modalCard: { maxHeight: '88%', gap: 14, padding: 20, paddingBottom: 32, borderTopLeftRadius: 28, borderTopRightRadius: 28, backgroundColor: colors.card },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  modalTitle: { color: colors.text, fontSize: 22, fontWeight: '900' },
  modalClose: { color: colors.text, fontSize: 30 },
  reasonScroll: { maxHeight: 310 },
  reasonList: { gap: 8 },
  reason: { gap: 3, padding: 13, borderWidth: 1, borderColor: colors.line, borderRadius: 15, backgroundColor: colors.cardSecondary },
  reasonSelected: { borderColor: colors.accent, backgroundColor: '#ff3d7114' },
  reasonTitle: { color: colors.text, fontWeight: '900' },
  reasonDescription: { color: colors.muted, fontSize: 11, lineHeight: 16 },
  reportDetails: { minHeight: 78, padding: 12, borderRadius: 14, color: colors.text, textAlignVertical: 'top', backgroundColor: colors.cardSecondary },
  reportButton: { alignItems: 'center', padding: 15, borderRadius: 99, backgroundColor: colors.text },
  reportButtonText: { color: colors.background, fontWeight: '900' },
});
