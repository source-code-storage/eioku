import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import ArtifactGallery, { ArtifactSearchResult } from './ArtifactGallery';

/**
 * Integration tests for ArtifactGallery component.
 * Tests the full search flow, navigation to player, and URL state preservation.
 *
 * @requirements 5, 6
 */

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

// Mock window.history.replaceState
const mockReplaceState = vi.fn();

// Store original location
const originalLocation = window.location;

// Sample search results for testing
const mockObjectResults: ArtifactSearchResult[] = [
  {
    video_id: 'video_001',
    artifact_id: 'artifact_001',
    artifact_type: 'object.detection',
    start_ms: 5000,
    thumbnail_url: '/v1/thumbnails/video_001/5000',
    preview: { label: 'dog', confidence: 0.95 },
    video_filename: 'vacation_2024.mp4',
    file_created_at: '2024-01-15T10:30:00Z',
    artifact_count: null,
  },
  {
    video_id: 'video_002',
    artifact_id: 'artifact_002',
    artifact_type: 'object.detection',
    start_ms: 15000,
    thumbnail_url: '/v1/thumbnails/video_002/15000',
    preview: { label: 'car', confidence: 0.88 },
    video_filename: 'road_trip.mp4',
    file_created_at: '2024-01-16T14:00:00Z',
    artifact_count: null,
  },
];

const mockTranscriptResults: ArtifactSearchResult[] = [
  {
    video_id: 'video_003',
    artifact_id: 'artifact_003',
    artifact_type: 'transcript.segment',
    start_ms: 30000,
    thumbnail_url: '/v1/thumbnails/video_003/30000',
    preview: { text: 'Hello world, this is a test transcript' },
    video_filename: 'meeting_recording.mp4',
    file_created_at: '2024-01-17T09:00:00Z',
    artifact_count: null,
  },
];

const mockGroupedResults: ArtifactSearchResult[] = [
  {
    video_id: 'video_001',
    artifact_id: 'artifact_001',
    artifact_type: 'object.detection',
    start_ms: 5000,
    thumbnail_url: '/v1/thumbnails/video_001/5000',
    preview: { label: 'dog', confidence: 0.95 },
    video_filename: 'vacation_2024.mp4',
    file_created_at: '2024-01-15T10:30:00Z',
    artifact_count: 5,
  },
];

/**
 * Helper to get the artifact type select element.
 * Uses the combobox role since it's a select element.
 */
const getArtifactTypeSelect = () => {
  return screen.getByRole('combobox');
};

/**
 * Helper to wait for loading to complete and get the Search button.
 */
const waitForSearchButton = async () => {
  await waitFor(() => {
    expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument();
  });
  return screen.getByRole('button', { name: 'Search' });
};

describe('ArtifactGallery Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock window.history
    Object.defineProperty(window, 'history', {
      value: { replaceState: mockReplaceState },
      writable: true,
    });

    // Mock window.location with default values
    delete (window as { location?: Location }).location;
    window.location = {
      ...originalLocation,
      search: '',
      pathname: '/gallery',
    } as Location;
  });

  afterEach(() => {
    // Restore original location
    window.location = originalLocation;
  });

  describe('Search Flow End-to-End', () => {
    /**
     * Tests that submitting the search form triggers an API call with correct parameters.
     * @requirements 6.5
     */
    it('submits search form and triggers API call with correct parameters', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockObjectResults,
          total: 2,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      // Wait for initial load
      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
      });

      // Verify initial API call includes default parameters
      const initialCall = mockFetch.mock.calls[0][0];
      expect(initialCall).toContain('/api/v1/artifacts/search');
      expect(initialCall).toContain('kind=object');
      expect(initialCall).toContain('limit=20');
      expect(initialCall).toContain('offset=0');
    });

    /**
     * Tests the complete search flow: form input -> API call -> results display.
     * @requirements 6.5
     */
    it('completes full search flow from form input to results display', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockObjectResults,
          total: 2,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      // Wait for initial load to complete
      await waitFor(() => {
        expect(screen.getByText('dog (95%)')).toBeInTheDocument();
      });

      // Enter a label filter
      const labelInput = screen.getByPlaceholderText('e.g., dog, car, person');
      fireEvent.change(labelInput, { target: { value: 'cat' } });

      // Clear mock to track new search
      mockFetch.mockClear();
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [
            {
              ...mockObjectResults[0],
              preview: { label: 'cat', confidence: 0.92 },
            },
          ],
          total: 1,
          limit: 20,
          offset: 0,
        }),
      });

      // Wait for Search button to be available and click it
      const searchButton = await waitForSearchButton();
      fireEvent.click(searchButton);

      // Verify API was called with label parameter
      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
        const callUrl = mockFetch.mock.calls[0][0];
        expect(callUrl).toContain('label=cat');
      });

      // Verify results are displayed
      await waitFor(() => {
        expect(screen.getByText('cat (92%)')).toBeInTheDocument();
      });
    });

    /**
     * Tests that changing artifact type updates the form and triggers correct API call.
     * @requirements 6.1, 6.2
     */
    it('changes artifact type and triggers search with correct kind parameter', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockObjectResults,
          total: 2,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      // Wait for initial load to complete
      await waitFor(() => {
        expect(screen.getByText('dog (95%)')).toBeInTheDocument();
      });

      // Change to transcript type
      const select = getArtifactTypeSelect();
      fireEvent.change(select, { target: { value: 'transcript' } });

      // Verify query input appears (transcript uses query, not label)
      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search text...')).toBeInTheDocument();
        expect(screen.queryByPlaceholderText('e.g., dog, car, person')).not.toBeInTheDocument();
      });

      // Clear mock and set up transcript response
      mockFetch.mockClear();
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockTranscriptResults,
          total: 1,
          limit: 20,
          offset: 0,
        }),
      });

      // Enter query and search
      const queryInput = screen.getByPlaceholderText('Search text...');
      fireEvent.change(queryInput, { target: { value: 'hello' } });
      
      const searchButton = await waitForSearchButton();
      fireEvent.click(searchButton);

      // Verify API call has correct kind and query
      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
        const callUrl = mockFetch.mock.calls[0][0];
        expect(callUrl).toContain('kind=transcript');
        expect(callUrl).toContain('query=hello');
      });
    });

    /**
     * Tests that filename filter is included in API call.
     * @requirements 6.4
     */
    it('includes filename filter in search API call', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockObjectResults,
          total: 2,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      // Wait for initial load to complete
      await waitFor(() => {
        expect(screen.getByText('dog (95%)')).toBeInTheDocument();
      });

      // Enter filename filter
      const filenameInput = screen.getByPlaceholderText('Filter by filename...');
      fireEvent.change(filenameInput, { target: { value: 'vacation' } });

      // Clear mock and search
      mockFetch.mockClear();
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [mockObjectResults[0]],
          total: 1,
          limit: 20,
          offset: 0,
        }),
      });

      const searchButton = await waitForSearchButton();
      fireEvent.click(searchButton);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
        const callUrl = mockFetch.mock.calls[0][0];
        expect(callUrl).toContain('filename=vacation');
      });
    });

    /**
     * Tests that group_by_video toggle is included in API call and results show artifact count.
     * @requirements 6.7, 6.8
     */
    it('includes group_by_video in API call and displays artifact count badge', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockObjectResults,
          total: 2,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      // Wait for initial load to complete
      await waitFor(() => {
        expect(screen.getByText('dog (95%)')).toBeInTheDocument();
      });

      // Enable group by video
      const checkbox = screen.getByRole('checkbox', { name: 'Group by video' });
      fireEvent.click(checkbox);

      // Clear mock and set up grouped response
      mockFetch.mockClear();
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockGroupedResults,
          total: 1,
          limit: 20,
          offset: 0,
        }),
      });

      const searchButton = await waitForSearchButton();
      fireEvent.click(searchButton);

      // Verify API call includes group_by_video
      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
        const callUrl = mockFetch.mock.calls[0][0];
        expect(callUrl).toContain('group_by_video=true');
      });

      // Verify artifact count badge is displayed
      await waitFor(() => {
        expect(screen.getByText('5 artifacts')).toBeInTheDocument();
      });
    });

    /**
     * Tests that confidence slider value is included in API call.
     * @requirements 6.3
     */
    it('includes min_confidence in API call when slider is adjusted', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockObjectResults,
          total: 2,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      // Wait for initial load to complete
      await waitFor(() => {
        expect(screen.getByText('dog (95%)')).toBeInTheDocument();
      });

      // Adjust confidence slider
      const slider = screen.getByRole('slider');
      fireEvent.change(slider, { target: { value: '0.75' } });

      // Clear mock and search
      mockFetch.mockClear();
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [mockObjectResults[0]],
          total: 1,
          limit: 20,
          offset: 0,
        }),
      });

      const searchButton = await waitForSearchButton();
      fireEvent.click(searchButton);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
        const callUrl = mockFetch.mock.calls[0][0];
        expect(callUrl).toContain('min_confidence=0.75');
      });
    });
  });

  describe('Navigation to Player', () => {
    /**
     * Tests that clicking a thumbnail card calls onArtifactClick with correct result data.
     * @requirements 5.4
     */
    it('calls onArtifactClick with correct artifact data when thumbnail is clicked', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockObjectResults,
          total: 2,
          limit: 20,
          offset: 0,
        }),
      });

      const handleArtifactClick = vi.fn();
      render(<ArtifactGallery onArtifactClick={handleArtifactClick} />);

      // Wait for results to load
      await waitFor(() => {
        expect(screen.getByText('dog (95%)')).toBeInTheDocument();
      });

      // Find and click the first thumbnail card
      const dogLabel = screen.getByText('dog (95%)');
      const card = dogLabel.closest('div[style*="cursor: pointer"]');
      expect(card).not.toBeNull();
      fireEvent.click(card!);

      // Verify callback was called with correct data
      expect(handleArtifactClick).toHaveBeenCalledTimes(1);
      expect(handleArtifactClick).toHaveBeenCalledWith(mockObjectResults[0]);

      // Verify the callback received correct video_id and start_ms for navigation
      const callArg = handleArtifactClick.mock.calls[0][0];
      expect(callArg.video_id).toBe('video_001');
      expect(callArg.start_ms).toBe(5000);
    });

    /**
     * Tests that clicking different thumbnails passes correct artifact data.
     * @requirements 5.4
     */
    it('passes correct artifact data for different thumbnails', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockObjectResults,
          total: 2,
          limit: 20,
          offset: 0,
        }),
      });

      const handleArtifactClick = vi.fn();
      render(<ArtifactGallery onArtifactClick={handleArtifactClick} />);

      // Wait for results to load
      await waitFor(() => {
        expect(screen.getByText('car (88%)')).toBeInTheDocument();
      });

      // Click the second thumbnail (car)
      const carLabel = screen.getByText('car (88%)');
      const card = carLabel.closest('div[style*="cursor: pointer"]');
      fireEvent.click(card!);

      // Verify callback received second artifact's data
      expect(handleArtifactClick).toHaveBeenCalledWith(mockObjectResults[1]);
      const callArg = handleArtifactClick.mock.calls[0][0];
      expect(callArg.video_id).toBe('video_002');
      expect(callArg.start_ms).toBe(15000);
    });

    /**
     * Tests that thumbnail URL is correctly constructed for navigation context.
     * @requirements 5.4
     */
    it('provides thumbnail_url in artifact data for player context', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockObjectResults,
          total: 2,
          limit: 20,
          offset: 0,
        }),
      });

      const handleArtifactClick = vi.fn();
      render(<ArtifactGallery onArtifactClick={handleArtifactClick} />);

      await waitFor(() => {
        expect(screen.getByText('dog (95%)')).toBeInTheDocument();
      });

      const dogLabel = screen.getByText('dog (95%)');
      const card = dogLabel.closest('div[style*="cursor: pointer"]');
      fireEvent.click(card!);

      const callArg = handleArtifactClick.mock.calls[0][0];
      expect(callArg.thumbnail_url).toBe('/v1/thumbnails/video_001/5000');
    });
  });

  describe('URL State Preservation', () => {
    /**
     * Tests that search parameters are preserved in URL after search.
     * @requirements 6.6
     */
    it('updates URL with search parameters after search', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockObjectResults,
          total: 2,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByText('dog (95%)')).toBeInTheDocument();
      });

      // Verify URL was updated with search params
      expect(mockReplaceState).toHaveBeenCalled();
      const lastCall = mockReplaceState.mock.calls[mockReplaceState.mock.calls.length - 1];
      const urlString = lastCall[2];
      expect(urlString).toContain('kind=object');
    });

    /**
     * Tests that label filter is preserved in URL.
     * @requirements 6.6
     */
    it('preserves label filter in URL', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockObjectResults,
          total: 2,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      // Wait for initial load to complete
      await waitFor(() => {
        expect(screen.getByText('dog (95%)')).toBeInTheDocument();
      });

      // Enter label and search
      const labelInput = screen.getByPlaceholderText('e.g., dog, car, person');
      fireEvent.change(labelInput, { target: { value: 'dog' } });

      mockReplaceState.mockClear();
      const searchButton = await waitForSearchButton();
      fireEvent.click(searchButton);

      await waitFor(() => {
        expect(mockReplaceState).toHaveBeenCalled();
        const lastCall = mockReplaceState.mock.calls[mockReplaceState.mock.calls.length - 1];
        const urlString = lastCall[2];
        expect(urlString).toContain('label=dog');
      });
    });

    /**
     * Tests that URL state is read on component mount.
     * @requirements 6.6
     */
    it('reads initial state from URL on mount', async () => {
      // Set up URL with search params
      delete (window as { location?: Location }).location;
      window.location = {
        ...originalLocation,
        search: '?kind=transcript&query=hello&min_confidence=0.8',
        pathname: '/gallery',
      } as Location;

      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockTranscriptResults,
          total: 1,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      // Wait for component to load and verify it read URL params
      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
        const callUrl = mockFetch.mock.calls[0][0];
        expect(callUrl).toContain('kind=transcript');
        expect(callUrl).toContain('query=hello');
      });

      // Verify form state reflects URL params - use combobox role for select
      await waitFor(() => {
        const select = getArtifactTypeSelect();
        expect(select).toHaveValue('transcript');
      });
    });

    /**
     * Tests that group_by_video state is preserved in URL.
     * @requirements 6.6
     */
    it('preserves group_by_video state in URL', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockObjectResults,
          total: 2,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      // Wait for initial load to complete
      await waitFor(() => {
        expect(screen.getByText('dog (95%)')).toBeInTheDocument();
      });

      // Enable group by video
      const checkbox = screen.getByRole('checkbox', { name: 'Group by video' });
      fireEvent.click(checkbox);

      mockReplaceState.mockClear();
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockGroupedResults,
          total: 1,
          limit: 20,
          offset: 0,
        }),
      });

      const searchButton = await waitForSearchButton();
      fireEvent.click(searchButton);

      await waitFor(() => {
        expect(mockReplaceState).toHaveBeenCalled();
        const lastCall = mockReplaceState.mock.calls[mockReplaceState.mock.calls.length - 1];
        const urlString = lastCall[2];
        expect(urlString).toContain('group_by_video=true');
      });
    });

    /**
     * Tests that pagination offset is preserved in URL.
     * @requirements 6.6
     */
    it('preserves pagination offset in URL', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockObjectResults,
          total: 100,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument();
      });

      // Click next page
      mockReplaceState.mockClear();
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockObjectResults,
          total: 100,
          limit: 20,
          offset: 20,
        }),
      });

      fireEvent.click(screen.getByRole('button', { name: 'Next' }));

      await waitFor(() => {
        expect(mockReplaceState).toHaveBeenCalled();
        const lastCall = mockReplaceState.mock.calls[mockReplaceState.mock.calls.length - 1];
        const urlString = lastCall[2];
        expect(urlString).toContain('offset=20');
      });
    });

    /**
     * Tests that filename filter is preserved in URL.
     * @requirements 6.6
     */
    it('preserves filename filter in URL', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockObjectResults,
          total: 2,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      // Wait for initial load to complete
      await waitFor(() => {
        expect(screen.getByText('dog (95%)')).toBeInTheDocument();
      });

      // Enter filename filter
      const filenameInput = screen.getByPlaceholderText('Filter by filename...');
      fireEvent.change(filenameInput, { target: { value: 'vacation' } });

      mockReplaceState.mockClear();
      const searchButton = await waitForSearchButton();
      fireEvent.click(searchButton);

      await waitFor(() => {
        expect(mockReplaceState).toHaveBeenCalled();
        const lastCall = mockReplaceState.mock.calls[mockReplaceState.mock.calls.length - 1];
        const urlString = lastCall[2];
        expect(urlString).toContain('filename=vacation');
      });
    });

    /**
     * Tests that URL is shareable - loading from URL produces same results.
     * @requirements 6.6
     */
    it('produces shareable URLs that restore search state', async () => {
      // Set up URL with complete search state
      delete (window as { location?: Location }).location;
      window.location = {
        ...originalLocation,
        search: '?kind=object&label=dog&min_confidence=0.8&filename=vacation&group_by_video=true',
        pathname: '/gallery',
      } as Location;

      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: mockGroupedResults,
          total: 1,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      // Verify API call includes all URL params
      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
        const callUrl = mockFetch.mock.calls[0][0];
        expect(callUrl).toContain('kind=object');
        expect(callUrl).toContain('label=dog');
        expect(callUrl).toContain('min_confidence=0.8');
        expect(callUrl).toContain('filename=vacation');
        expect(callUrl).toContain('group_by_video=true');
      });

      // Verify form state matches URL - use appropriate selectors
      await waitFor(() => {
        expect(getArtifactTypeSelect()).toHaveValue('object');
        expect(screen.getByPlaceholderText('e.g., dog, car, person')).toHaveValue('dog');
        expect(screen.getByPlaceholderText('Filter by filename...')).toHaveValue('vacation');
        expect(screen.getByRole('checkbox', { name: 'Group by video' })).toBeChecked();
      });
    });
  });
});
