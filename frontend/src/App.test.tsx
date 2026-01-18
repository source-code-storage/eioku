import { render, screen } from '@testing-library/react'
import App from './App'

test('renders Eioku title', () => {
  render(<App />)
  const titleElement = screen.getByText(/eioku/i)
  expect(titleElement).toBeInTheDocument()
})

test('renders description', () => {
  render(<App />)
  const descElement = screen.getByText(/semantic video search platform/i)
  expect(descElement).toBeInTheDocument()
})
