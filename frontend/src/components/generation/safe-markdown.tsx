"use client";

import ReactMarkdown from "react-markdown";

/**
 * Render Markdown written by an AI model.
 * Safe by design: react-markdown builds React elements (no innerHTML), raw HTML
 * in the text is dropped (skipHtml), and unsafe link URLs are removed by its
 * default URL filter. Images are shown as their alt text so no remote content loads.
 */
export function SafeMarkdown({ text }: { text: string }) {
  return (
    <div className="prose-aszda text-sm">
      <ReactMarkdown
        skipHtml
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer nofollow">{children}</a>
          ),
          img: ({ alt }) => <span>{alt ? `[image: ${alt}]` : "[image]"}</span>,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
