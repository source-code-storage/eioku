import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import ArtifactGallery, { ArtifactSearchResult } from './ArtifactGallery';

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

// Mock window.history.replaceState
const mockReplaceState = vi.fn();
Object.defineProperty(window, 'history', {
  value: {
    replaceState: mockReplaceState,
  },
  writable: true,
});

// Mock window.location
const mockLocation = {
  search: '',
  pathname: '/gallery',
};
Object.defineProperty(window, 'location', {
  value: mockLocation,
  writable: true,
});

// Sample search results for testing
const mockSearchResults: ArtifactSearchResult[] = [
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

const mockSearchResponse = {
  results: mockSearchResults,
  total: 2,
  limit: 20,
  offset: 0,
};

/**
 * Helper to get the artifact type select element.
 * Uses the combobox role since it's a select element.
 */
const getArtifactTypeSelect = () => {
  return screen.getByRole('combobox');
};

describe('ArtifactGallery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLocation.search = '';
  });

  describe('Search Form Rendering', () => {
    it('renders artifact type selector', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(getArtifactTypeSelect()).toBeInTheDocument();
      });

      // Check all artifact type options are present
      const select = getArtifactTypeSelect();
      expect(select).toHaveValue('object');
      
      // Verify options exist
      expect(screen.getByRole('option', { name: 'Object Detection' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Face Detection' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Transcript' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'OCR Text' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Scene' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Place Classification' })).toBeInTheDocument();
    });

    it('renders label input for object type', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('e.g., dog, car, person')).toBeInTheDocument();
      });

      const labelInput = screen.getByPlaceholderText('e.g., dog, car, person');
      expect(labelInput).toBeInTheDocument();
    });

    it('renders query input for transcript type', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(getArtifactTypeSelect()).toBeInTheDocument();
      });

      // Change to transcript type
      const select = getArtifactTypeSelect();
      fireEvent.change(select, { target: { value: 'transcript' } });

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search text...')).toBeInTheDocument();
      });

      const queryInput = screen.getByPlaceholderText('Search text...');
      expect(queryInput).toBeInTheDocument();
    });

    it('renders confidence slider for applicable types', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByText(/Min Confidence:/)).toBeInTheDocument();
      });

      const slider = screen.getByRole('slider');
      expect(slider).toBeInTheDocument();
      expect(slider).toHaveValue('0.5');
    });

    it('hides confidence slider for transcript type', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(getArtifactTypeSelect()).toBeInTheDocument();
      });

      // Change to transcript type
      const select = getArtifactTypeSelect();
      fireEvent.change(select, { target: { value: 'transcript' } });

      await waitFor(() => {
        expect(screen.queryByText(/Min Confidence:/)).not.toBeInTheDocument();
      });
    });

    it('renders group by video toggle', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByRole('checkbox', { name: 'Group by video' })).toBeInTheDocument();
      });

      const checkbox = screen.getByRole('checkbox', { name: 'Group by video' });
      expect(checkbox).toBeInTheDocument();
      expect(checkbox).not.toBeChecked();
    });

    it('renders filename filter input', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Filter by filename...')).toBeInTheDocument();
      });

      const filenameInput = screen.getByPlaceholderText('Filter by filename...');
      expect(filenameInput).toBeInTheDocument();
    });

    it('renders search button', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument();
      });
    });
  });

  describe('Grid Layout', () => {
    it('renders thumbnail grid with results', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        // Check that thumbnail cards are rendered
        expect(screen.getByText('dog (95%)')).toBeInTheDocument();
        expect(screen.getByText('car (88%)')).toBeInTheDocument();
      });
    });

    it('renders correct number of thumbnail cards', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        const images = screen.getAllByRole('img');
        expect(images).toHaveLength(2);
      });
    });
  });

  describe('Thumbnail Card Rendering', () => {
    it('displays thumbnail image with correct src', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        const images = screen.getAllByRole('img');
        // apiBaseUrl defaults to '' so URL is /api/v1/thumbnails/...
        expect(images[0]).toHaveAttribute(
          'src',
          '/api/v1/thumbnails/video_001/5000'
        );
      });
    });

    it('displays artifact label and confidence', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByText('dog (95%)')).toBeInTheDocument();
        expect(screen.getByText('car (88%)')).toBeInTheDocument();
      });
    });

    it('displays video filename', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByText('vacation_2024.mp4')).toBeInTheDocument();
        expect(screen.getByText('road_trip.mp4')).toBeInTheDocument();
      });
    });

    it('displays timestamp in MM:SS format', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        // 5000ms = 0:05, 15000ms = 0:15
        expect(screen.getByText('0:05')).toBeInTheDocument();
        expect(screen.getByText('0:15')).toBeInTheDocument();
      });
    });

    it('displays artifact count badge when grouped', async () => {
      const groupedResults = [
        {
          ...mockSearchResults[0],
          artifact_count: 5,
        },
      ];

      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: groupedResults,
          total: 1,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByText('5 artifacts')).toBeInTheDocument();
      });
    });

    it('calls onArtifactClick when thumbnail is clicked', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      const handleClick = vi.fn();
      render(<ArtifactGallery onArtifactClick={handleClick} />);

      await waitFor(() => {
        expect(screen.getByText('dog (95%)')).toBeInTheDocument();
      });

      // Click on the first card (find by the label text and click its parent card)
      const dogLabel = screen.getByText('dog (95%)');
      const card = dogLabel.closest('div[style*="cursor: pointer"]');
      if (card) {
        fireEvent.click(card);
      }

      expect(handleClick).toHaveBeenCalledWith(mockSearchResults[0]);
    });
  });

  describe('Placeholder on Image Error', () => {
    it('shows placeholder when thumbnail fails to load', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        const images = screen.getAllByRole('img');
        expect(images.length).toBeGreaterThan(0);
      });

      // Simulate image error
      const images = screen.getAllByRole('img');
      fireEvent.error(images[0]);

      await waitFor(() => {
        // Object detection placeholder is 📦
        expect(screen.getByText('📦')).toBeInTheDocument();
      });
    });

    it('shows correct placeholder icon for face detection', async () => {
      const faceResults = [
        {
          ...mockSearchResults[0],
          artifact_type: 'face.detection',
          preview: { confidence: 0.9 },
        },
      ];

      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: faceResults,
          total: 1,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        const images = screen.getAllByRole('img');
        expect(images.length).toBeGreaterThan(0);
      });

      // Simulate image error
      const images = screen.getAllByRole('img');
      fireEvent.error(images[0]);

      await waitFor(() => {
        // Face detection placeholder is 👤
        expect(screen.getByText('👤')).toBeInTheDocument();
      });
    });

    it('shows correct placeholder icon for transcript', async () => {
      const transcriptResults = [
        {
          ...mockSearchResults[0],
          artifact_type: 'transcript.segment',
          preview: { text: 'Hello world' },
        },
      ];

      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: transcriptResults,
          total: 1,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        const images = screen.getAllByRole('img');
        expect(images.length).toBeGreaterThan(0);
      });

      // Simulate image error
      const images = screen.getAllByRole('img');
      fireEvent.error(images[0]);

      await waitFor(() => {
        // Transcript placeholder is 💬
        expect(screen.getByText('💬')).toBeInTheDocument();
      });
    });
  });

  describe('Loading State', () => {
    it('displays loading spinner while fetching', async () => {
      // Create a promise that doesn't resolve immediately
      mockFetch.mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<ArtifactGallery />);

      // Should show loading state
      expect(screen.getByText('Loading artifacts...')).toBeInTheDocument();
    });

    it('shows "Searching..." on search button while loading', async () => {
      mockFetch.mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<ArtifactGallery />);

      expect(screen.getByRole('button', { name: 'Searching...' })).toBeInTheDocument();
    });

    it('disables search button while loading', async () => {
      mockFetch.mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<ArtifactGallery />);

      const searchButton = screen.getByRole('button', { name: 'Searching...' });
      expect(searchButton).toBeDisabled();
    });
  });

  describe('Empty State', () => {
    it('displays "No results found" when search returns empty', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [],
          total: 0,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByText('No results found')).toBeInTheDocument();
      });
    });

    it('displays helpful suggestions in empty state', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [],
          total: 0,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByText('Try a different artifact type')).toBeInTheDocument();
        expect(screen.getByText('Use broader search terms')).toBeInTheDocument();
        expect(screen.getByText('Lower the confidence threshold')).toBeInTheDocument();
        expect(screen.getByText('Clear the filename filter')).toBeInTheDocument();
      });
    });

    it('displays search icon in empty state', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [],
          total: 0,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByText('🔍')).toBeInTheDocument();
      });
    });
  });

  describe('Error State', () => {
    it('displays error message on API failure', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        json: async () => ({ detail: 'Internal server error' }),
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByText('Something went wrong')).toBeInTheDocument();
        expect(screen.getByText('Internal server error')).toBeInTheDocument();
      });
    });

    it('displays retry button on error', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        json: async () => ({ detail: 'Internal server error' }),
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Try Again' })).toBeInTheDocument();
      });
    });
  });

  describe('Search Functionality', () => {
    it('triggers search on button click', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument();
      });

      // Clear mock to track new calls
      mockFetch.mockClear();
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      // Click search button
      fireEvent.click(screen.getByRole('button', { name: 'Search' }));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
        const callUrl = mockFetch.mock.calls[0][0];
        expect(callUrl).toContain('/v1/artifacts/search');
        expect(callUrl).toContain('kind=object');
      });
    });

    it('includes label parameter in search for object type', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('e.g., dog, car, person')).toBeInTheDocument();
      });

      // Enter a label
      const labelInput = screen.getByPlaceholderText('e.g., dog, car, person');
      fireEvent.change(labelInput, { target: { value: 'cat' } });

      // Wait for search button to be available (not in loading state)
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument();
      });

      // Clear mock and click search
      mockFetch.mockClear();
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      fireEvent.click(screen.getByRole('button', { name: 'Search' }));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
        const callUrl = mockFetch.mock.calls[0][0];
        expect(callUrl).toContain('label=cat');
      });
    });

    it('includes min_confidence parameter in search', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByRole('slider')).toBeInTheDocument();
      });

      // Change confidence slider
      const slider = screen.getByRole('slider');
      fireEvent.change(slider, { target: { value: '0.8' } });

      // Wait for search button to be available
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument();
      });

      // Clear mock and click search
      mockFetch.mockClear();
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockSearchResponse,
      });

      fireEvent.click(screen.getByRole('button', { name: 'Search' }));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
        const callUrl = mockFetch.mock.calls[0][0];
        expect(callUrl).toContain('min_confidence=0.8');
      });
    });
  });

  describe('Pagination', () => {
    it('displays pagination controls when results exist', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockSearchResponse,
          total: 50,
        }),
      });

      render(<ArtifactGallery />);

      // Wait for results to load first
      await waitFor(() => {
        expect(screen.getByText('dog (95%)')).toBeInTheDocument();
      });

      // Then check pagination - use queryByText with a function to find the element containing the text
      await waitFor(() => {
        // Find the div containing the pagination text
        // With 2 results, limit 20, total 50: shows "Showing 1-2 of 50 results"
        // But endResult = Math.min(offset + limit, total) = Math.min(0 + 20, 50) = 20
        // So it shows "Showing 1-20 of 50 results" because limit is 20
        const paginationDiv = document.querySelector('div[style*="color: rgb(153, 153, 153)"]');
        expect(paginationDiv?.textContent).toBe('Showing 1-20 of 50 results');
      });
    });

    it('displays page navigation buttons', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockSearchResponse,
          total: 100,
        }),
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'First' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Previous' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Last' })).toBeInTheDocument();
      });
    });

    it('disables Previous and First buttons on first page', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockSearchResponse,
          total: 100,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'First' })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
      });
    });
  });

  describe('Preview Text Rendering', () => {
    it('displays truncated text for transcript artifacts', async () => {
      const transcriptResults = [
        {
          ...mockSearchResults[0],
          artifact_type: 'transcript.segment',
          preview: { text: 'This is a very long transcript text that should be truncated after fifty characters to fit in the card' },
        },
      ];

      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: transcriptResults,
          total: 1,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        // Text should be truncated to 50 chars + "..."
        // First 50 chars: "This is a very long transcript text that should be"
        // With "...": "This is a very long transcript text that should be..."
        expect(screen.getByText('This is a very long transcript text that should be...')).toBeInTheDocument();
      });
    });

    it('displays face cluster ID for face detection', async () => {
      const faceResults = [
        {
          ...mockSearchResults[0],
          artifact_type: 'face.detection',
          preview: { cluster_id: 42, confidence: 0.9 },
        },
      ];

      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          results: faceResults,
          total: 1,
          limit: 20,
          offset: 0,
        }),
      });

      render(<ArtifactGallery />);

      await waitFor(() => {
        expect(screen.getByText('Face #42')).toBeInTheDocument();
      });
    });
  });
});
