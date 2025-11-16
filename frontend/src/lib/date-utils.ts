/**
 * Date formatting utilities for consistent date display across the application.
 */

/**
 * Formats a date string to a detailed format with date and time.
 * Example: "Jan 15, 2024, 02:30 PM"
 *
 * @param dateString - ISO date string to format
 * @returns Formatted date string
 */
export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/**
 * Formats a date string to a simple date format without time.
 * Example: "1/15/2024"
 *
 * @param dateString - ISO date string to format
 * @returns Formatted date string
 */
export function formatSimpleDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString();
}

/**
 * Formats a duration in seconds to a human-readable string.
 * Example: "1:23" for 83 seconds, "2:05:30" for 7530 seconds
 *
 * @param seconds - Duration in seconds
 * @returns Formatted duration string
 */
export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}
