'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { ChangeEvent, useEffect, useMemo, useState } from 'react';

import { Badge, PageHeading, QueryState } from '@/components/ui';
import { apiRequest, formatDate } from '@/lib/api';

type ContentKind = 'series' | 'movies';
type CatalogItem = { id: string; name: string; code?: string; active?: boolean };
type VideoAsset = {
  id: string;
  provider: string;
  provider_asset_id: string;
  status: string;
  duration_seconds?: number | null;
  width?: number | null;
  height?: number | null;
  thumbnail_url?: string | null;
  playback_id?: string | null;
  created_at: string;
};
type ContentDetail = {
  id: string;
  type: 'series' | 'movie';
  title: string;
  slug: string;
  original_title?: string | null;
  short_description?: string | null;
  description?: string | null;
  poster_url?: string | null;
  backdrop_url?: string | null;
  trailer_url?: string | null;
  release_date?: string | null;
  country?: CatalogItem | null;
  original_language?: CatalogItem | null;
  age_rating: string;
  status: string;
  visibility: string;
  featured: boolean;
  premium: boolean;
  rating: number | string;
  genres: CatalogItem[];
  tags: CatalogItem[];
  seo?: { title?: string | null; description?: string | null };
  series_status?: string;
  orientation?: string;
  total_seasons?: number;
  total_episodes?: number;
  duration_seconds?: number | null;
  access_type?: string;
  coin_price?: number;
  video_asset?: VideoAsset | null;
  updated_at?: string;
};
type Season = {
  id: string;
  season_number: number;
  title?: string | null;
  description?: string | null;
  status: string;
  release_date?: string | null;
};
type Episode = {
  id: string;
  season_id?: string | null;
  episode_number: number;
  title: string;
  description?: string | null;
  thumbnail_url?: string | null;
  duration_seconds?: number | null;
  orientation: string;
  access_type: string;
  coin_price: number;
  premium: boolean;
  status: string;
  published_at?: string | null;
  video_asset?: VideoAsset | null;
};
type UploadSession = {
  video_asset_id: string;
  protocol: string;
  upload_url: string;
  upload_headers: Record<string, string>;
};
type MetadataForm = {
  title: string;
  slug: string;
  original_title: string;
  short_description: string;
  description: string;
  poster_url: string;
  backdrop_url: string;
  trailer_url: string;
  release_date: string;
  country_id: string;
  original_language_id: string;
  age_rating: string;
  visibility: string;
  featured: boolean;
  premium: boolean;
  rating: string;
  genre_ids: string[];
  tag_ids: string[];
  seo_title: string;
  seo_description: string;
  series_status: string;
  orientation: string;
  duration_seconds: string;
  access_type: string;
  coin_price: string;
  video_asset_id: string;
};

const emptyForm: MetadataForm = {
  title: '', slug: '', original_title: '', short_description: '', description: '',
  poster_url: '', backdrop_url: '', trailer_url: '', release_date: '', country_id: '',
  original_language_id: '', age_rating: 'all', visibility: 'private', featured: false,
  premium: false, rating: '0', genre_ids: [], tag_ids: [], seo_title: '',
  seo_description: '', series_status: 'draft', orientation: 'horizontal',
  duration_seconds: '', access_type: 'free', coin_price: '0', video_asset_id: '',
};

function nullable(value: string) {
  const clean = value.trim();
  return clean.length ? clean : null;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The operation could not be completed.';
}

function delay(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

async function pollVideoAsset(assetId: string, onUpdate: (asset: VideoAsset) => void) {
  let latest: VideoAsset | null = null;
  for (let attempt = 0; attempt < 36; attempt += 1) {
    const response = await apiRequest<VideoAsset>(`/video-assets/${assetId}/refresh`, { method: 'POST' });
    latest = response.data;
    onUpdate(latest);
    if (latest.status === 'ready' || latest.status === 'failed') return latest;
    await delay(5000);
  }
  return latest;
}

function multiSelectValues(event: ChangeEvent<HTMLSelectElement>) {
  return Array.from(event.target.selectedOptions, (option) => option.value);
}

export function ContentStudio({ kind, contentId }: { kind: ContentKind; contentId: string }) {
  const client = useQueryClient();
  const [form, setForm] = useState<MetadataForm>(emptyForm);
  const [notice, setNotice] = useState('');
  const [uploadError, setUploadError] = useState('');
  const [uploadStatus, setUploadStatus] = useState('');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceName, setSourceName] = useState('');
  const [seasonForm, setSeasonForm] = useState({ season_number: '1', title: '', description: '' });
  const [episodeForm, setEpisodeForm] = useState({
    season_id: '', episode_number: '1', title: '', description: '', thumbnail_url: '',
    orientation: 'horizontal', access_type: 'free', coin_price: '0', premium: false,
    video_asset_id: '',
  });

  const detail = useQuery({
    queryKey: ['content-detail', kind, contentId],
    queryFn: async () => (await apiRequest<ContentDetail>(`/${kind}/${contentId}`)).data,
  });
  const countries = useQuery({
    queryKey: ['content-countries'],
    queryFn: async () => (await apiRequest<CatalogItem[]>('/countries?page=1&limit=100')).data,
  });
  const languages = useQuery({
    queryKey: ['content-languages'],
    queryFn: async () => (await apiRequest<CatalogItem[]>('/languages?page=1&limit=100')).data,
  });
  const genres = useQuery({
    queryKey: ['content-genres'],
    queryFn: async () => (await apiRequest<CatalogItem[]>('/genres?page=1&limit=100')).data,
  });
  const tags = useQuery({
    queryKey: ['content-tags'],
    queryFn: async () => (await apiRequest<CatalogItem[]>('/tags?page=1&limit=100')).data,
  });
  const seasons = useQuery({
    queryKey: ['content-seasons', contentId],
    queryFn: async () => (await apiRequest<Season[]>(`/seasons?series_id=${contentId}&page=1&limit=100`)).data,
    enabled: kind === 'series',
  });
  const episodes = useQuery({
    queryKey: ['content-episodes', contentId],
    queryFn: async () => (await apiRequest<Episode[]>(`/episodes?series_id=${contentId}&page=1&limit=100`)).data,
    enabled: kind === 'series',
  });
  const assets = useQuery({
    queryKey: ['video-assets'],
    queryFn: async () => (await apiRequest<VideoAsset[]>('/video-assets?page=1&limit=100')).data,
  });

  useEffect(() => {
    if (!detail.data) return;
    const row = detail.data;
    setForm({
      title: row.title ?? '', slug: row.slug ?? '', original_title: row.original_title ?? '',
      short_description: row.short_description ?? '', description: row.description ?? '',
      poster_url: row.poster_url ?? '', backdrop_url: row.backdrop_url ?? '',
      trailer_url: row.trailer_url ?? '', release_date: row.release_date ?? '',
      country_id: row.country?.id ?? '', original_language_id: row.original_language?.id ?? '',
      age_rating: row.age_rating ?? 'all', visibility: row.visibility ?? 'private',
      featured: row.featured ?? false, premium: row.premium ?? false,
      rating: String(row.rating ?? 0), genre_ids: row.genres?.map((item) => item.id) ?? [],
      tag_ids: row.tags?.map((item) => item.id) ?? [], seo_title: row.seo?.title ?? '',
      seo_description: row.seo?.description ?? '', series_status: row.series_status ?? 'draft',
      orientation: row.orientation ?? 'horizontal',
      duration_seconds: row.duration_seconds == null ? '' : String(row.duration_seconds),
      access_type: row.access_type ?? 'free', coin_price: String(row.coin_price ?? 0),
      video_asset_id: row.video_asset?.id ?? '',
    });
  }, [detail.data]);

  useEffect(() => {
    if (kind !== 'series' || !seasons.data) return;
    const nextSeason = Math.max(0, ...seasons.data.map((item) => item.season_number)) + 1;
    setSeasonForm((current) => ({ ...current, season_number: String(nextSeason) }));
  }, [kind, seasons.data]);

  useEffect(() => {
    if (kind !== 'series' || !episodes.data) return;
    const nextEpisode = Math.max(0, ...episodes.data.map((item) => item.episode_number)) + 1;
    setEpisodeForm((current) => ({ ...current, episode_number: String(nextEpisode) }));
  }, [kind, episodes.data]);

  const refreshDetail = () => client.invalidateQueries({ queryKey: ['content-detail', kind, contentId] });
  const refreshSeries = () => {
    client.invalidateQueries({ queryKey: ['content-seasons', contentId] });
    client.invalidateQueries({ queryKey: ['content-episodes', contentId] });
    refreshDetail();
  };
  const refreshAssets = () => client.invalidateQueries({ queryKey: ['video-assets'] });

  const save = useMutation({
    mutationFn: async () => {
      if (!form.title.trim()) throw new Error('Title is required.');
      if (['coin_unlock', 'premium_or_coin'].includes(form.access_type) && Number(form.coin_price) < 1) {
        throw new Error('Coin price must be at least 1 for coin access.');
      }
      const common: Record<string, unknown> = {
        title: form.title.trim(), slug: form.slug.trim(), original_title: nullable(form.original_title),
        short_description: nullable(form.short_description), description: nullable(form.description),
        poster_url: nullable(form.poster_url), backdrop_url: nullable(form.backdrop_url),
        trailer_url: nullable(form.trailer_url), release_date: nullable(form.release_date),
        country_id: nullable(form.country_id), original_language_id: nullable(form.original_language_id),
        age_rating: form.age_rating, visibility: form.visibility, featured: form.featured,
        premium: form.premium, rating: Number(form.rating || 0), genre_ids: form.genre_ids,
        tag_ids: form.tag_ids, seo_title: nullable(form.seo_title),
        seo_description: nullable(form.seo_description),
      };
      const specific = kind === 'series'
        ? { series_status: form.series_status, orientation: form.orientation }
        : {
            duration_seconds: form.duration_seconds ? Number(form.duration_seconds) : null,
            video_asset_id: nullable(form.video_asset_id), access_type: form.access_type,
            coin_price: Number(form.coin_price || 0),
          };
      return apiRequest<ContentDetail>(`/${kind}/${contentId}`, {
        method: 'PATCH', body: JSON.stringify({ ...common, ...specific }),
      });
    },
    onSuccess: () => { setNotice('Changes saved.'); refreshDetail(); },
  });
  const publish = useMutation({
    mutationFn: () => apiRequest<ContentDetail>(`/${kind}/${contentId}/publish`, { method: 'POST' }),
    onSuccess: () => { setNotice(`${kind === 'series' ? 'Series' : 'Movie'} published.`); refreshDetail(); },
  });
  const attachMovieAsset = useMutation({
    mutationFn: (assetId: string) => apiRequest<ContentDetail>(`/movies/${contentId}`, {
      method: 'PATCH', body: JSON.stringify({ video_asset_id: assetId }),
    }),
    onSuccess: (response) => {
      setForm((current) => ({ ...current, video_asset_id: response.data.video_asset?.id ?? '' }));
      setNotice('Video attached to the movie.');
      refreshDetail();
    },
  });
  const createSeason = useMutation({
    mutationFn: () => apiRequest<Season>('/seasons', {
      method: 'POST', body: JSON.stringify({
        series_id: contentId, season_number: Number(seasonForm.season_number),
        title: nullable(seasonForm.title), description: nullable(seasonForm.description),
      }),
    }),
    onSuccess: (response) => {
      setNotice(`Season ${response.data.season_number} created.`);
      setSeasonForm((current) => ({ ...current, title: '', description: '' }));
      refreshSeries();
    },
  });
  const publishSeason = useMutation({
    mutationFn: (id: string) => apiRequest(`/seasons/${id}/publish`, { method: 'POST' }),
    onSuccess: () => { setNotice('Season published.'); refreshSeries(); },
  });
  const archiveSeason = useMutation({
    mutationFn: (id: string) => apiRequest(`/seasons/${id}`, { method: 'DELETE' }),
    onSuccess: () => { setNotice('Season archived.'); refreshSeries(); },
  });
  const createEpisode = useMutation({
    mutationFn: async () => {
      if (!episodeForm.title.trim()) throw new Error('Episode title is required.');
      if (['coin_unlock', 'premium_or_coin'].includes(episodeForm.access_type) && Number(episodeForm.coin_price) < 1) {
        throw new Error('Coin price must be at least 1 for coin access.');
      }
      return apiRequest<Episode>('/episodes', {
        method: 'POST', body: JSON.stringify({
          series_id: contentId, season_id: nullable(episodeForm.season_id),
          episode_number: Number(episodeForm.episode_number), title: episodeForm.title.trim(),
          description: nullable(episodeForm.description), thumbnail_url: nullable(episodeForm.thumbnail_url),
          video_asset_id: nullable(episodeForm.video_asset_id), orientation: episodeForm.orientation,
          access_type: episodeForm.access_type, coin_price: Number(episodeForm.coin_price || 0),
          premium: episodeForm.premium,
        }),
      });
    },
    onSuccess: (response) => {
      setNotice(`Episode ${response.data.episode_number} created.`);
      setEpisodeForm((current) => ({ ...current, title: '', description: '', thumbnail_url: '', video_asset_id: '' }));
      refreshSeries();
    },
  });
  const publishEpisode = useMutation({
    mutationFn: (id: string) => apiRequest(`/episodes/${id}/publish`, { method: 'POST' }),
    onSuccess: () => { setNotice('Episode published.'); refreshSeries(); },
  });
  const archiveEpisode = useMutation({
    mutationFn: (id: string) => apiRequest(`/episodes/${id}`, { method: 'DELETE' }),
    onSuccess: () => { setNotice('Episode archived.'); refreshSeries(); },
  });

  const mutationError = save.error ?? publish.error ?? attachMovieAsset.error ?? createSeason.error
    ?? publishSeason.error ?? archiveSeason.error ?? createEpisode.error ?? publishEpisode.error
    ?? archiveEpisode.error;

  const readyAssets = useMemo(
    () => assets.data?.filter((asset) => asset.status === 'ready') ?? [],
    [assets.data],
  );

  const selectAsset = (asset: VideoAsset) => {
    if (asset.status !== 'ready') return;
    if (kind === 'movies') {
      setForm((current) => ({ ...current, video_asset_id: asset.id }));
      attachMovieAsset.mutate(asset.id);
    } else {
      setEpisodeForm((current) => ({ ...current, video_asset_id: asset.id }));
      setNotice('Video selected for the new episode. Complete the episode form, then create it.');
    }
  };

  const updatePolledAsset = (asset: VideoAsset) => {
    setUploadStatus(asset.status === 'ready' ? 'Video is ready.' : `Mux status: ${asset.status}…`);
    client.setQueryData<VideoAsset[]>(['video-assets'], (current) => {
      if (!current) return [asset];
      return current.some((item) => item.id === asset.id)
        ? current.map((item) => item.id === asset.id ? asset : item)
        : [asset, ...current];
    });
  };

  const uploadFile = async (file: File) => {
    setUploadError(''); setNotice(''); setUploadProgress(0); setUploadStatus('Creating secure Mux upload…');
    try {
      const contentType = file.type || (file.name.toLowerCase().endsWith('.mov') ? 'video/quicktime' : 'video/mp4');
      const session = (await apiRequest<UploadSession>('/video-assets/upload-sessions', {
        method: 'POST', body: JSON.stringify({
          file_name: file.name, content_type: contentType, file_size_bytes: file.size,
          max_duration_seconds: 14400, protocol: 'auto',
        }),
      })).data;
      setUploadStatus('Uploading directly to Mux…');
      await new Promise<void>((resolve, reject) => {
        const request = new XMLHttpRequest();
        request.open('PUT', session.upload_url);
        Object.entries(session.upload_headers ?? {}).forEach(([key, value]) => request.setRequestHeader(key, value));
        if (!Object.keys(session.upload_headers ?? {}).some((key) => key.toLowerCase() === 'content-type')) {
          request.setRequestHeader('Content-Type', contentType);
        }
        request.upload.onprogress = (event) => {
          if (event.lengthComputable) setUploadProgress(Math.round((event.loaded / event.total) * 100));
        };
        request.onerror = () => reject(new Error('The browser could not upload the video to Mux.'));
        request.onabort = () => reject(new Error('The upload was cancelled.'));
        request.onload = () => request.status >= 200 && request.status < 300
          ? resolve()
          : reject(new Error(`Mux upload failed (${request.status}).`));
        request.send(file);
      });
      setUploadProgress(100); setUploadStatus('Upload complete. Mux is processing the video…');
      const asset = await pollVideoAsset(session.video_asset_id, updatePolledAsset);
      await refreshAssets();
      if (asset?.status === 'ready') selectAsset(asset);
      else if (asset?.status === 'failed') throw new Error('Mux could not process this video. Try another file.');
      else setNotice('The video is still processing. Use Refresh status below in a moment.');
    } catch (error) {
      setUploadError(errorMessage(error));
      setUploadStatus('');
    }
  };

  const ingestSource = async () => {
    setUploadError(''); setNotice(''); setUploadProgress(0); setUploadStatus('Sending source URL to Mux…');
    try {
      if (!sourceUrl.startsWith('https://')) throw new Error('Source URL must start with https://');
      const asset = (await apiRequest<VideoAsset>('/video-assets/ingest', {
        method: 'POST', body: JSON.stringify({ source_url: sourceUrl.trim(), file_name: sourceName.trim() || 'drovixa-video.mp4' }),
      })).data;
      updatePolledAsset(asset);
      const refreshed = asset.status === 'ready' ? asset : await pollVideoAsset(asset.id, updatePolledAsset);
      await refreshAssets();
      if (refreshed?.status === 'ready') selectAsset(refreshed);
      else if (refreshed?.status === 'failed') throw new Error('Mux could not ingest this URL.');
      else setNotice('The video is still processing. Use Refresh status below in a moment.');
    } catch (error) {
      setUploadError(errorMessage(error));
      setUploadStatus('');
    }
  };

  const refreshSingleAsset = async (assetId: string) => {
    setUploadError('');
    try {
      const asset = (await apiRequest<VideoAsset>(`/video-assets/${assetId}/refresh`, { method: 'POST' })).data;
      updatePolledAsset(asset);
      await refreshAssets();
      if (asset.status === 'ready') selectAsset(asset);
    } catch (error) {
      setUploadError(errorMessage(error));
    }
  };

  return (
    <div className="page">
      <PageHeading
        eyebrow="Content studio"
        title={detail.data?.title ?? 'Loading content…'}
        description={kind === 'series'
          ? 'Edit the series, create seasons and episodes, upload videos to Mux, then publish.'
          : 'Edit movie metadata, upload and attach its Mux video, then publish.'}
        action={<Link className="button button-quiet" href="/content">← Back to catalog</Link>}
      />
      <QueryState loading={detail.isLoading} error={detail.error}>
        {detail.data ? (
          <>
            <div className="studio-summary">
              <Badge tone={detail.data.status === 'published' ? 'success' : 'warning'}>{detail.data.status}</Badge>
              <span>/{detail.data.slug}</span>
              {kind === 'series' ? <span>{detail.data.total_seasons ?? 0} seasons · {detail.data.total_episodes ?? 0} episodes</span> : null}
              {detail.data.updated_at ? <span>Updated {formatDate(detail.data.updated_at)}</span> : null}
            </div>
            {notice ? <div className="notice success studio-notice">{notice}</div> : null}
            {mutationError ? <div className="notice studio-notice">{mutationError.message}</div> : null}

            <section className="studio-layout">
              <article className="panel">
                <div className="panel-header"><div><h3>Title &amp; discovery</h3><p>Everything viewers see in the catalog.</p></div></div>
                <div className="form-grid">
                  <div className="form-field"><label>Title *</label><input className="field" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></div>
                  <div className="form-field"><label>Slug *</label><input className="field" value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value })} /></div>
                  <div className="form-field"><label>Original title</label><input className="field" value={form.original_title} onChange={(event) => setForm({ ...form, original_title: event.target.value })} /></div>
                  <div className="form-field"><label>Release date</label><input className="field" type="date" value={form.release_date} onChange={(event) => setForm({ ...form, release_date: event.target.value })} /></div>
                  <div className="form-field full"><label>Short description</label><textarea className="textarea compact" maxLength={500} value={form.short_description} onChange={(event) => setForm({ ...form, short_description: event.target.value })} /></div>
                  <div className="form-field full"><label>Full description</label><textarea className="textarea" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></div>
                  <div className="form-field"><label>Poster URL</label><input className="field" type="url" placeholder="https://…" value={form.poster_url} onChange={(event) => setForm({ ...form, poster_url: event.target.value })} /></div>
                  <div className="form-field"><label>Backdrop URL</label><input className="field" type="url" placeholder="https://…" value={form.backdrop_url} onChange={(event) => setForm({ ...form, backdrop_url: event.target.value })} /></div>
                  <div className="form-field full"><label>Trailer URL</label><input className="field" type="url" placeholder="https://…" value={form.trailer_url} onChange={(event) => setForm({ ...form, trailer_url: event.target.value })} /></div>
                </div>
                {(form.poster_url || form.backdrop_url) ? <div className="media-previews">
                  {form.poster_url ? <img src={form.poster_url} alt="Poster preview" /> : null}
                  {form.backdrop_url ? <img className="wide" src={form.backdrop_url} alt="Backdrop preview" /> : null}
                </div> : null}
              </article>

              <aside className="panel">
                <div className="panel-header"><div><h3>Publishing</h3><p>Audience, access and catalog placement.</p></div></div>
                <div className="form-grid">
                  <div className="form-field"><label>Visibility</label><select className="select" value={form.visibility} onChange={(event) => setForm({ ...form, visibility: event.target.value })}><option value="private">Private</option><option value="public">Public</option><option value="unlisted">Unlisted</option><option value="scheduled">Scheduled</option></select></div>
                  <div className="form-field"><label>Age rating</label><select className="select" value={form.age_rating} onChange={(event) => setForm({ ...form, age_rating: event.target.value })}><option value="all">All</option><option value="7+">7+</option><option value="13+">13+</option><option value="16+">16+</option><option value="18+">18+</option></select></div>
                  <div className="form-field"><label>Country</label><select className="select" value={form.country_id} onChange={(event) => setForm({ ...form, country_id: event.target.value })}><option value="">Not set</option>{countries.data?.filter((item) => item.active !== false).map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></div>
                  <div className="form-field"><label>Original language</label><select className="select" value={form.original_language_id} onChange={(event) => setForm({ ...form, original_language_id: event.target.value })}><option value="">Not set</option>{languages.data?.filter((item) => item.active !== false).map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></div>
                  <div className="form-field"><label>Rating (0–10)</label><input className="field" type="number" min="0" max="10" step="0.1" value={form.rating} onChange={(event) => setForm({ ...form, rating: event.target.value })} /></div>
                  {kind === 'series' ? <>
                    <div className="form-field"><label>Series state</label><select className="select" value={form.series_status} onChange={(event) => setForm({ ...form, series_status: event.target.value })}><option value="draft">Draft</option><option value="scheduled">Scheduled</option><option value="ongoing">Ongoing</option><option value="completed">Completed</option><option value="paused">Paused</option></select></div>
                    <div className="form-field full"><label>Orientation</label><select className="select" value={form.orientation} onChange={(event) => setForm({ ...form, orientation: event.target.value })}><option value="horizontal">Horizontal</option><option value="vertical">Vertical</option><option value="mixed">Mixed</option></select></div>
                  </> : <>
                    <div className="form-field"><label>Duration (seconds)</label><input className="field" type="number" min="0" value={form.duration_seconds} onChange={(event) => setForm({ ...form, duration_seconds: event.target.value })} /></div>
                    <div className="form-field"><label>Access</label><select className="select" value={form.access_type} onChange={(event) => setForm({ ...form, access_type: event.target.value })}><option value="free">Free</option><option value="premium_subscription">Premium subscription</option><option value="coin_unlock">Coin unlock</option><option value="premium_or_coin">Premium or coins</option><option value="ad_unlock">Ad unlock</option><option value="scheduled_free">Scheduled free</option></select></div>
                    <div className="form-field"><label>Coin price</label><input className="field" type="number" min="0" value={form.coin_price} onChange={(event) => setForm({ ...form, coin_price: event.target.value })} /></div>
                  </>}
                  <label className="check-row"><input type="checkbox" checked={form.featured} onChange={(event) => setForm({ ...form, featured: event.target.checked })} /> Featured</label>
                  <label className="check-row"><input type="checkbox" checked={form.premium} onChange={(event) => setForm({ ...form, premium: event.target.checked })} /> Premium</label>
                  <div className="form-field full"><label>Genres (Ctrl/Cmd + click for several)</label><select className="select multi-select" multiple value={form.genre_ids} onChange={(event) => setForm({ ...form, genre_ids: multiSelectValues(event) })}>{genres.data?.filter((item) => item.active !== false).map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></div>
                  <div className="form-field full"><label>Tags</label><select className="select multi-select" multiple value={form.tag_ids} onChange={(event) => setForm({ ...form, tag_ids: multiSelectValues(event) })}>{tags.data?.filter((item) => item.active !== false).map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></div>
                  <div className="form-field full"><label>SEO title</label><input className="field" value={form.seo_title} onChange={(event) => setForm({ ...form, seo_title: event.target.value })} /></div>
                  <div className="form-field full"><label>SEO description</label><textarea className="textarea compact" value={form.seo_description} onChange={(event) => setForm({ ...form, seo_description: event.target.value })} /></div>
                </div>
                <div className="studio-actions">
                  <button className="button button-accent" disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending ? 'Saving…' : 'Save changes'}</button>
                  <button className="button button-primary" disabled={publish.isPending || detail.data.status === 'published'} onClick={() => publish.mutate()}>{detail.data.status === 'published' ? 'Published' : publish.isPending ? 'Publishing…' : `Publish ${kind === 'series' ? 'series' : 'movie'}`}</button>
                </div>
                {kind === 'series' && (detail.data.total_episodes ?? 0) === 0 ? <div className="notice warning-note">This series has no episodes yet. Add a season and an episode below before promoting it to viewers.</div> : null}
                {kind === 'movies' && !form.video_asset_id ? <div className="notice warning-note">A movie needs a ready Mux video before it can be published.</div> : null}
              </aside>
            </section>

            <section className="panel studio-section">
              <div className="panel-header"><div><h3>Video uploader</h3><p>The browser sends the file directly to Mux. Drovixa stores only the secure asset reference.</p></div><Badge tone={form.video_asset_id || episodeForm.video_asset_id ? 'success' : 'warning'}>{form.video_asset_id || episodeForm.video_asset_id ? 'video selected' : 'video required'}</Badge></div>
              <div className="upload-grid">
                <div className="upload-zone">
                  <strong>Upload a video file</strong><span>MP4, MOV, MKV, WebM or M4V. Keep this tab open while upload runs.</span>
                  <label className="button button-accent file-button">Choose video<input type="file" accept="video/mp4,video/quicktime,video/x-matroska,video/webm,video/x-m4v" onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadFile(file); event.target.value = ''; }} /></label>
                  {uploadStatus ? <div className="upload-status"><span>{uploadStatus}</span><strong>{uploadProgress}%</strong></div> : null}
                  {uploadStatus ? <div className="progress-track"><div className="progress-bar" style={{ width: `${uploadProgress}%` }} /></div> : null}
                  {uploadError ? <div className="notice">{uploadError}</div> : null}
                </div>
                <div className="upload-zone">
                  <strong>Or import an HTTPS source</strong><span>Use a direct video file URL that Mux can reach.</span>
                  <input className="field" type="url" placeholder="https://…/movie.mp4" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} />
                  <input className="field" placeholder="File name, for example movie.mp4" value={sourceName} onChange={(event) => setSourceName(event.target.value)} />
                  <button className="button button-quiet" disabled={!sourceUrl.trim() || Boolean(uploadStatus)} onClick={() => void ingestSource()}>Import into Mux</button>
                </div>
              </div>
              <div className="asset-list">
                {assets.isLoading ? <div className="skeleton" style={{ height: 72 }} /> : null}
                {assets.data?.map((asset) => <div className={`asset-card ${form.video_asset_id === asset.id || episodeForm.video_asset_id === asset.id ? 'selected' : ''}`} key={asset.id}>
                  {asset.thumbnail_url ? <img src={asset.thumbnail_url} alt="Video thumbnail" /> : <div className="asset-placeholder">▶</div>}
                  <div className="primary-cell"><strong>{asset.provider} · {asset.provider_asset_id.slice(0, 16)}…</strong><small>{asset.duration_seconds ? `${Math.round(asset.duration_seconds / 60)} min · ` : ''}{asset.width && asset.height ? `${asset.width}×${asset.height} · ` : ''}{formatDate(asset.created_at)}</small></div>
                  <Badge tone={asset.status === 'ready' ? 'success' : asset.status === 'failed' ? 'danger' : 'warning'}>{asset.status}</Badge>
                  <div className="actions">{asset.status === 'ready' ? <button className="button button-accent" onClick={() => selectAsset(asset)}>Use this video</button> : <button className="button button-quiet" onClick={() => void refreshSingleAsset(asset.id)}>Refresh status</button>}</div>
                </div>)}
                {!assets.isLoading && assets.data?.length === 0 ? <div className="empty-state compact-empty"><div><strong>No video assets yet</strong><span>Choose a local file or import a source URL above.</span></div></div> : null}
              </div>
            </section>

            {kind === 'series' ? <>
              <section className="studio-layout studio-section">
                <article className="panel">
                  <div className="panel-header"><div><h3>Seasons</h3><p>Create and publish the containers for your episodes.</p></div></div>
                  <div className="form-grid">
                    <div className="form-field"><label>Season number</label><input className="field" type="number" min="1" value={seasonForm.season_number} onChange={(event) => setSeasonForm({ ...seasonForm, season_number: event.target.value })} /></div>
                    <div className="form-field"><label>Season title</label><input className="field" placeholder="Season 1" value={seasonForm.title} onChange={(event) => setSeasonForm({ ...seasonForm, title: event.target.value })} /></div>
                    <div className="form-field full"><label>Description</label><textarea className="textarea compact" value={seasonForm.description} onChange={(event) => setSeasonForm({ ...seasonForm, description: event.target.value })} /></div>
                    <button className="button button-accent" disabled={createSeason.isPending} onClick={() => createSeason.mutate()}>Create season</button>
                  </div>
                  <div className="record-list">{seasons.data?.map((season) => <div className="record-card" key={season.id}><div className="primary-cell"><strong>Season {season.season_number}{season.title ? ` · ${season.title}` : ''}</strong><small>{season.description || 'No description'}</small></div><Badge tone={season.status === 'published' ? 'success' : 'warning'}>{season.status}</Badge><div className="actions">{season.status !== 'published' ? <button className="button button-primary" onClick={() => publishSeason.mutate(season.id)}>Publish</button> : null}<button className="button button-danger" onClick={() => window.confirm('Archive this empty season?') && archiveSeason.mutate(season.id)}>Archive</button></div></div>)}</div>
                </article>
                <article className="panel">
                  <div className="panel-header"><div><h3>New episode</h3><p>Select a ready video above, then create the episode.</p></div></div>
                  <div className="form-grid">
                    <div className="form-field"><label>Season</label><select className="select" value={episodeForm.season_id} onChange={(event) => setEpisodeForm({ ...episodeForm, season_id: event.target.value })}><option value="">No season</option>{seasons.data?.map((season) => <option value={season.id} key={season.id}>Season {season.season_number}{season.title ? ` · ${season.title}` : ''}</option>)}</select></div>
                    <div className="form-field"><label>Episode number</label><input className="field" type="number" min="1" value={episodeForm.episode_number} onChange={(event) => setEpisodeForm({ ...episodeForm, episode_number: event.target.value })} /></div>
                    <div className="form-field full"><label>Title *</label><input className="field" value={episodeForm.title} onChange={(event) => setEpisodeForm({ ...episodeForm, title: event.target.value })} /></div>
                    <div className="form-field full"><label>Description</label><textarea className="textarea compact" value={episodeForm.description} onChange={(event) => setEpisodeForm({ ...episodeForm, description: event.target.value })} /></div>
                    <div className="form-field full"><label>Thumbnail URL</label><input className="field" type="url" placeholder="https://…" value={episodeForm.thumbnail_url} onChange={(event) => setEpisodeForm({ ...episodeForm, thumbnail_url: event.target.value })} /></div>
                    <div className="form-field"><label>Orientation</label><select className="select" value={episodeForm.orientation} onChange={(event) => setEpisodeForm({ ...episodeForm, orientation: event.target.value })}><option value="horizontal">Horizontal</option><option value="vertical">Vertical</option></select></div>
                    <div className="form-field"><label>Access</label><select className="select" value={episodeForm.access_type} onChange={(event) => setEpisodeForm({ ...episodeForm, access_type: event.target.value })}><option value="free">Free</option><option value="premium_subscription">Premium subscription</option><option value="coin_unlock">Coin unlock</option><option value="premium_or_coin">Premium or coins</option><option value="ad_unlock">Ad unlock</option><option value="scheduled_free">Scheduled free</option></select></div>
                    <div className="form-field"><label>Coin price</label><input className="field" type="number" min="0" value={episodeForm.coin_price} onChange={(event) => setEpisodeForm({ ...episodeForm, coin_price: event.target.value })} /></div>
                    <label className="check-row"><input type="checkbox" checked={episodeForm.premium} onChange={(event) => setEpisodeForm({ ...episodeForm, premium: event.target.checked })} /> Premium</label>
                    <div className="form-field full"><label>Selected video</label><select className="select" value={episodeForm.video_asset_id} onChange={(event) => setEpisodeForm({ ...episodeForm, video_asset_id: event.target.value })}><option value="">No video yet</option>{readyAssets.map((asset) => <option value={asset.id} key={asset.id}>{asset.provider_asset_id} · {asset.duration_seconds ? `${Math.round(asset.duration_seconds / 60)} min` : 'ready'}</option>)}</select></div>
                    <button className="button button-accent" disabled={createEpisode.isPending} onClick={() => createEpisode.mutate()}>Create episode</button>
                  </div>
                </article>
              </section>

              <section className="panel studio-section">
                <div className="panel-header"><div><h3>Episodes</h3><p>Publish only after the attached Mux asset is ready.</p></div><Badge>{episodes.data?.length ?? 0} total</Badge></div>
                <div className="record-list">{episodes.data?.map((episode) => <div className="record-card episode-card" key={episode.id}>
                  {episode.thumbnail_url || episode.video_asset?.thumbnail_url ? <img src={episode.thumbnail_url || episode.video_asset?.thumbnail_url || ''} alt="Episode thumbnail" /> : <div className="asset-placeholder">E{episode.episode_number}</div>}
                  <div className="primary-cell"><strong>Episode {episode.episode_number} · {episode.title}</strong><small>{episode.season_id ? `Season attached · ` : ''}{episode.access_type} · {episode.video_asset ? `video ${episode.video_asset.status}` : 'no video'}</small></div>
                  <Badge tone={episode.status === 'published' ? 'success' : 'warning'}>{episode.status}</Badge>
                  <div className="actions">{episode.status !== 'published' ? <button className="button button-primary" disabled={episode.video_asset?.status !== 'ready'} title={episode.video_asset?.status !== 'ready' ? 'Attach a ready video first' : ''} onClick={() => publishEpisode.mutate(episode.id)}>Publish</button> : null}<button className="button button-danger" onClick={() => window.confirm(`Archive ${episode.title}?`) && archiveEpisode.mutate(episode.id)}>Archive</button></div>
                </div>)}</div>
                {!episodes.isLoading && episodes.data?.length === 0 ? <div className="empty-state compact-empty"><div><strong>No episodes yet</strong><span>Create the first episode with the form above.</span></div></div> : null}
              </section>
            </> : null}
          </>
        ) : null}
      </QueryState>
    </div>
  );
}
