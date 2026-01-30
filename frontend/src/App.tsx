import { useState } from 'react';
import VideoGallery from './components/VideoGallery';
import VideoPlayer from './components/VideoPlayer';
import SearchPage, { SearchNavigationState } from './pages/SearchPage';

/**
 * State passed from search page to player page.
 * Contains form state for preservation and initial timestamp.
 */
interface PlayerNavigationState {
  fromSearch: boolean;
  formState: SearchNavigationState;
  initialTimestampMs: number;
}

function App() {
  const [view, setView] = useState<'gallery' | 'player' | 'search'>('gallery');
  const [selectedVideoId, setSelectedVideoId] = useState('');
  const [playerNavState, setPlayerNavState] = useState<PlayerNavigationState | null>(null);

  const handleSelectVideo = (videoId: string) => {
    setSelectedVideoId(videoId);
    setPlayerNavState(null); // Clear any previous search state
    setView('player');
  };

  const handleBack = () => {
    setSelectedVideoId('');
    setPlayerNavState(null);
    setView('gallery');
  };

  const handleGoToSearch = () => {
    setView('search');
  };

  /**
   * Handle navigation from search page to player page.
   * Passes form state to player page for preservation (Requirement 1.1.5).
   * Navigates to player page with video loaded at correct timestamp (Requirement 1.1.4).
   */
  const handleNavigateToVideo = (
    videoId: string,
    timestampMs: number,
    formState: SearchNavigationState
  ) => {
    setSelectedVideoId(videoId);
    setPlayerNavState({
      fromSearch: true,
      formState,
      initialTimestampMs: timestampMs,
    });
    setView('player');
  };

  // Render search page
  if (view === 'search') {
    return (
      <SearchPage
        onNavigateToVideo={handleNavigateToVideo}
        onBack={handleBack}
        initialState={playerNavState?.formState}
      />
    );
  }

  // Render player page
  if (view === 'player' && selectedVideoId) {
    return (
      <VideoPlayer
        videoId={selectedVideoId}
        onBack={handleBack}
        initialTimestampMs={playerNavState?.initialTimestampMs}
        initialArtifactType={playerNavState?.formState?.artifactType}
        initialLabel={playerNavState?.formState?.label}
        initialQuery={playerNavState?.formState?.query}
        initialConfidence={playerNavState?.formState?.confidence}
        onVideoChange={(newVideoId, timestampMs) => {
          // Handle cross-video navigation by updating selected video
          setSelectedVideoId(newVideoId);
          setPlayerNavState(prev => prev ? {
            ...prev,
            initialTimestampMs: timestampMs,
          } : {
            fromSearch: false,
            formState: { 
              artifactType: 'object', 
              label: '', 
              query: '', 
              confidence: 0,
              timestampMs: timestampMs,
            },
            initialTimestampMs: timestampMs,
          });
        }}
      />
    );
  }

  // Render gallery (default view)
  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#fff' }}>
      <div style={{ padding: '20px', borderBottom: '1px solid #eee', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ margin: '0 0 5px 0', fontSize: '28px' }}>Eioku</h1>
          <p style={{ margin: '0', color: '#666', fontSize: '14px' }}>Semantic Video Search Platform</p>
        </div>
        <button
          onClick={handleGoToSearch}
          style={{
            padding: '10px 20px',
            backgroundColor: '#1976d2',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: '500',
          }}
        >
          🔍 Global Search
        </button>
      </div>
      <VideoGallery onSelectVideo={handleSelectVideo} />
    </div>
  );
}

export default App;
