'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useEffect, useState } from 'react';

import { useAuthStore } from '@/stores/auth-store';
import { createComment, deleteComment, getComments, getReplies, getReportReasons, reportComment, setCommentLike, updateComment } from './api';
import type { CommentTargetType, CommunityComment } from './types';

export function CommentsPanel({ targetId, targetType }: { targetId: string; targetType: CommentTargetType }) {
  const client = useQueryClient();
  const authenticated = useAuthStore((state) => Boolean(state.accessToken));
  const [body, setBody] = useState('');
  const [spoiler, setSpoiler] = useState(false);
  const [replyingTo, setReplyingTo] = useState<CommunityComment | null>(null);
  const [reporting, setReporting] = useState<CommunityComment | null>(null);
  const comments = useQuery({ queryKey: ['comments', targetType, targetId], queryFn: () => getComments(targetType, targetId) });
  const submit = useMutation({
    mutationFn: () => createComment({ targetId, targetType, body, isSpoiler: spoiler, parentId: replyingTo?.id }),
    onSuccess: async () => { setBody(''); setSpoiler(false); setReplyingTo(null); await client.invalidateQueries({ queryKey: ['comments'] }); },
  });

  return <section className="mt-12 border-t border-white/10 pt-10">
    <div className="flex items-center gap-3"><h2 className="text-2xl font-black">Comments</h2><span className="text-sm font-bold text-[var(--muted)]">{comments.data?.meta.total ?? 0}</span></div>
    {authenticated ? <div className="mt-5 rounded-3xl bg-[var(--card)] p-4">
      {replyingTo ? <div className="mb-3 flex justify-between text-xs font-bold text-[var(--accent)]"><span>Replying to {replyingTo.author.name}</span><button onClick={() => setReplyingTo(null)}>Cancel</button></div> : null}
      <textarea className="min-h-28 w-full resize-y rounded-2xl bg-white/[.04] p-4 text-sm outline-none ring-[var(--accent)] placeholder:text-white/35 focus:ring-1" maxLength={2000} onChange={(event) => setBody(event.target.value)} placeholder={replyingTo ? 'Write a reply…' : 'Join the conversation…'} value={body}/>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3"><label className="flex cursor-pointer items-center gap-2 text-xs font-bold text-white/65"><input checked={spoiler} onChange={(event) => setSpoiler(event.target.checked)} type="checkbox"/> Mark as spoiler</label><button className="primary-button disabled:opacity-40" disabled={!body.trim() || submit.isPending} onClick={() => submit.mutate()}>{submit.isPending ? 'Posting…' : replyingTo ? 'Reply' : 'Post'}</button></div>
      {submit.isError ? <p className="mt-3 text-sm text-red-400">Your comment could not be posted.</p> : null}
    </div> : <div className="mt-5 rounded-3xl bg-[var(--card)] p-6"><h3 className="font-black">Join the conversation</h3><p className="mt-2 text-sm text-[var(--muted)]">Sign in to comment, reply, like and report.</p><Link className="mt-4 inline-block font-black text-[var(--accent)]" href="/login">Sign in</Link></div>}
    {comments.isPending ? <div className="mt-6 h-24 animate-pulse rounded-3xl bg-white/[.04]"/> : comments.isError ? <div className="mt-6 rounded-3xl bg-[var(--card)] p-6 text-[var(--muted)]">Comments are temporarily unavailable. <button className="ml-2 font-black text-[var(--accent)]" onClick={() => void comments.refetch()}>Try again</button></div> : comments.data.data.length ? <div className="mt-6 divide-y divide-white/[.07]">{comments.data.data.map((comment) => <CommentCard comment={comment} key={comment.id} onReply={setReplyingTo} onReport={setReporting} rootId={comment.id}/>)}</div> : <div className="mt-6 rounded-3xl bg-[var(--card)] p-8 text-center"><p className="font-black">Start the conversation</p><p className="mt-2 text-sm text-[var(--muted)]">Be the first viewer to share a thought.</p></div>}
    <ReportDialog comment={reporting} onClose={() => setReporting(null)}/>
  </section>;
}

function CommentCard({ comment, compact = false, onReply, onReport, rootId }: { comment: CommunityComment; compact?: boolean; onReply: (comment: CommunityComment) => void; onReport: (comment: CommunityComment) => void; rootId: string }) {
  const client = useQueryClient();
  const authenticated = useAuthStore((state) => Boolean(state.accessToken));
  const [showSpoiler, setShowSpoiler] = useState(false);
  const [showReplies, setShowReplies] = useState(false);
  const [editing, setEditing] = useState(false);
  const [body, setBody] = useState(comment.body);
  const [spoiler, setSpoiler] = useState(comment.is_spoiler);
  const replies = useQuery({ queryKey: ['comments', 'replies', rootId], queryFn: () => getReplies(rootId), enabled: showReplies && !compact });
  const invalidate = () => client.invalidateQueries({ queryKey: ['comments'] });
  const like = useMutation({ mutationFn: () => setCommentLike(comment.id, comment.liked_by_me), onSuccess: invalidate });
  const edit = useMutation({ mutationFn: () => updateComment(comment.id, body, spoiler), onSuccess: async () => { setEditing(false); await invalidate(); } });
  const remove = useMutation({ mutationFn: () => deleteComment(comment.id), onSuccess: invalidate });
  const requireAuth = (action: () => void) => authenticated ? action() : window.location.assign('/login');

  return <article className={`flex gap-3 py-5 ${compact ? 'ml-3 border-0 py-3 md:ml-8' : ''}`}>
    <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-white/10 text-sm font-black">{comment.author.name.slice(0, 1).toUpperCase()}</div>
    <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="font-black">{comment.author.name}</span>{comment.author.badge ? <span className="text-[10px] font-black tracking-widest text-[var(--accent)]">{comment.author.badge.toUpperCase()}</span> : null}{comment.is_pinned ? <span className="text-[10px] font-black tracking-widest text-amber-400">PINNED</span> : null}</div><p className="mt-1 text-xs text-[var(--muted)]">{new Date(comment.created_at).toLocaleDateString()}{comment.edited ? ' · edited' : ''}</p>
      {editing ? <div className="mt-3"><textarea className="min-h-24 w-full rounded-xl bg-white/[.05] p-3 outline-none" maxLength={2000} onChange={(event) => setBody(event.target.value)} value={body}/><div className="mt-2 flex flex-wrap justify-end gap-4 text-xs font-bold"><label><input checked={spoiler} onChange={(event) => setSpoiler(event.target.checked)} type="checkbox"/> Spoiler</label><button onClick={() => setEditing(false)}>Cancel</button><button className="text-[var(--accent)]" disabled={!body.trim()} onClick={() => edit.mutate()}>Save</button></div></div> : comment.is_spoiler && !showSpoiler ? <button className="mt-3 w-full rounded-xl bg-white/[.05] p-4 text-left"><span className="font-black" onClick={() => setShowSpoiler(true)}>Spoiler hidden · click to reveal</span></button> : <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-white/80">{comment.body}</p>}
      {!editing ? <div className="mt-3 flex flex-wrap gap-4 text-xs font-bold text-[var(--muted)]"><button className={comment.liked_by_me ? 'text-[var(--accent)]' : ''} onClick={() => requireAuth(() => like.mutate())}>{comment.liked_by_me ? '♥' : '♡'} {comment.like_count}</button>{!compact ? <button onClick={() => requireAuth(() => onReply(comment))}>Reply</button> : null}<button onClick={() => requireAuth(() => onReport(comment))}>Report</button>{comment.can_edit ? <button onClick={() => setEditing(true)}>Edit</button> : null}{comment.can_delete ? <button className="text-red-400" onClick={() => window.confirm('Delete this comment?') && remove.mutate()}>Delete</button> : null}</div> : null}
      {!compact && comment.reply_count > 0 ? <div className="mt-4"><button className="text-xs font-black text-[var(--accent)]" onClick={() => setShowReplies((value) => !value)}>{showReplies ? 'Hide replies' : `View ${comment.reply_count} replies`}</button>{showReplies ? replies.data?.data.map((reply) => <CommentCard comment={reply} compact key={reply.id} onReply={onReply} onReport={onReport} rootId={rootId}/>) : null}</div> : null}
    </div>
  </article>;
}

function ReportDialog({ comment, onClose }: { comment: CommunityComment | null; onClose: () => void }) {
  const [selected, setSelected] = useState('');
  const [details, setDetails] = useState('');
  const reasons = useQuery({ queryKey: ['report-reasons', 'comment'], queryFn: getReportReasons, enabled: Boolean(comment) });
  const report = useMutation({ mutationFn: () => reportComment(comment!.id, selected, details), onSuccess: () => { window.alert('Report received. Our moderation team will review it.'); onClose(); } });
  useEffect(() => { if (comment) { setSelected(''); setDetails(''); } }, [comment]);
  if (!comment) return null;
  return <div aria-modal="true" className="fixed inset-0 z-[100] grid place-items-end bg-black/70 p-0 md:place-items-center md:p-6" role="dialog"><div className="max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-t-3xl bg-[var(--card)] p-6 md:rounded-3xl"><div className="flex items-center justify-between"><h2 className="text-xl font-black">Report comment</h2><button className="text-3xl" onClick={onClose}>×</button></div><p className="mt-2 text-sm text-[var(--muted)]">Choose the reason that best describes the problem.</p><div className="mt-5 grid gap-2">{reasons.data?.map((reason) => <button className={`rounded-2xl border p-4 text-left ${selected === reason.code ? 'border-[var(--accent)] bg-[var(--accent-glow)]' : 'border-white/10 bg-white/[.03]'}`} key={reason.code} onClick={() => setSelected(reason.code)}><span className="block font-black">{reason.label}</span>{reason.description ? <span className="mt-1 block text-xs text-[var(--muted)]">{reason.description}</span> : null}</button>)}</div><textarea className="mt-4 min-h-24 w-full rounded-2xl bg-white/[.05] p-4 outline-none" maxLength={2000} onChange={(event) => setDetails(event.target.value)} placeholder="Additional details (optional)" value={details}/><button className="primary-button mt-4 w-full disabled:opacity-40" disabled={!selected || report.isPending} onClick={() => report.mutate()}>Submit report</button></div></div>;
}
