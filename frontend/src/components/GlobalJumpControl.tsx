import React, { useState } from 'react';

/**
 * Artifact types supported by the global jump API.
 * Each type has different input requirements and filtering options.
 */
export type ArtifactType = 'object' | 'face' | 'transcript' | 'ocr' | 'scene' | 'place' | 'location';

/**
 * Result from the global jump API for a single match.
 */
export interface GlobalJumpResult {
  video_id: string;
  video_filename: string;
  file_created_at: string;
  jump_to: {
    start_ms: number;
    end_ms: number;
  };
  artifact_id: string;
  preview: Record<string, unknown>;
}

/**
 * Response from the global jump API.
 */
export interface GlobalJumpResponse {
  results: GlobalJumpResult[];
  has_more: boolean;
}

/**
 * Props for the GlobalJumpControl component.
 * 
 * The component can operate in two modes:
 * 1. Search Page Mode: videoId is undefined, searches from beginning of global timeline
 * 2. Player Page Mode: videoId is provided, searches from current video position
 */
export interface GlobalJumpControlProps {
  /** Current video context (optional - null when on search page) */
  videoId?: string;
  
  /** Reference to the video element for seeking (optional) */
  videoRef?: React.RefObject<HTMLVideoElement>;
  
  /** API base URL (defaults to http://localhost:8080) */
  apiUrl?: string;
  
  /** 
   * Callback when navigation requires changing to a different video.
   * Called with the new video_id and target timestamp in milliseconds.
   * Should return a Promise that resolves when the video is loaded.
   */
  onVideoChange?: (videoId: string, timestampMs: number) => Promise<void>;
  
  /**
   * Callback when navigation occurs (for search page to navigate to player).
   * Called with the video_id, timestamp, and current form state.
   */
  onNavigate?: (videoId: string, timestampMs: number, formState: {
    artifactType: ArtifactType;
    label: string;
    query: string;
    confidence: number;
  }) => void;
  
  /** Initial artifact type (for preserving form state across page navigation) */
  initialArtifactType?: ArtifactType;
  
  /** Initial label value (for preserving form state across page navigation) */
  initialLabel?: string;
  
  /** Initial query value (for preserving form state across page navigation) */
  initialQuery?: string;
  
  /** Initial confidence threshold (for preserving form state across page navigation) */
  initialConfidence?: number;
}

/**
 * Configuration for each artifact type defining UI behavior.
 */
interface ArtifactConfig {
  label: string;
  hasLabelInput: boolean;
  hasQueryInput: boolean;
  hasConfidence: boolean;
  placeholder?: string;
}

/**
 * Configuration map for all artifact types.
 * Defines which input fields and controls are shown for each type.
 */
const ARTIFACT_CONFIG: Record<ArtifactType, ArtifactConfig> = {
  object: {
    label: 'Objects',
    hasLabelInput: true,
    hasQueryInput: false,
    hasConfidence: true,
    placeholder: 'e.g., dog, car, person',
  },
  face: {
    label: 'Faces',
    hasLabelInput: false,
    hasQueryInput: false,
    hasConfidence: true,
  },
  transcript: {
    label: 'Transcript',
    hasLabelInput: false,
    hasQueryInput: true,
    hasConfidence: false,
    placeholder: 'Search spoken words...',
  },
  ocr: {
    label: 'OCR Text',
    hasLabelInput: false,
    hasQueryInput: true,
    hasConfidence: false,
    placeholder: 'Search on-screen text...',
  },
  scene: {
    label: 'Scenes',
    hasLabelInput: false,
    hasQueryInput: false,
    hasConfidence: false,
  },
  place: {
    label: 'Places',
    hasLabelInput: true,
    hasQueryInput: false,
    hasConfidence: true,
    placeholder: 'e.g., kitchen, beach, office',
  },
  location: {
    label: 'Location',
    hasLabelInput: false,
    hasQueryInput: true,
    hasConfidence: false,
    placeholder: 'e.g., Tokyo, Japan, California',
  },
};

/**
 * GlobalJumpControl - Cross-video artifact search and navigation component.
 * 
 * This component enables searching for artifacts across all videos in the library
 * using the global jump API (/api/v1/jump/global). It supports:
 * - All artifact types: object, face, transcript, ocr, scene, place, location
 * - Cross-video navigation with video change callbacks
 * - Same-video seeking
 * - Form state preservation across page navigation
 * 
 * Requirements: 1.1, 1.2, 1.3, 1.4
 */
export default function GlobalJumpControl({
  videoId,
  videoRef,
  apiUrl = 'http://localhost:8080',
  onVideoChange,
  onNavigate,
  initialArtifactType = 'object',
  initialLabel = '',
  initialQuery = '',
  initialConfidence = 0,
}: GlobalJumpControlProps) {
  // Form state - preserved across navigation
  const [artifactType, setArtifactType] = useState<ArtifactType>(initialArtifactType);
  const [label, setLabel] = useState<string>(initialLabel);
  const [query, setQuery] = useState<string>(initialQuery);
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(initialConfidence);
  
  // Face cluster ID for face searches (separate from label/query)
  const [faceClusterId, setFaceClusterId] = useState<string>('');
  
  // Loading and result state
  const [loading, setLoading] = useState<boolean>(false);
  const [currentMatch, setCurrentMatch] = useState<string>('');
  const [lastResult, setLastResult] = useState<GlobalJumpResult | null>(null);
  
  // Error state
  const [error, setError] = useState<string | null>(null);
  
  // Export clip loading state
  const [exporting, setExporting] = useState<boolean>(false);
  
  // Clip export timestamp inputs (user-editable, in MM:SS format)
  const [clipStartTime, setClipStartTime] = useState<string>('0:00');
  const [clipEndTime, setClipEndTime] = useState<string>('0:00');

  // Get the configuration for the current artifact type
  const config = ARTIFACT_CONFIG[artifactType];

  /**
   * Format milliseconds as MM:SS for display.
   */
  const formatTime = (ms: number): string => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  /**
   * Parse MM:SS or M:SS format to milliseconds.
   * Returns null if invalid format.
   */
  const parseTime = (timeStr: string): number | null => {
    const match = timeStr.match(/^(\d+):(\d{1,2})$/);
    if (!match) return null;
    const minutes = parseInt(match[1], 10);
    const seconds = parseInt(match[2], 10);
    if (seconds >= 60) return null;
    return (minutes * 60 + seconds) * 1000;
  };

  /**
   * Update clip timestamps when a new result is received.
   */
  const updateClipTimestamps = (result: GlobalJumpResult) => {
    setClipStartTime(formatTime(result.jump_to.start_ms));
    setClipEndTime(formatTime(result.jump_to.end_ms));
  };

  /**
   * Handle artifact type change - resets type-specific fields.
   */
  const handleArtifactTypeChange = (newType: ArtifactType) => {
    setArtifactType(newType);
    // Reset type-specific fields when changing type
    setLabel('');
    setQuery('');
    setFaceClusterId('');
    setError(null);
  };

  /**
   * Execute a jump navigation request.
   * TODO: Task 7 - Implement full API call logic
   */
  const jump = async (direction: 'next' | 'prev') => {
    setLoading(true);
    setError(null);
    
    try {
      // Get current position
      const fromVideoId = videoId;
      const fromMs = videoRef?.current 
        ? Math.floor(videoRef.current.currentTime * 1000) 
        : 0;

      // Build API URL - using global jump endpoint
      const params = new URLSearchParams({
        kind: artifactType,
        direction,
        ...(fromVideoId && { from_video_id: fromVideoId }),
        from_ms: fromMs.toString(),
      });

      // Add type-specific parameters
      if (config.hasLabelInput && label) {
        params.set('label', label);
      }
      if (config.hasQueryInput && query) {
        params.set('query', query);
      }
      if (artifactType === 'face' && faceClusterId) {
        params.set('face_cluster_id', faceClusterId);
      }
      if (config.hasConfidence && confidenceThreshold > 0) {
        params.set('min_confidence', confidenceThreshold.toString());
      }

      const response = await fetch(`${apiUrl}/api/v1/jump/global?${params}`);
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data: GlobalJumpResponse = await response.json();

      if (data.results.length === 0) {
        const message = direction === 'next' 
          ? 'No more results - reached end of library'
          : 'No more results - reached beginning of library';
        setCurrentMatch(message);
        setLastResult(null);
        setError(message);
        return;
      }

      const result = data.results[0];
      setLastResult(result);
      setCurrentMatch(`${result.video_filename} @ ${formatTime(result.jump_to.start_ms)}`);
      updateClipTimestamps(result);

      // Handle navigation based on whether video changes
      if (result.video_id !== videoId) {
        // Cross-video navigation
        if (onVideoChange) {
          await onVideoChange(result.video_id, result.jump_to.start_ms);
        } else if (onNavigate) {
          onNavigate(result.video_id, result.jump_to.start_ms, {
            artifactType,
            label,
            query,
            confidence: confidenceThreshold,
          });
        } else {
          console.warn('GlobalJumpControl: Cross-video navigation attempted but no callback provided');
        }
      } else {
        // Same-video navigation - seek directly
        if (videoRef?.current) {
          videoRef.current.currentTime = result.jump_to.start_ms / 1000;
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      setCurrentMatch(`Error: ${message}`);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Export a video clip containing the current search result.
   * Uses user-editable start/end timestamps in MM:SS format.
   * Requirements: 11.1, 11.2, 11.3, 11.8
   */
  const exportClip = async () => {
    // Parse user-entered timestamps
    const startMs = parseTime(clipStartTime);
    const endMs = parseTime(clipEndTime);
    
    if (startMs === null || endMs === null) {
      setError('Invalid timestamp format. Use MM:SS (e.g., 1:30)');
      return;
    }
    
    if (endMs <= startMs) {
      setError('End time must be after start time');
      return;
    }
    
    // Use the video ID from the last result if available, otherwise use current videoId
    const targetVideoId = lastResult?.video_id || videoId;
    
    if (!targetVideoId) {
      setError('No video selected');
      return;
    }
    
    setExporting(true);
    setError(null);
    
    try {
      const buffer_ms = 2000; // 2 second buffer
      
      const params = new URLSearchParams({
        start_ms: startMs.toString(),
        end_ms: endMs.toString(),
        buffer_ms: buffer_ms.toString(),
      });
      
      const response = await fetch(
        `${apiUrl}/api/v1/videos/${targetVideoId}/clip?${params}`
      );
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to export clip: ${errorText}`);
      }
      
      // Get filename from Content-Disposition header
      const disposition = response.headers.get('Content-Disposition');
      const filenameMatch = disposition?.match(/filename="(.+)"/);
      const filename = filenameMatch?.[1] || 'clip.mp4';
      
      // Download the blob
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Export failed';
      setError(message);
      console.error('Export failed:', err);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div
      style={{
        backgroundColor: '#1a1a1a',
        borderTop: '1px solid #333',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}
    >
      {/* Artifact type selector */}
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <span style={{ color: '#999', fontSize: '12px', minWidth: '60px' }}>Jump to:</span>
        <select
          value={artifactType}
          onChange={(e) => handleArtifactTypeChange(e.target.value as ArtifactType)}
          style={{
            padding: '6px 10px',
            backgroundColor: '#2a2a2a',
            color: '#fff',
            border: '1px solid #444',
            borderRadius: '4px',
            fontSize: '12px',
            cursor: 'pointer',
          }}
        >
          {(Object.keys(ARTIFACT_CONFIG) as ArtifactType[]).map((type) => (
            <option key={type} value={type}>
              {ARTIFACT_CONFIG[type].label}
            </option>
          ))}
        </select>
      </div>

      {/* Label input (for object/place) */}
      {config.hasLabelInput && (
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ color: '#999', fontSize: '12px', minWidth: '60px' }}>Label:</span>
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !loading) {
                e.preventDefault();
                jump('next');
              }
            }}
            placeholder={config.placeholder}
            style={{
              flex: 1,
              padding: '6px 10px',
              backgroundColor: '#2a2a2a',
              color: '#fff',
              border: '1px solid #444',
              borderRadius: '4px',
              fontSize: '12px',
            }}
          />
        </div>
      )}

      {/* Query input (for transcript/ocr/location) */}
      {config.hasQueryInput && (
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ color: '#999', fontSize: '12px', minWidth: '60px' }}>Search:</span>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !loading) {
                e.preventDefault();
                jump('next');
              }
            }}
            placeholder={config.placeholder}
            style={{
              flex: 1,
              padding: '6px 10px',
              backgroundColor: '#2a2a2a',
              color: '#fff',
              border: '1px solid #444',
              borderRadius: '4px',
              fontSize: '12px',
            }}
          />
        </div>
      )}

      {/* Face cluster selector (for face) */}
      {artifactType === 'face' && (
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ color: '#999', fontSize: '12px', minWidth: '60px' }}>Face ID:</span>
          <input
            type="text"
            value={faceClusterId}
            onChange={(e) => setFaceClusterId(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !loading) {
                e.preventDefault();
                jump('next');
              }
            }}
            placeholder="Face cluster ID..."
            style={{
              flex: 1,
              padding: '6px 10px',
              backgroundColor: '#2a2a2a',
              color: '#fff',
              border: '1px solid #444',
              borderRadius: '4px',
              fontSize: '12px',
            }}
          />
        </div>
      )}

      {/* Confidence threshold slider (for object/face/place) */}
      {config.hasConfidence && (
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ color: '#999', fontSize: '12px', minWidth: '60px' }}>Confidence:</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={confidenceThreshold}
            onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
            style={{ flex: 1, maxWidth: '200px' }}
          />
          <span style={{ color: '#999', fontSize: '12px', minWidth: '40px' }}>
            {(confidenceThreshold * 100).toFixed(0)}%
          </span>
        </div>
      )}

      {/* Navigation buttons */}
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <button
          onClick={() => jump('prev')}
          disabled={loading}
          style={{
            padding: '8px 16px',
            backgroundColor: '#2a2a2a',
            color: '#fff',
            border: '1px solid #444',
            borderRadius: '4px',
            fontSize: '12px',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.5 : 1,
          }}
        >
          ← Previous
        </button>

        <button
          onClick={() => jump('next')}
          disabled={loading}
          style={{
            padding: '8px 16px',
            backgroundColor: '#2a2a2a',
            color: '#fff',
            border: '1px solid #444',
            borderRadius: '4px',
            fontSize: '12px',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.5 : 1,
          }}
        >
          Next →
        </button>

        {/* Export Clip section - shown when viewing any video */}
        {videoId && (
          <>
            <button
              onClick={() => {
                if (videoRef?.current) {
                  setClipStartTime(formatTime(Math.floor(videoRef.current.currentTime * 1000)));
                }
              }}
              title="Set start to current time"
              style={{
                padding: '6px 8px',
                backgroundColor: '#2a2a2a',
                color: '#fff',
                border: '1px solid #444',
                borderRadius: '4px',
                fontSize: '10px',
                cursor: 'pointer',
              }}
            >
              ⏱️
            </button>
            <input
              type="text"
              value={clipStartTime}
              onChange={(e) => setClipStartTime(e.target.value)}
              placeholder="0:00"
              title="Start time (MM:SS)"
              style={{
                width: '50px',
                padding: '6px 8px',
                backgroundColor: '#2a2a2a',
                color: '#fff',
                border: '1px solid #444',
                borderRadius: '4px',
                fontSize: '12px',
                textAlign: 'center',
              }}
            />
            <span style={{ color: '#666', fontSize: '12px' }}>→</span>
            <input
              type="text"
              value={clipEndTime}
              onChange={(e) => setClipEndTime(e.target.value)}
              placeholder="0:00"
              title="End time (MM:SS)"
              style={{
                width: '50px',
                padding: '6px 8px',
                backgroundColor: '#2a2a2a',
                color: '#fff',
                border: '1px solid #444',
                borderRadius: '4px',
                fontSize: '12px',
                textAlign: 'center',
              }}
            />
            <button
              onClick={() => {
                if (videoRef?.current) {
                  setClipEndTime(formatTime(Math.floor(videoRef.current.currentTime * 1000)));
                }
              }}
              title="Set end to current time"
              style={{
                padding: '6px 8px',
                backgroundColor: '#2a2a2a',
                color: '#fff',
                border: '1px solid #444',
                borderRadius: '4px',
                fontSize: '10px',
                cursor: 'pointer',
              }}
            >
              ⏱️
            </button>
            <button
              onClick={exportClip}
              disabled={exporting || loading}
              style={{
                padding: '8px 16px',
                backgroundColor: '#2a5a2a',
                color: '#fff',
                border: '1px solid #3a7a3a',
                borderRadius: '4px',
                fontSize: '12px',
                cursor: exporting || loading ? 'not-allowed' : 'pointer',
                opacity: exporting || loading ? 0.5 : 1,
              }}
            >
              {exporting ? 'Exporting...' : '📥 Export Clip'}
            </button>
          </>
        )}

        {/* Loading indicator */}
        {loading && (
          <span style={{ color: '#999', fontSize: '12px' }}>Loading...</span>
        )}

        {/* Current match display */}
        {currentMatch && !loading && (
          <span style={{ color: '#999', fontSize: '12px', marginLeft: 'auto' }}>
            {lastResult && lastResult.video_id !== videoId && (
              <span style={{ color: '#4caf50', marginRight: '4px' }}>↗</span>
            )}
            {currentMatch}
          </span>
        )}
      </div>

      {/* Error display */}
      {error && (
        <div style={{ color: '#f44336', fontSize: '12px' }}>
          {error}
        </div>
      )}
    </div>
  );
}
