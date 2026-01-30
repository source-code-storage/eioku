import ArtifactGallery, { ArtifactSearchResult } from '../components/ArtifactGallery';

/**
 * Props for the GalleryPage component.
 */
interface GalleryPageProps {
  /**
   * Callback when user clicks on an artifact to navigate to the video player.
   * Called with the video_id and timestamp in milliseconds.
   */
  onNavigateToVideo: (videoId: string, timestampMs: number) => void;

  /** Callback to go back to the main gallery */
  onBack: () => void;
}

/**
 * GalleryPage - Dedicated page for browsing artifacts as a visual thumbnail gallery.
 *
 * This page renders the ArtifactGallery component which displays search results
 * as a thumbnail grid. When a user clicks on an artifact thumbnail, it navigates
 * to the video player at that artifact's timestamp.
 *
 * @requirements 5.4
 */
export default function GalleryPage({
  onNavigateToVideo,
  onBack,
}: GalleryPageProps) {
  /**
   * Handle artifact click navigation to player.
   * Extracts video_id and start_ms from the artifact result and navigates to the player.
   * @requirements 5.4
   */
  const handleArtifactClick = (result: ArtifactSearchResult) => {
    onNavigateToVideo(result.video_id, result.start_ms);
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
            Artifact Gallery
          </h2>
        </div>
      </div>

      {/* Main content - ArtifactGallery component */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          padding: '20px',
        }}
      >
        <ArtifactGallery
          onArtifactClick={handleArtifactClick}
        />
      </div>
    </div>
  );
}
