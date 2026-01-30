import { useState, useEffect } from 'react';
import GlobalJumpControl, { ArtifactType } from '../components/GlobalJumpControl';

/**
 * State passed to the player page when navigating from search results.
 */
export interface SearchNavigationState {
  artifactType: ArtifactType;
  label: string;
  query: string;
  confidence: number;
  timestampMs: number;
}

interface Props {
  /** API base URL (defaults to http://localhost:8080) */
  apiUrl?: string;
  
  /**
   * Callback when user navigates to a search result.
   * Called with the video_id, timestamp, and form state to preserve.
   */
  onNavigateToVideo: (
    videoId: string,
    timestampMs: number,
    formState: SearchNavigationState
  ) => void;
  
  /** Callback to go back to gallery */
  onBack: () => void;
  
  /** Initial form state (for returning from player page) */
  initialState?: Partial<SearchNavigationState>;
}

/**
 * SearchPage - Dedicated search page for cross-video artifact search.
 * 
 * This page renders the GlobalJumpControl without a video context,
 * allowing users to search across all videos in the library.
 * When a result is found, it navigates to the player page with the
 * result video loaded at the correct timestamp.
 * 
 * Requirements: 1.1.1, 1.1.2, 1.1.3
 */
export default function SearchPage({
  apiUrl = 'http://localhost:8080',
  onNavigateToVideo,
  onBack,
  initialState,
}: Props) {
  // Initial form state values (passed to GlobalJumpControl)
  const artifactType = initialState?.artifactType || 'object';
  const label = initialState?.label || '';
  const query = initialState?.query || '';
  const confidence = initialState?.confidence || 0;
  
  // Earliest video ID for starting point when no video is loaded
  const [earliestVideoId, setEarliestVideoId] = useState<string | null>(null);
  const [loadingEarliest, setLoadingEarliest] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Fetch the earliest video in the library to use as starting point.
   * This satisfies requirement 1.1.3: search from beginning of global timeline.
   */
  useEffect(() => {
    const fetchEarliestVideo = async () => {
      setLoadingEarliest(true);
      setError(null);
      
      try {
        const response = await fetch(
          `${apiUrl}/api/v1/videos?sort=file_created_at&order=asc&limit=1`
        );
        
        if (!response.ok) {
          throw new Error(`Failed to fetch videos: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.length > 0) {
          setEarliestVideoId(data[0].video_id);
        } else {
          setError('No videos found in library');
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown error';
        setError(`Failed to load video library: ${message}`);
        console.error('Failed to fetch earliest video:', err);
      } finally {
        setLoadingEarliest(false);
      }
    };

    fetchEarliestVideo();
  }, [apiUrl]);

  /**
   * Handle navigation to a search result.
   * Passes form state to the player page for preservation.
   */
  const handleNavigate = (videoId: string, timestampMs: number) => {
    onNavigateToVideo(videoId, timestampMs, {
      artifactType,
      label,
      query,
      confidence,
      timestampMs,
    });
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        minHeight: '100vh',
        backgroundColor: '#000',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '10px 20px',
          backgroundColor: '#1a1a1a',
          borderBottom: '1px solid #333',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button
            onClick={onBack}
            style={{
              padding: '8px 16px',
              backgroundColor: '#333',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px',
            }}
          >
            ← Back
          </button>
          <h2
            style={{
              margin: 0,
              color: '#fff',
              fontSize: '16px',
              fontWeight: '600',
            }}
          >
            Global Search
          </h2>
        </div>
      </div>

      {/* Main content */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'flex-start',
          padding: '40px 20px',
        }}
      >
        {/* Search description */}
        <div
          style={{
            maxWidth: '600px',
            width: '100%',
            marginBottom: '24px',
            textAlign: 'center',
          }}
        >
          <h1
            style={{
              color: '#fff',
              fontSize: '24px',
              fontWeight: '600',
              margin: '0 0 8px 0',
            }}
          >
            Search Your Video Library
          </h1>
          <p
            style={{
              color: '#999',
              fontSize: '14px',
              margin: 0,
            }}
          >
            Search for objects, faces, transcript text, OCR text, scenes, places,
            or locations across all your videos.
          </p>
        </div>

        {/* Error display */}
        {error && (
          <div
            style={{
              maxWidth: '600px',
              width: '100%',
              padding: '16px',
              backgroundColor: '#2a1a1a',
              border: '1px solid #f44336',
              borderRadius: '4px',
              marginBottom: '24px',
            }}
          >
            <p style={{ color: '#f44336', margin: 0, fontSize: '14px' }}>
              {error}
            </p>
          </div>
        )}

        {/* Loading state */}
        {loadingEarliest && (
          <div
            style={{
              maxWidth: '600px',
              width: '100%',
              padding: '16px',
              backgroundColor: '#2a2a2a',
              borderRadius: '4px',
              marginBottom: '24px',
              textAlign: 'center',
            }}
          >
            <p style={{ color: '#999', margin: 0, fontSize: '14px' }}>
              Loading video library...
            </p>
          </div>
        )}

        {/* GlobalJumpControl - rendered without video context */}
        {!loadingEarliest && earliestVideoId && (
          <div
            style={{
              maxWidth: '600px',
              width: '100%',
              borderRadius: '8px',
              overflow: 'hidden',
              border: '1px solid #333',
            }}
          >
            <GlobalJumpControl
              apiUrl={apiUrl}
              onNavigate={handleNavigate}
              initialArtifactType={artifactType}
              initialLabel={label}
              initialQuery={query}
              initialConfidence={confidence}
            />
          </div>
        )}

        {/* Instructions */}
        <div
          style={{
            maxWidth: '600px',
            width: '100%',
            marginTop: '24px',
            padding: '16px',
            backgroundColor: '#1a1a1a',
            borderRadius: '8px',
            border: '1px solid #333',
          }}
        >
          <h3
            style={{
              color: '#fff',
              fontSize: '14px',
              fontWeight: '600',
              margin: '0 0 12px 0',
            }}
          >
            How to use
          </h3>
          <ol
            style={{
              color: '#999',
              fontSize: '13px',
              margin: 0,
              paddingLeft: '20px',
              lineHeight: '1.8',
            }}
          >
            <li>Select an artifact type from the dropdown</li>
            <li>Enter a search term (if applicable for the type)</li>
            <li>Adjust confidence threshold (for objects, faces, places)</li>
            <li>Click "Next" to find the first match</li>
            <li>Continue clicking "Next" or "Previous" to browse results</li>
          </ol>
        </div>
      </div>
    </div>
  );
}
