/** Return a message that can be shown to the user for any thrown value. */
export function errorText(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message !== '') {
    return error.message
  }
  return fallback
}