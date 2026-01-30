import React, { useState, useEffect, useCallback } from 'react';

/**
 * Represents a single artifact search result from the API.
 */
export interface ArtifactSearchResult {
  video_id: string;
  artifact_id: string;
  artifact_type: string;
  start_ms: number;
  thumbnail_url: string;
  preview: Record<string, unknown>;
  video_filename: string;
  file_created_at: string | null;
  artifact_count: number | null; // Only present when group_by_video=true
}

/**
 * Paginated response from the artifact search API.
 */
export interface ArtifactSearchResponse {
  results: ArtifactSearchResult[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Search parameters for the artifact search API.
 */
export interface ArtifactSearchParams {
  kind: string;
  label?: string;
  query?: string;
  filename?: string;
  min_confidence?: number;
  limit?: number;
  offset?: number;
  group_by_video?: boolean;
}

/**
 * Props for the ArtifactGallery component.
 */
export interface ArtifactGalleryProps {
  apiBaseUrl?: string;
  onArtifactClick?: (result: ArtifactSearchResult) => void;
}

/**
 * ArtifactGallery component displays search results as a thumbnail grid.
 *
 * Features:
 * - Search form (kind selector, label/query input, confidence slider)
 * - Thumbnail grid with responsive layout
 * - Pagination controls or infinite scroll
 * - Loading and empty states
 *
 * @requirements 5.1
 */
export default function ArtifactGallery({
  apiBaseUrl = '',
  onArtifactClick,
}: ArtifactGalleryProps) {
  // Search results state
  const [results, setResults] = useState<ArtifactSearchResult[]>([]);
  const [total, setTotal] = useState<number>(0);

  // Loading and error states
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Pagination state
  const [limit] = useState<number>(20);
  const [offset, setOffset] = useState<number>(0);

  // Search form state (will be used in Task 19)
  const [kind, setKind] = useState<string>('object');
  const [label, setLabel] = useState<string>('');
  const [query, setQuery] = useState<string>('');
  const [filename, setFilename] = useState<string>('');
  const [minConfidence, setMinConfidence] = useState<number>(0.5);
  const [groupByVideo, setGroupByVideo] = useState<boolean>(false);

  // Track if initial URL state has been loaded
  const [urlStateLoaded, setUrlStateLoaded] = useState<boolean>(false);

  /**
   * Reads URL query params and initializes form state.
   * Called on component mount to restore state from shareable URLs.
   * @requirements 6.6
   */
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);

    // Read kind param (default: 'object')
    const urlKind = params.get('kind');
    if (urlKind && ['object', 'face', 'transcript', 'ocr', 'scene', 'place'].includes(urlKind)) {
      setKind(urlKind);
    }

    // Read label param
    const urlLabel = params.get('label');
    if (urlLabel) {
      setLabel(urlLabel);
    }

    // Read query param
    const urlQuery = params.get('query');
    if (urlQuery) {
      setQuery(urlQuery);
    }

    // Read filename param
    const urlFilename = params.get('filename');
    if (urlFilename) {
      setFilename(urlFilename);
    }

    // Read min_confidence param
    const urlMinConfidence = params.get('min_confidence');
    if (urlMinConfidence) {
      const confidence = parseFloat(urlMinConfidence);
      if (!isNaN(confidence) && confidence >= 0 && confidence <= 1) {
        setMinConfidence(confidence);
      }
    }

    // Read group_by_video param
    const urlGroupByVideo = params.get('group_by_video');
    if (urlGroupByVideo === 'true') {
      setGroupByVideo(true);
    }

    // Read offset param
    const urlOffset = params.get('offset');
    if (urlOffset) {
      const offsetValue = parseInt(urlOffset, 10);
      if (!isNaN(offsetValue) && offsetValue >= 0) {
        setOffset(offsetValue);
      }
    }

    setUrlStateLoaded(true);
  }, []);

  /**
   * Updates URL query params to reflect current form state.
   * Enables shareable/bookmarkable search URLs.
   * Uses replaceState to avoid adding to browser history on each search.
   * @requirements 6.6
   */
  const updateUrlParams = useCallback((searchOffset: number) => {
    const params = new URLSearchParams();

    // Always include kind
    params.set('kind', kind);

    // Include optional filters only if they have values
    if ((kind === 'object' || kind === 'place') && label.trim()) {
      params.set('label', label.trim());
    }
    if ((kind === 'transcript' || kind === 'ocr') && query.trim()) {
      params.set('query', query.trim());
    }
    if (filename.trim()) {
      params.set('filename', filename.trim());
    }
    if (kind === 'object' || kind === 'face' || kind === 'place') {
      params.set('min_confidence', minConfidence.toString());
    }
    if (groupByVideo) {
      params.set('group_by_video', 'true');
    }
    if (searchOffset > 0) {
      params.set('offset', searchOffset.toString());
    }

    // Update URL without navigation using replaceState
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState({}, '', newUrl);
  }, [kind, label, query, filename, minConfidence, groupByVideo]);

  /**
   * Searches artifacts using the API with current form state.
   * Builds query params from form state and calls GET /v1/artifacts/search.
   * Updates results, total, loading, and error states.
   * @requirements 6.5
   */
  const searchArtifacts = useCallback(async (searchOffset: number = 0) => {
    setLoading(true);
    setError(null);
    // Clear failed thumbnails when starting a new search
    setFailedThumbnails(new Set());

    try {
      // Build query params from form state
      const params = new URLSearchParams();
      params.set('kind', kind);
      params.set('limit', limit.toString());
      params.set('offset', searchOffset.toString());

      // Add optional filters based on artifact type
      if ((kind === 'object' || kind === 'place') && label.trim()) {
        params.set('label', label.trim());
      }
      if ((kind === 'transcript' || kind === 'ocr') && query.trim()) {
        params.set('query', query.trim());
      }
      if (filename.trim()) {
        params.set('filename', filename.trim());
      }
      if (kind === 'object' || kind === 'face' || kind === 'place') {
        params.set('min_confidence', minConfidence.toString());
      }
      if (groupByVideo) {
        params.set('group_by_video', 'true');
      }

      // Call the API - use /api prefix which nginx proxies to backend
      const response = await fetch(`${apiBaseUrl}/api/v1/artifacts/search?${params.toString()}`);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Search failed with status ${response.status}`);
      }

      const data: ArtifactSearchResponse = await response.json();
      setResults(data.results);
      setTotal(data.total);
      setOffset(searchOffset);

      // Update URL params after successful search for shareable links
      // @requirements 6.6
      updateUrlParams(searchOffset);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred';
      setError(errorMessage);
      setResults([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl, kind, label, query, filename, minConfidence, groupByVideo, limit, updateUrlParams]);

  /**
   * Handles search form submission.
   * Resets offset to 0 and triggers a new search.
   */
  const handleSearch = () => {
    setOffset(0);
    searchArtifacts(0);
  };

  /**
   * Handles pagination changes.
   * Triggers a search with the new offset.
   */
  const handlePageChange = (newOffset: number) => {
    searchArtifacts(newOffset);
  };

  // Search on initial load after URL state is loaded
  // @requirements 6.6
  useEffect(() => {
    if (urlStateLoaded) {
      searchArtifacts(offset);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlStateLoaded]);

  /**
   * Artifact types available for search.
   * Maps display names to API kind values.
   */
  const artifactTypes = [
    { value: 'object', label: 'Object Detection' },
    { value: 'face', label: 'Face Detection' },
    { value: 'transcript', label: 'Transcript' },
    { value: 'ocr', label: 'OCR Text' },
    { value: 'scene', label: 'Scene' },
    { value: 'place', label: 'Place Classification' },
  ];

  /**
   * Determines if the current artifact type uses a label input.
   * Object and place types use label filtering.
   * @requirements 6.2
   */
  const usesLabelInput = kind === 'object' || kind === 'place';

  /**
   * Determines if the current artifact type uses a query input.
   * Transcript and OCR types use text query filtering.
   * @requirements 6.2
   */
  const usesQueryInput = kind === 'transcript' || kind === 'ocr';

  /**
   * Determines if the current artifact type supports confidence filtering.
   * Object, face, and place types have confidence scores.
   * @requirements 6.3
   */
  const supportsConfidence = kind === 'object' || kind === 'face' || kind === 'place';

  /**
   * Renders the search form with artifact type selector, filters, and options.
   * @requirements 6.1, 6.2, 6.3, 6.4, 6.7
   */
  const renderSearchForm = () => {
    const inputStyle: React.CSSProperties = {
      padding: '8px 12px',
      backgroundColor: '#2a2a2a',
      color: '#fff',
      border: '1px solid #444',
      borderRadius: '4px',
      fontSize: '14px',
      outline: 'none',
    };

    const labelStyle: React.CSSProperties = {
      color: '#999',
      fontSize: '12px',
      marginBottom: '4px',
      display: 'block',
    };

    const formGroupStyle: React.CSSProperties = {
      display: 'flex',
      flexDirection: 'column',
      minWidth: '150px',
    };

    /**
     * Handle form submission (Enter key or button click).
     */
    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      handleSearch();
    };

    return (
      <form
        onSubmit={handleSubmit}
        style={{
          backgroundColor: '#1a1a1a',
          padding: '16px',
          borderRadius: '8px',
          border: '1px solid #333',
          marginBottom: '20px',
        }}
      >
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '16px',
            alignItems: 'flex-end',
          }}
        >
          {/* Artifact Type Selector - Requirement 6.1 */}
          <div style={formGroupStyle}>
            <label style={labelStyle}>Artifact Type</label>
            <select
              value={kind}
              onChange={(e) => {
                setKind(e.target.value);
                // Clear type-specific inputs when changing type
                setLabel('');
                setQuery('');
              }}
              style={{
                ...inputStyle,
                cursor: 'pointer',
                minWidth: '180px',
              }}
            >
              {artifactTypes.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          {/* Label Input for object/place types - Requirement 6.2 */}
          {usesLabelInput && (
            <div style={formGroupStyle}>
              <label style={labelStyle}>Label</label>
              <input
                type="text"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="e.g., dog, car, person"
                style={{
                  ...inputStyle,
                  minWidth: '200px',
                }}
              />
            </div>
          )}

          {/* Query Input for transcript/ocr types - Requirement 6.2 */}
          {usesQueryInput && (
            <div style={formGroupStyle}>
              <label style={labelStyle}>Query</label>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search text..."
                style={{
                  ...inputStyle,
                  minWidth: '200px',
                }}
              />
            </div>
          )}

          {/* Filename Filter - Requirement 6.4 */}
          <div style={formGroupStyle}>
            <label style={labelStyle}>Filename Filter</label>
            <input
              type="text"
              value={filename}
              onChange={(e) => setFilename(e.target.value)}
              placeholder="Filter by filename..."
              style={{
                ...inputStyle,
                minWidth: '180px',
              }}
            />
          </div>

          {/* Confidence Slider for applicable types - Requirement 6.3 */}
          {supportsConfidence && (
            <div style={formGroupStyle}>
              <label style={labelStyle}>
                Min Confidence: {minConfidence.toFixed(2)}
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={minConfidence}
                  onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
                  style={{
                    width: '120px',
                    accentColor: '#1976d2',
                  }}
                />
                <span style={{ color: '#fff', fontSize: '12px', minWidth: '32px' }}>
                  {(minConfidence * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          )}

          {/* Group by Video Toggle - Requirement 6.7 */}
          <div style={{ ...formGroupStyle, minWidth: 'auto' }}>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                cursor: 'pointer',
                color: '#fff',
                fontSize: '14px',
                padding: '8px 0',
              }}
            >
              <input
                type="checkbox"
                checked={groupByVideo}
                onChange={(e) => setGroupByVideo(e.target.checked)}
                style={{
                  width: '16px',
                  height: '16px',
                  accentColor: '#1976d2',
                  cursor: 'pointer',
                }}
              />
              Group by video
            </label>
          </div>

          {/* Search Button - Requirement 6.5 */}
          <div style={{ ...formGroupStyle, minWidth: 'auto' }}>
            <button
              type="submit"
              disabled={loading}
              style={{
                padding: '8px 24px',
                backgroundColor: loading ? '#555' : '#1976d2',
                color: '#fff',
                border: 'none',
                borderRadius: '4px',
                fontSize: '14px',
                fontWeight: 500,
                cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'background-color 0.2s',
              }}
            >
              {loading ? 'Searching...' : 'Search'}
            </button>
          </div>
        </div>
      </form>
    );
  };

  /**
   * Placeholder icons for each artifact type.
   * Shown when thumbnail fails to load (404 or error).
   * @requirements 7.2
   */
  const PlaceholderIcon: Record<string, string> = {
    'object.detection': '📦',
    'face.detection': '👤',
    'transcript.segment': '💬',
    'ocr.text': '📝',
    'scene': '🎬',
    'place.classification': '📍',
  };

  /**
   * Tracks which thumbnails have failed to load.
   * Used to show placeholder instead of broken image.
   */
  const [failedThumbnails, setFailedThumbnails] = useState<Set<string>>(new Set());

  /**
   * Handles thumbnail image load error.
   * Adds the artifact_id to failedThumbnails set to show placeholder.
   * @requirements 7.1
   */
  const handleThumbnailError = (artifactId: string) => {
    setFailedThumbnails((prev) => new Set(prev).add(artifactId));
  };

  /**
   * Renders a placeholder for failed thumbnails.
   * Shows an icon based on artifact type.
   * @requirements 7.2, 7.3
   */
  const renderPlaceholder = (artifactType: string) => {
    const icon = PlaceholderIcon[artifactType] || '🎬';
    return (
      <div
        style={{
          width: '100%',
          aspectRatio: '16/9',
          backgroundColor: '#1a1a1a',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '48px',
        }}
      >
        {icon}
      </div>
    );
  };

  /**
   * Formats a timestamp in milliseconds to MM:SS format.
   * @param ms - Timestamp in milliseconds
   * @returns Formatted string like "0:15" or "2:30"
   * @requirements 5.3
   */
  const formatTimestamp = (ms: number): string => {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  /**
   * Extracts a preview string from the artifact's preview data based on type.
   * - For object/place: shows label and confidence
   * - For transcript/ocr: shows truncated text
   * - For face: shows cluster_id or confidence
   * - For scene: shows scene type if available
   * @param result - The artifact search result
   * @returns A preview string to display on the card
   * @requirements 5.3
   */
  const getPreviewText = (result: ArtifactSearchResult): string => {
    const preview = result.preview;
    const artifactType = result.artifact_type;

    // Object detection: show label and confidence
    if (artifactType === 'object.detection') {
      const label = preview.label as string | undefined;
      const confidence = preview.confidence as number | undefined;
      if (label) {
        const confStr = confidence !== undefined ? ` (${(confidence * 100).toFixed(0)}%)` : '';
        return `${label}${confStr}`;
      }
    }

    // Place classification: show label and confidence
    if (artifactType === 'place.classification') {
      const label = preview.label as string | undefined;
      const confidence = preview.confidence as number | undefined;
      if (label) {
        const confStr = confidence !== undefined ? ` (${(confidence * 100).toFixed(0)}%)` : '';
        return `${label}${confStr}`;
      }
    }

    // Transcript segment: show truncated text
    if (artifactType === 'transcript.segment') {
      const text = preview.text as string | undefined;
      if (text) {
        const maxLength = 50;
        return text.length > maxLength ? `${text.substring(0, maxLength)}...` : text;
      }
    }

    // OCR text: show truncated text
    if (artifactType === 'ocr.text') {
      const text = preview.text as string | undefined;
      if (text) {
        const maxLength = 50;
        return text.length > maxLength ? `${text.substring(0, maxLength)}...` : text;
      }
    }

    // Face detection: show cluster_id or confidence
    if (artifactType === 'face.detection') {
      const clusterId = preview.cluster_id as string | number | undefined;
      const confidence = preview.confidence as number | undefined;
      if (clusterId !== undefined) {
        return `Face #${clusterId}`;
      }
      if (confidence !== undefined) {
        return `Face (${(confidence * 100).toFixed(0)}%)`;
      }
    }

    // Scene: show scene type if available
    if (artifactType === 'scene') {
      const sceneType = preview.scene_type as string | undefined;
      const label = preview.label as string | undefined;
      if (sceneType) {
        return sceneType;
      }
      if (label) {
        return label;
      }
    }

    // Fallback: return artifact type in a readable format
    return artifactType.replace('.', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  };

  /**
   * Renders a single thumbnail card with image, info, and optional artifact count badge.
   * Displays: thumbnail image, label/text preview, video filename, timestamp (MM:SS), artifact count badge.
   * @requirements 5.2, 5.3, 5.4, 6.8, 7.1, 7.2, 7.3
   */
  const renderThumbnailCard = (result: ArtifactSearchResult) => {
    const hasFailed = failedThumbnails.has(result.artifact_id);

    // Card styles
    const cardStyles: React.CSSProperties = {
      backgroundColor: '#2a2a2a',
      borderRadius: '8px',
      overflow: 'hidden',
      cursor: 'pointer',
      transition: 'transform 0.2s',
      position: 'relative',
    };

    // Thumbnail image styles
    const thumbnailStyles: React.CSSProperties = {
      width: '100%',
      aspectRatio: '16/9',
      objectFit: 'cover',
      backgroundColor: '#1a1a1a',
      display: 'block',
    };

    // Artifact count badge styles (for group_by_video mode)
    const badgeStyles: React.CSSProperties = {
      position: 'absolute',
      top: '8px',
      right: '8px',
      backgroundColor: 'rgba(25, 118, 210, 0.9)',
      color: '#fff',
      padding: '4px 8px',
      borderRadius: '12px',
      fontSize: '12px',
      fontWeight: 600,
    };

    // Timestamp badge styles
    const timestampBadgeStyles: React.CSSProperties = {
      position: 'absolute',
      bottom: '8px',
      left: '8px',
      backgroundColor: 'rgba(0, 0, 0, 0.7)',
      color: '#fff',
      padding: '2px 6px',
      borderRadius: '4px',
      fontSize: '11px',
      fontWeight: 500,
    };

    return (
      <div
        key={result.artifact_id}
        onClick={() => onArtifactClick?.(result)}
        style={cardStyles}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'scale(1.02)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'scale(1)';
        }}
      >
        {/* Thumbnail container with overlays */}
        <div style={{ position: 'relative' }}>
          {/* Thumbnail image or placeholder */}
          {hasFailed ? (
            renderPlaceholder(result.artifact_type)
          ) : (
            <img
              src={`${apiBaseUrl}/api${result.thumbnail_url}`}
              alt={`Thumbnail for ${result.artifact_type}`}
              style={thumbnailStyles}
              onError={() => handleThumbnailError(result.artifact_id)}
            />
          )}

          {/* Timestamp badge overlay - Requirement 5.3 */}
          <div style={timestampBadgeStyles}>{formatTimestamp(result.start_ms)}</div>

          {/* Artifact count badge (group_by_video mode) - Requirement 6.8 */}
          {result.artifact_count !== null && result.artifact_count > 1 && (
            <div style={badgeStyles}>{result.artifact_count} artifacts</div>
          )}
        </div>

        {/* Card info - Requirements 5.3, 5.4 */}
        <div style={{ padding: '12px', color: '#fff' }}>
          {/* Label/text preview - Requirement 5.3 */}
          <p
            style={{
              margin: '0 0 4px 0',
              fontSize: '14px',
              fontWeight: 500,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={getPreviewText(result)}
          >
            {getPreviewText(result)}
          </p>
          {/* Video filename - Requirement 5.3 */}
          <p
            style={{
              margin: 0,
              fontSize: '12px',
              color: '#999',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={result.video_filename}
          >
            {result.video_filename}
          </p>
        </div>
      </div>
    );
  };

  /**
   * Renders a loading spinner animation.
   * Shows a spinning circle with "Loading artifacts..." text.
   * @requirements 5.5
   */
  const renderLoadingState = () => {
    const spinnerKeyframes = `
      @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }
    `;

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
        <style>{spinnerKeyframes}</style>
        {/* Spinning loader circle */}
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
        <p
          style={{
            color: '#999',
            fontSize: '16px',
            margin: 0,
          }}
        >
          Loading artifacts...
        </p>
      </div>
    );
  };

  /**
   * Renders an empty state when no results are found.
   * Shows a search icon and helpful message with suggestions.
   * @requirements 5.6
   */
  const renderEmptyState = () => {
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
        {/* Search icon */}
        <div
          style={{
            fontSize: '64px',
            marginBottom: '16px',
            opacity: 0.5,
          }}
        >
          🔍
        </div>
        <h3
          style={{
            color: '#fff',
            fontSize: '20px',
            margin: '0 0 8px 0',
            fontWeight: 500,
          }}
        >
          No results found
        </h3>
        <p
          style={{
            color: '#999',
            fontSize: '14px',
            margin: '0 0 16px 0',
            textAlign: 'center',
            maxWidth: '400px',
          }}
        >
          Try adjusting your search criteria or filters to find what you&apos;re looking for.
        </p>
        <ul
          style={{
            color: '#666',
            fontSize: '13px',
            margin: 0,
            padding: '0 0 0 20px',
            textAlign: 'left',
          }}
        >
          <li style={{ marginBottom: '4px' }}>Try a different artifact type</li>
          <li style={{ marginBottom: '4px' }}>Use broader search terms</li>
          <li style={{ marginBottom: '4px' }}>Lower the confidence threshold</li>
          <li>Clear the filename filter</li>
        </ul>
      </div>
    );
  };

  /**
   * Renders an error state with error message and retry button.
   * Shows an error icon, the error message, and a retry button.
   */
  const renderErrorState = () => {
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
        {/* Error icon */}
        <div
          style={{
            fontSize: '64px',
            marginBottom: '16px',
          }}
        >
          ⚠️
        </div>
        <h3
          style={{
            color: '#ff6b6b',
            fontSize: '20px',
            margin: '0 0 8px 0',
            fontWeight: 500,
          }}
        >
          Something went wrong
        </h3>
        <p
          style={{
            color: '#999',
            fontSize: '14px',
            margin: '0 0 20px 0',
            textAlign: 'center',
            maxWidth: '400px',
          }}
        >
          {error}
        </p>
        <button
          onClick={handleSearch}
          style={{
            padding: '10px 24px',
            backgroundColor: '#1976d2',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            fontSize: '14px',
            fontWeight: 500,
            cursor: 'pointer',
            transition: 'background-color 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#1565c0';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = '#1976d2';
          }}
        >
          Try Again
        </button>
      </div>
    );
  };

  /**
   * Renders the thumbnail grid with responsive layout.
   * Handles loading, error, and empty states.
   * @requirements 5.2, 5.5, 5.6, 7.1, 7.2, 7.3
   */
  const renderThumbnailGrid = () => {
    if (loading) {
      return renderLoadingState();
    }

    if (error) {
      return renderErrorState();
    }

    if (results.length === 0) {
      return renderEmptyState();
    }

    // Grid layout styles - Requirement 5.2
    const gridStyles: React.CSSProperties = {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
      gap: '16px',
      padding: '16px',
    };

    return <div style={gridStyles}>{results.map(renderThumbnailCard)}</div>;
  };

  /**
   * Renders enhanced pagination controls with First/Last buttons, page numbers, and results range.
   * Features:
   * - First and Last buttons for quick navigation
   * - Page number display with clickable page numbers
   * - Results range display (e.g., "Showing 21-40 of 150")
   * - Previous/Next navigation buttons
   * @requirements 5.7
   */
  const renderPagination = () => {
    if (total === 0) return null;

    const currentPage = Math.floor(offset / limit) + 1;
    const totalPages = Math.ceil(total / limit);
    const hasPrevious = offset > 0;
    const hasNext = offset + limit < total;

    // Calculate results range for display
    const startResult = offset + 1;
    const endResult = Math.min(offset + limit, total);

    const buttonStyle: React.CSSProperties = {
      padding: '8px 16px',
      backgroundColor: '#2a2a2a',
      color: '#fff',
      border: '1px solid #444',
      borderRadius: '4px',
      cursor: 'pointer',
      fontSize: '14px',
      transition: 'background-color 0.2s',
    };

    const disabledButtonStyle: React.CSSProperties = {
      ...buttonStyle,
      backgroundColor: '#1a1a1a',
      color: '#666',
      cursor: 'not-allowed',
    };

    const pageButtonStyle: React.CSSProperties = {
      ...buttonStyle,
      padding: '8px 12px',
      minWidth: '40px',
    };

    const activePageButtonStyle: React.CSSProperties = {
      ...pageButtonStyle,
      backgroundColor: '#1976d2',
      borderColor: '#1976d2',
    };

    /**
     * Generates an array of page numbers to display.
     * Shows first page, last page, current page, and pages around current.
     * Uses ellipsis (...) for gaps.
     */
    const getPageNumbers = (): (number | string)[] => {
      const pages: (number | string)[] = [];
      const maxVisiblePages = 7; // Maximum number of page buttons to show

      if (totalPages <= maxVisiblePages) {
        // Show all pages if total is small
        for (let i = 1; i <= totalPages; i++) {
          pages.push(i);
        }
      } else {
        // Always show first page
        pages.push(1);

        // Calculate range around current page
        const startPage = Math.max(2, currentPage - 1);
        const endPage = Math.min(totalPages - 1, currentPage + 1);

        // Add ellipsis after first page if needed
        if (startPage > 2) {
          pages.push('...');
        }

        // Add pages around current page
        for (let i = startPage; i <= endPage; i++) {
          pages.push(i);
        }

        // Add ellipsis before last page if needed
        if (endPage < totalPages - 1) {
          pages.push('...');
        }

        // Always show last page
        pages.push(totalPages);
      }

      return pages;
    };

    /**
     * Handles click on a specific page number.
     * Calculates the offset and triggers a search.
     */
    const handlePageClick = (page: number) => {
      const newOffset = (page - 1) * limit;
      handlePageChange(newOffset);
    };

    return (
      <div
        style={{
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '12px',
        }}
      >
        {/* Results range display */}
        <div style={{ color: '#999', fontSize: '14px' }}>
          Showing {startResult}-{endResult} of {total} results
        </div>

        {/* Pagination controls */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: '8px',
            flexWrap: 'wrap',
          }}
        >
          {/* First button */}
          <button
            onClick={() => handlePageChange(0)}
            disabled={!hasPrevious || loading}
            style={hasPrevious && !loading ? buttonStyle : disabledButtonStyle}
            title="Go to first page"
          >
            First
          </button>

          {/* Previous button */}
          <button
            onClick={() => handlePageChange(offset - limit)}
            disabled={!hasPrevious || loading}
            style={hasPrevious && !loading ? buttonStyle : disabledButtonStyle}
            title="Go to previous page"
          >
            Previous
          </button>

          {/* Page numbers */}
          <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
            {getPageNumbers().map((page, index) => {
              if (page === '...') {
                return (
                  <span
                    key={`ellipsis-${index}`}
                    style={{ color: '#666', padding: '0 8px', fontSize: '14px' }}
                  >
                    ...
                  </span>
                );
              }

              const pageNum = page as number;
              const isCurrentPage = pageNum === currentPage;

              return (
                <button
                  key={pageNum}
                  onClick={() => handlePageClick(pageNum)}
                  disabled={loading}
                  style={
                    isCurrentPage
                      ? activePageButtonStyle
                      : loading
                        ? disabledButtonStyle
                        : pageButtonStyle
                  }
                  title={`Go to page ${pageNum}`}
                >
                  {pageNum}
                </button>
              );
            })}
          </div>

          {/* Next button */}
          <button
            onClick={() => handlePageChange(offset + limit)}
            disabled={!hasNext || loading}
            style={hasNext && !loading ? buttonStyle : disabledButtonStyle}
            title="Go to next page"
          >
            Next
          </button>

          {/* Last button */}
          <button
            onClick={() => handlePageChange((totalPages - 1) * limit)}
            disabled={!hasNext || loading}
            style={hasNext && !loading ? buttonStyle : disabledButtonStyle}
            title="Go to last page"
          >
            Last
          </button>
        </div>

        {/* Page info */}
        <div style={{ color: '#666', fontSize: '12px' }}>
          Page {currentPage} of {totalPages}
        </div>
      </div>
    );
  };

  return (
    <div
      style={{
        padding: '20px',
        backgroundColor: '#121212',
        minHeight: '100vh',
        color: '#fff',
      }}
    >
      <h2
        style={{
          color: '#fff',
          fontSize: '24px',
          fontWeight: 600,
          margin: '0 0 20px 0',
          paddingBottom: '12px',
          borderBottom: '1px solid #333',
        }}
      >
        Artifact Gallery
      </h2>
      {renderSearchForm()}
      {renderThumbnailGrid()}
      {renderPagination()}
    </div>
  );
}
