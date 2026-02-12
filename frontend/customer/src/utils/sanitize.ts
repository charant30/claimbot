/**
 * Input sanitization utilities for XSS prevention
 */

/**
 * Sanitize user input by escaping HTML entities
 */
export function sanitizeHtml(input: string): string {
    const htmlEntities: Record<string, string> = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '/': '&#x2F;',
    }
    return input.replace(/[&<>"'/]/g, (char) => htmlEntities[char] || char)
}

/**
 * Sanitize message content for display
 * Allows basic markdown but escapes dangerous HTML
 */
export function sanitizeMessage(content: string): string {
    // First escape all HTML
    let sanitized = sanitizeHtml(content)

    // Then re-enable safe markdown-style formatting
    // Bold: **text** -> <strong>text</strong>
    sanitized = sanitized.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')

    // Convert newlines to <br> for display
    sanitized = sanitized.replace(/\n/g, '<br>')

    return sanitized
}

/**
 * Strip all HTML tags from input
 */
export function stripHtml(input: string): string {
    return input.replace(/<[^>]*>/g, '')
}

/**
 * Validate and sanitize URL
 */
export function sanitizeUrl(url: string): string | null {
    try {
        const parsed = new URL(url)
        // Only allow http and https protocols
        if (!['http:', 'https:'].includes(parsed.protocol)) {
            return null
        }
        return parsed.href
    } catch {
        return null
    }
}
