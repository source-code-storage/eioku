/**
 * Application configuration.
 * 
 * API URL:
 * - Production (Docker): empty string (relative URLs via nginx proxy)
 * - Development (npm run dev outside Docker): set VITE_API_URL=http://localhost:8080
 */

export const API_URL = import.meta.env.VITE_API_URL ?? '';
