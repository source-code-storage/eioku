import { useEffect, useState } from 'react';

interface Video {
  video_id: string;
  filename: string;
  file_size: number;
  status: string;
}

interface Props {
  apiUrl?: string;
  onSelectVideo: (videoId: string) => void;
}

export default function VideoGallery({ apiUrl = 'http://localhost:8080', onSelectVideo }: Props) {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [failedThumbnails, setFailedThumbnails] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetch(`${apiUrl}/api/v1/videos/`)
      .then(res => res.json())
      .then(data => {
        setVideos(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [apiUrl]);

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const handleThumbnailError = (videoId: string) => {
    setFailedThumbnails(prev => new Set(prev).add(videoId));
  };

  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '60px 20px',
          minHeight: '300px',
        }}
      >
        <div
          style={{
            width: '48px',
            height: '48px',
            border: '4px solid #333',
            borderTop: '4px solid #1976d2',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            marginBottom: '16px',
          }}
        />
        <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
        <p style={{ color: '#999', fontSize: '16px', margin: 0 }}>Loading videos...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '60px 20px',
          minHeight: '300px',
          backgroundColor: '#1a1a1a',
          borderRadius: '8px',
          margin: '16px',
        }}
      >
        <div style={{ fontSize: '64px', marginBottom: '16px' }}>⚠️</div>
        <h3 style={{ color: '#ff6b6b', fontSize: '20px', margin: '0 0 8px 0', fontWeight: 500 }}>
          Something went wrong
        </h3>
        <p style={{ color: '#999', fontSize: '14px', margin: 0, textAlign: 'center' }}>{error}</p>
      </div>
    );
  }

  if (videos.length === 0) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '60px 20px',
          minHeight: '300px',
          backgroundColor: '#1a1a1a',
          borderRadius: '8px',
          margin: '16px',
        }}
      >
        <div style={{ fontSize: '64px', marginBottom: '16px', opacity: 0.5 }}>🎬</div>
        <h3 style={{ color: '#fff', fontSize: '20px', margin: '0 0 8px 0', fontWeight: 500 }}>
          No videos found
        </h3>
        <p style={{ color: '#999', fontSize: '14px', margin: 0, textAlign: 'center' }}>
          Add videos to get started.
        </p>
      </div>
    );
  }

  return (
    <div style={{ padding: '16px' }}>
      <h2 style={{ color: '#fff', margin: '0 0 16px 0', fontSize: '18px', fontWeight: 500 }}>
        Videos ({videos.length})
      </h2>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: '16px',
        }}
      >
        {videos.map(video => {
          const hasFailed = failedThumbnails.has(video.video_id);
          const thumbnailUrl = `${apiUrl}/api/v1/thumbnails/${video.video_id}/0`;

          return (
            <div
              key={video.video_id}
              onClick={() => onSelectVideo(video.video_id)}
              style={{
                cursor: 'pointer',
                backgroundColor: '#2a2a2a',
                borderRadius: '8px',
                overflow: 'hidden',
                transition: 'transform 0.2s',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLDivElement).style.transform = 'scale(1.02)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLDivElement).style.transform = 'scale(1)';
              }}
            >
              {/* Thumbnail or placeholder */}
              <div
                style={{
                  width: '100%',
                  aspectRatio: '16/9',
                  backgroundColor: '#1a1a1a',
                  position: 'relative',
                }}
              >
                {hasFailed ? (
                  <div
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '48px',
                    }}
                  >
                    🎬
                  </div>
                ) : (
                  <img
                    src={thumbnailUrl}
                    alt={`Thumbnail for ${video.filename}`}
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      height: '100%',
                      objectFit: 'cover',
                    }}
                    onError={() => handleThumbnailError(video.video_id)}
                  />
                )}
              </div>

              {/* Video info */}
              <div style={{ padding: '12px', color: '#fff' }}>
                <p
                  style={{
                    margin: '0 0 4px 0',
                    fontSize: '14px',
                    fontWeight: 500,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  title={video.filename}
                >
                  {video.filename}
                </p>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '12px', color: '#999' }}>{formatFileSize(video.file_size)}</span>
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '2px 6px',
                      backgroundColor:
                        video.status === 'completed'
                          ? 'rgba(76, 175, 80, 0.2)'
                          : video.status === 'processing'
                            ? 'rgba(255, 152, 0, 0.2)'
                            : 'rgba(255, 255, 255, 0.1)',
                      color:
                        video.status === 'completed'
                          ? '#4caf50'
                          : video.status === 'processing'
                            ? '#ff9800'
                            : '#999',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 500,
                    }}
                  >
                    {video.status}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
